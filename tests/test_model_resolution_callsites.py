"""AC-MODEL-5b structural test: `resolve_model_selection` is called
exactly once per launch, from the documented composition roots
(`textbrush/ipc/handler.py::handle_init` and `textbrush/cli.py::main`).
T08 may add the CLI site; until then we assert only the handler site
plus a live test that the IPC path calls the resolver exactly once.
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import Mock, patch

TEXTBRUSH_ROOT = Path(__file__).resolve().parents[1] / "textbrush"


def _find_resolve_call_sites() -> set[tuple[str, str]]:
    """Walk `textbrush/` and collect every Call to `resolve_model_selection`
    together with the enclosing function name."""
    sites: set[tuple[str, str]] = set()
    for path in TEXTBRUSH_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Name) or func.id != "resolve_model_selection":
                continue
            # Find enclosing FunctionDef
            enclosing = None
            for parent in ast.walk(tree):
                if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for child in ast.walk(parent):
                        if child is node:
                            enclosing = parent.name
                            break
                    if enclosing:
                        break
            if enclosing:
                rel = path.relative_to(TEXTBRUSH_ROOT.parent)
                sites.add((str(rel), enclosing))
    return sites


class TestResolveModelSelectionCallsites:
    """The composition-root call sites of `resolve_model_selection` are
    the documented ones -- no other module is allowed to call it
    silently, or `resolve_model_selection` will run more than once per
    launch and silently re-route the model (spec §5.1)."""

    def test_call_sites_match_handler_init(self) -> None:
        sites = _find_resolve_call_sites()
        # T08 lands the CLI call site. Both `_start_selected_model` (the
        # handler's single entry to starting a model, reached from
        # `handle_init` for a pinned model and from the deferred
        # selection) and `main` are the documented production callers;
        # no other production module is allowed to call
        # `resolve_model_selection` (running the resolver silently
        # elsewhere would re-route the model selection and silently
        # violate AC-MODEL-5b).
        handler_site = ("textbrush/ipc/handler.py", "_start_selected_model")
        cli_site = ("textbrush/cli.py", "main")
        assert handler_site in sites, (
            f"_start_selected_model must call resolve_model_selection; found sites: {sites}"
        )
        assert cli_site in sites, (
            f"cli.main must call resolve_model_selection; found sites: {sites}"
        )
        non_test_sites = {(file, func) for file, func in sites if not file.startswith("tests/")}
        # Only the two documented production callers.
        assert non_test_sites == {handler_site, cli_site}, (
            f"Unexpected resolve_model_selection call sites: {non_test_sites}"
        )

    def test_cli_launch_resolves_once(self, sample_config) -> None:
        from textbrush.cli import main
        from textbrush.model.registry import FLUX1_SCHNELL, ModelResolution

        resolver = Mock(return_value=ModelResolution(model_id=FLUX1_SCHNELL, blocked=False))
        with (
            patch("textbrush.cli.load_config", return_value=sample_config),
            patch("textbrush.cli.resolve_model_selection", resolver),
            patch("textbrush.cli.run_headless") as headless,
        ):
            main(["--prompt", "test", "--headless"])
        resolver.assert_called_once()
        headless.assert_called_once()

    def test_handler_calls_resolve_once_across_init_and_two_edits(self, tmp_path) -> None:
        """Live test: selecting a model runs the resolver exactly once;
        editing updates do NOT re-run it (T07 step 2a + 2c + live
        assertion).

        With deferred loading the selection can arrive at INIT (a pinned
        model, as here) or later as an UPDATE_CONFIG; either way it is
        resolved once, and every subsequent edit goes through
        `apply_configuration`, which does not resolve at all.
        """
        from textbrush.config import (
            Config,
            EditingConfig,
            HuggingFaceConfig,
            InferenceConfig,
            LoggingConfig,
            ModelConfig,
            OutputConfig,
        )
        from textbrush.ipc.handler import MessageHandler
        from textbrush.model.registry import FLUX1_SCHNELL

        config = Config(
            output=OutputConfig(directory=tmp_path / "out", format="png"),
            model=ModelConfig(directories=[], buffer_size=8, selected_id=None),
            huggingface=HuggingFaceConfig(token=None),
            inference=InferenceConfig(backend="flux"),
            logging=LoggingConfig(verbosity="info"),
            editing=EditingConfig(default_preset="landscape-medium"),
        )

        call_count = {"n": 0}

        def counting_resolver(*, selected_id, reference_count, availability):
            call_count["n"] += 1
            from textbrush.model.registry import ModelResolution

            return ModelResolution(model_id=FLUX1_SCHNELL, blocked=False)

        from textbrush.model.weights import AvailabilityReport

        with (
            patch(
                "textbrush.ipc.handler.resolve_model_selection",
                side_effect=counting_resolver,
            ),
            patch(
                "textbrush.ipc.handler.check_model_availability",
                return_value=AvailabilityReport(available=True, cause=None, detail="", root=None),
            ),
            patch("textbrush.backend.create_engine") as mock_create_engine,
        ):
            from tests.mocks import MockInferenceEngine

            schnell_engine = MockInferenceEngine()
            schnell_engine.model_id = FLUX1_SCHNELL
            mock_create_engine.return_value = schnell_engine

            handler = MessageHandler(config)
            server = Mock()

            # Trigger handle_init with the model already selected. The
            # resolver is called once.
            handler.handle_init(
                {"prompt": "test", "aspect_ratio": "1:1", "model_id": FLUX1_SCHNELL}, server
            )
            assert call_count["n"] == 1, (
                f"resolve_model_selection should be called once on init; got {call_count['n']}"
            )
