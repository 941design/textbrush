"""Klein snapshots must include the prompt template used during generation."""

import fnmatch
import json
from unittest.mock import patch

import pytest

from tests.model_fixtures import write_complete_snapshot
from textbrush.model.registry import DiscoveryCause
from textbrush.model.weights import check_model_availability, download_model_weights

MODEL = "flux2-klein-4b"
TEMPLATE = "{{ messages[0]['content'] }}"


def test_download_repairs_previously_complete_cache_without_refetching_weights(tmp_path):
    root = tmp_path / "snapshot"
    write_complete_snapshot(root, MODEL)
    template = root / "tokenizer/chat_template.jinja"
    template.unlink()
    weight = next((root / "transformer").glob("*.safetensors"))
    original_weight = weight.read_bytes()

    def download(repo_id, *, allow_patterns, ignore_patterns, force_download):
        assert repo_id == "black-forest-labs/FLUX.2-klein-4B"
        assert not force_download
        filename = "tokenizer/chat_template.jinja"
        if any(fnmatch.fnmatch(filename, p) for p in allow_patterns) and not any(
            fnmatch.fnmatch(filename, p) for p in ignore_patterns
        ):
            template.write_text(TEMPLATE)
        return str(root)

    with (
        patch(
            "textbrush.model.weights.try_to_load_from_cache",
            return_value=str(root / "model_index.json"),
        ),
        patch("textbrush.model.weights.snapshot_download", side_effect=download) as fetch,
    ):
        before = check_model_availability(MODEL)
        assert not before.available
        assert before.cause == DiscoveryCause.INCOMPLETE
        assert "chat template" in before.detail
        assert download_model_weights(MODEL) == root
        fetch.assert_called_once()
        assert check_model_availability(MODEL).available
        assert download_model_weights(MODEL) == root
        fetch.assert_called_once()  # Fully repaired snapshots need no request.
    assert template.read_text() == TEMPLATE
    assert weight.read_bytes() == original_weight


@pytest.mark.parametrize(
    "embedded,available",
    [
        (TEMPLATE, True),
        ({"default": TEMPLATE}, True),
        ([{"name": "default", "template": TEMPLATE}], True),
        (None, False),
        ("", False),
        ("  \n", False),
        ({"tool_use": TEMPLATE}, False),
        ([{"name": "tool_use", "template": TEMPLATE}], False),
    ],
)
def test_embedded_default_templates(tmp_path, embedded, available):
    write_complete_snapshot(tmp_path, MODEL)
    (tmp_path / "tokenizer/chat_template.jinja").unlink()
    (tmp_path / "tokenizer/tokenizer_config.json").write_text(
        json.dumps({"chat_template": embedded})
    )
    with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
        assert check_model_availability(MODEL, custom_dirs=[tmp_path]).available is available


@pytest.mark.parametrize(
    "filename,content,available",
    [
        ("chat_template.jinja", TEMPLATE, True),
        ("chat_template.jinja", "", False),
        ("chat_templates/default.jinja", TEMPLATE, True),
        ("chat_templates/tool_use.jinja", TEMPLATE, False),
    ],
)
def test_standalone_templates_override_embedded_template(tmp_path, filename, content, available):
    write_complete_snapshot(tmp_path, MODEL)
    (tmp_path / "tokenizer/chat_template.jinja").unlink()
    (tmp_path / "tokenizer/tokenizer_config.json").write_text(
        json.dumps({"chat_template": TEMPLATE})
    )
    target = tmp_path / "tokenizer" / filename
    target.parent.mkdir(exist_ok=True)
    target.write_text(content)
    with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
        assert check_model_availability(MODEL, custom_dirs=[tmp_path]).available is available


def test_missing_custom_template_does_not_shadow_complete_cached_snapshot(tmp_path):
    custom, cached = tmp_path / "custom", tmp_path / "cached"
    for root in (custom, cached):
        write_complete_snapshot(root, MODEL)
    (custom / "tokenizer/chat_template.jinja").unlink()
    with patch(
        "textbrush.model.weights.try_to_load_from_cache",
        return_value=str(cached / "model_index.json"),
    ):
        report = check_model_availability(MODEL, custom_dirs=[custom])
    assert report.available
    assert report.root == cached


def test_schnell_does_not_require_chat_templates(tmp_path):
    write_complete_snapshot(tmp_path, "flux1-schnell")
    assert not list(tmp_path.rglob("*.jinja"))
    with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
        assert check_model_availability("flux1-schnell", custom_dirs=[tmp_path]).available


@pytest.mark.parametrize("content", [b"", b"\xff"])
def test_invalid_named_default_overrides_valid_root_default(tmp_path, content):
    write_complete_snapshot(tmp_path, MODEL)
    named = tmp_path / "tokenizer/chat_templates/default.jinja"
    named.parent.mkdir()
    named.write_bytes(content)
    with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
        report = check_model_availability(MODEL, custom_dirs=[tmp_path])
    assert report.cause == DiscoveryCause.INCOMPLETE
    assert "chat template" in report.detail
