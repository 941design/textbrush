"""Shared fixtures for textbrush tests."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

# Import shared mock classes
from tests.mocks import MockInferenceEngine
from textbrush.config import (
    Config,
    HuggingFaceConfig,
    InferenceConfig,
    LoggingConfig,
    ModelConfig,
    OutputConfig,
)

if TYPE_CHECKING:
    from textbrush.inference.flux import FluxInferenceEngine


def pytest_addoption(parser):
    """Add command-line options for running slow/integration tests."""
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="Run slow tests that require model loading (memory intensive)",
    )


def pytest_collection_modifyitems(config, items):
    """Skip slow/integration tests unless --run-slow is passed.

    Also ensures slow tests run sequentially by checking for parallel execution.
    """
    run_slow = config.getoption("--run-slow")

    # Check if pytest-xdist is being used for parallel execution
    worker_id = getattr(config, "workerinput", {}).get("workerid", None)
    if worker_id is not None and run_slow:
        # Running in parallel with --run-slow is not allowed
        pytest.exit(
            "ERROR: Slow tests cannot run in parallel. Remove -n option when using --run-slow.",
            returncode=1,
        )

    if not run_slow:
        skip_slow = pytest.mark.skip(
            reason="Skipped by default (requires model, memory intensive). Use --run-slow to run."
        )
        for item in items:
            if "slow" in item.keywords or "integration" in item.keywords:
                item.add_marker(skip_slow)


# Session-scoped FLUX engine fixture - loaded once, reused across all tests
_flux_engine_instance: "FluxInferenceEngine | None" = None


@pytest.fixture(scope="session")
def flux_engine_session():
    """Session-scoped FLUX engine fixture.

    Loads the model once at the start of the test session and reuses it
    across all tests that require it. This avoids expensive model loading
    for each test.

    IMPORTANT: Tests using this fixture must NOT run in parallel as they
    share the same model instance and GPU memory.
    """
    global _flux_engine_instance

    from textbrush.inference.flux import FluxInferenceEngine

    if _flux_engine_instance is None:
        _flux_engine_instance = FluxInferenceEngine()
        _flux_engine_instance.load()

    yield _flux_engine_instance

    # Cleanup at end of session
    if _flux_engine_instance is not None:
        _flux_engine_instance.unload()
        _flux_engine_instance = None


@pytest.fixture
def mock_engine() -> MockInferenceEngine:
    """Create a mock inference engine for testing."""
    return MockInferenceEngine()


@pytest.fixture
def mock_engine_factory():
    """Factory fixture for creating mock engines with custom settings."""

    def _create(
        *,
        fail_on_load: bool = False,
        fail_on_generate: bool = False,
        fail_after_n_generations: int | None = None,
    ) -> MockInferenceEngine:
        return MockInferenceEngine(
            fail_on_load=fail_on_load,
            fail_on_generate=fail_on_generate,
            fail_after_n_generations=fail_after_n_generations,
        )

    return _create


@pytest.fixture
def sample_config(tmp_path: Path) -> Config:
    """Create a sample config for testing with temp directory for output."""
    return Config(
        output=OutputConfig(
            directory=tmp_path / "outputs",
            format="png",
        ),
        model=ModelConfig(
            directories=[],
            buffer_size=8,
        ),
        huggingface=HuggingFaceConfig(token=None),
        inference=InferenceConfig(backend="flux"),
        logging=LoggingConfig(verbosity="info"),
    )


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    """Create a temporary config file with default values."""
    import tomli_w

    config_path = tmp_path / "config.toml"
    config_data = {
        "output": {"directory": str(tmp_path / "outputs"), "format": "png"},
        "model": {"directories": [], "buffer_size": 8},
        "huggingface": {},
        "inference": {"backend": "flux"},
        "logging": {"verbosity": "info"},
    }
    with open(config_path, "wb") as f:
        tomli_w.dump(config_data, f)
    return config_path
