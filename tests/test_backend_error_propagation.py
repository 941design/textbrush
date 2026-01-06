"""Property-based tests for TextbrushBackend error checking."""

from unittest.mock import Mock

import hypothesis.strategies as st
from hypothesis import given, settings

from textbrush.backend import TextbrushBackend
from textbrush.config import Config, InferenceConfig, ModelConfig
from textbrush.worker import GenerationWorker


class TestBackendErrorPropagationProperties:
    """Property-based tests for backend error checking."""

    def test_backend_check_worker_error_delegates_correctly(self):
        """Property: backend.check_worker_error() delegates to worker.get_error()."""
        mock_config = Mock(spec=Config)
        mock_config.inference = Mock(spec=InferenceConfig)
        mock_config.inference.backend = "flux"
        mock_config.model = Mock(spec=ModelConfig)
        mock_config.model.buffer_size = 8

        backend = TextbrushBackend(mock_config)

        mock_worker = Mock(spec=GenerationWorker)
        test_error = RuntimeError("Test backend error")
        mock_worker.get_error.return_value = test_error

        backend._worker = mock_worker

        result = backend.check_worker_error()

        assert result is test_error
        mock_worker.get_error.assert_called_once()

    def test_backend_check_worker_error_no_worker(self):
        """Property: backend.check_worker_error() returns None if no worker."""
        mock_config = Mock(spec=Config)
        mock_config.inference = Mock(spec=InferenceConfig)
        mock_config.inference.backend = "flux"
        mock_config.model = Mock(spec=ModelConfig)
        mock_config.model.buffer_size = 8

        backend = TextbrushBackend(mock_config)
        backend._worker = None

        result = backend.check_worker_error()

        assert result is None

    def test_backend_check_worker_error_returns_none_on_success(self):
        """Property: backend returns None when worker has no error."""
        mock_config = Mock(spec=Config)
        mock_config.inference = Mock(spec=InferenceConfig)
        mock_config.inference.backend = "flux"
        mock_config.model = Mock(spec=ModelConfig)
        mock_config.model.buffer_size = 8

        backend = TextbrushBackend(mock_config)

        mock_worker = Mock(spec=GenerationWorker)
        mock_worker.get_error.return_value = None

        backend._worker = mock_worker

        result = backend.check_worker_error()

        assert result is None
        mock_worker.get_error.assert_called_once()

    @given(error_message=st.text(min_size=1, max_size=100))
    @settings(max_examples=20, deadline=None)
    def test_backend_propagates_error_message(self, error_message: str):
        """Property: error message is preserved through backend delegation."""
        mock_config = Mock(spec=Config)
        mock_config.inference = Mock(spec=InferenceConfig)
        mock_config.inference.backend = "flux"
        mock_config.model = Mock(spec=ModelConfig)
        mock_config.model.buffer_size = 8

        backend = TextbrushBackend(mock_config)

        test_error = ValueError(error_message)
        mock_worker = Mock(spec=GenerationWorker)
        mock_worker.get_error.return_value = test_error

        backend._worker = mock_worker

        result = backend.check_worker_error()

        assert result is test_error
        assert str(result) == error_message
