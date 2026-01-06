"""Shared fixtures for textbrush tests."""

from __future__ import annotations

from pathlib import Path

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
