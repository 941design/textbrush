"""Property-based tests for FluxInferenceEngine.load() method."""

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("torch")

import torch

from textbrush.inference.flux import FluxInferenceEngine


class TestLoadIdempotency:
    """Tests for load() idempotency property."""

    @patch("textbrush.inference.flux.FluxPipeline")
    @patch("torch.cuda.is_available")
    @patch("torch.backends.mps.is_available")
    def test_load_is_idempotent(self, mock_mps, mock_cuda, mock_pipeline_class):
        """Calling load() multiple times is safe and is a no-op after first call."""
        mock_cuda.return_value = False
        mock_mps.return_value = False
        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        engine = FluxInferenceEngine()

        engine.load()
        first_pipeline = engine._pipeline
        first_device = engine._device
        first_dtype = engine._dtype

        engine.load()
        engine.load()
        engine.load()

        assert engine._pipeline is first_pipeline
        assert engine._device == first_device
        assert engine._dtype is first_dtype
        assert mock_pipeline_class.from_pretrained.call_count == 1

    @patch("textbrush.inference.flux.FluxPipeline")
    @patch("torch.cuda.is_available")
    @patch("torch.backends.mps.is_available")
    @pytest.mark.parametrize("n", [1, 2, 5, 10])
    def test_load_n_times_calls_from_pretrained_once(
        self, mock_mps, mock_cuda, mock_pipeline_class, n
    ):
        """Loading N times only calls from_pretrained once."""
        mock_cuda.return_value = False
        mock_mps.return_value = False
        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        engine = FluxInferenceEngine()

        for _ in range(n):
            engine.load()

        assert mock_pipeline_class.from_pretrained.call_count == 1


class TestLoadStateTransition:
    """Tests for load() state transition property."""

    @patch("textbrush.inference.flux.FluxPipeline")
    @patch("torch.cuda.is_available")
    @patch("torch.backends.mps.is_available")
    def test_unloaded_to_loaded_state_transition(self, mock_mps, mock_cuda, mock_pipeline_class):
        """After load(), is_loaded() returns True."""
        mock_cuda.return_value = False
        mock_mps.return_value = False
        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        engine = FluxInferenceEngine()

        assert not engine.is_loaded()

        engine.load()

        assert engine.is_loaded()

    @patch("textbrush.inference.flux.FluxPipeline")
    @patch("torch.cuda.is_available")
    @patch("torch.backends.mps.is_available")
    def test_pipeline_initialized_after_load(self, mock_mps, mock_cuda, mock_pipeline_class):
        """After successful load, _pipeline is not None."""
        mock_cuda.return_value = False
        mock_mps.return_value = False
        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        engine = FluxInferenceEngine()

        assert engine._pipeline is None

        engine.load()

        assert engine._pipeline is not None


class TestDeviceAutoDetection:
    """Tests for device auto-detection property."""

    @patch("textbrush.inference.flux.FluxPipeline")
    @patch("torch.cuda.is_available")
    @patch("torch.backends.mps.is_available")
    def test_cuda_priority_when_available(self, mock_mps, mock_cuda, mock_pipeline_class):
        """When CUDA is available, device is 'cuda'."""
        mock_cuda.return_value = True
        mock_mps.return_value = True
        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        engine = FluxInferenceEngine()
        engine.load()

        assert engine._device == "cuda"
        assert engine.device == "cuda"

    @patch("textbrush.inference.flux.FluxPipeline")
    @patch("torch.cuda.is_available")
    @patch("torch.backends.mps.is_available")
    def test_mps_priority_when_cuda_unavailable(self, mock_mps, mock_cuda, mock_pipeline_class):
        """When CUDA unavailable but MPS available, device is 'mps'."""
        mock_cuda.return_value = False
        mock_mps.return_value = True
        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        engine = FluxInferenceEngine()
        engine.load()

        assert engine._device == "mps"
        assert engine.device == "mps"

    @patch("textbrush.inference.flux.FluxPipeline")
    @patch("torch.cuda.is_available")
    @patch("torch.backends.mps.is_available")
    def test_cpu_fallback_when_no_acceleration(self, mock_mps, mock_cuda, mock_pipeline_class):
        """When CUDA and MPS unavailable, device is 'cpu'."""
        mock_cuda.return_value = False
        mock_mps.return_value = False
        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        engine = FluxInferenceEngine()
        engine.load()

        assert engine._device == "cpu"
        assert engine.device == "cpu"

    @patch("textbrush.inference.flux.FluxPipeline")
    @patch("torch.cuda.is_available")
    @patch("torch.backends.mps.is_available")
    def test_device_is_one_of_valid_options(self, mock_mps, mock_cuda, mock_pipeline_class):
        """Device is always one of: cuda, mps, or cpu."""
        mock_cuda.return_value = False
        mock_mps.return_value = False
        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        engine = FluxInferenceEngine()
        engine.load()

        assert engine._device in ["cuda", "mps", "cpu"]


class TestDtypeSelection:
    """Tests for dtype selection based on device."""

    @patch("textbrush.inference.flux.FluxPipeline")
    @patch("torch.cuda.is_available")
    @patch("torch.backends.mps.is_available")
    def test_cuda_uses_bfloat16(self, mock_mps, mock_cuda, mock_pipeline_class):
        """CUDA device uses torch.bfloat16 dtype."""
        mock_cuda.return_value = True
        mock_mps.return_value = False
        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        engine = FluxInferenceEngine()
        engine.load()

        assert engine._dtype is torch.bfloat16
        mock_pipeline_class.from_pretrained.assert_called_once_with(
            FluxInferenceEngine.MODEL_ID, torch_dtype=torch.bfloat16
        )

    @patch("textbrush.inference.flux.FluxPipeline")
    @patch("torch.cuda.is_available")
    @patch("torch.backends.mps.is_available")
    def test_mps_uses_float32(self, mock_mps, mock_cuda, mock_pipeline_class):
        """MPS device uses torch.float32 dtype."""
        mock_cuda.return_value = False
        mock_mps.return_value = True
        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        engine = FluxInferenceEngine()
        engine.load()

        assert engine._dtype is torch.float32
        mock_pipeline_class.from_pretrained.assert_called_once_with(
            FluxInferenceEngine.MODEL_ID, torch_dtype=torch.float32
        )

    @patch("textbrush.inference.flux.FluxPipeline")
    @patch("torch.cuda.is_available")
    @patch("torch.backends.mps.is_available")
    def test_cpu_uses_float32(self, mock_mps, mock_cuda, mock_pipeline_class):
        """CPU device uses torch.float32 dtype."""
        mock_cuda.return_value = False
        mock_mps.return_value = False
        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        engine = FluxInferenceEngine()
        engine.load()

        assert engine._dtype is torch.float32
        mock_pipeline_class.from_pretrained.assert_called_once_with(
            FluxInferenceEngine.MODEL_ID, torch_dtype=torch.float32
        )


class TestDeviceOptimization:
    """Tests for device-specific optimization application."""

    @patch("textbrush.inference.flux.FluxPipeline")
    @patch("torch.cuda.is_available")
    @patch("torch.backends.mps.is_available")
    def test_cuda_uses_cpu_offload(self, mock_mps, mock_cuda, mock_pipeline_class):
        """CUDA device applies enable_model_cpu_offload()."""
        mock_cuda.return_value = True
        mock_mps.return_value = False
        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        engine = FluxInferenceEngine()
        engine.load()

        mock_pipeline.enable_model_cpu_offload.assert_called_once_with()
        mock_pipeline.to.assert_not_called()

    @patch("textbrush.inference.flux.FluxPipeline")
    @patch("torch.cuda.is_available")
    @patch("torch.backends.mps.is_available")
    def test_mps_uses_to_device(self, mock_mps, mock_cuda, mock_pipeline_class):
        """MPS device applies .to(device)."""
        mock_cuda.return_value = False
        mock_mps.return_value = True
        mock_pipeline = MagicMock()
        mock_pipeline.to.return_value = mock_pipeline
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        engine = FluxInferenceEngine()
        engine.load()

        mock_pipeline.to.assert_called_once_with("mps")
        mock_pipeline.enable_model_cpu_offload.assert_not_called()

    @patch("textbrush.inference.flux.FluxPipeline")
    @patch("torch.cuda.is_available")
    @patch("torch.backends.mps.is_available")
    def test_cpu_uses_to_device(self, mock_mps, mock_cuda, mock_pipeline_class):
        """CPU device applies .to(device)."""
        mock_cuda.return_value = False
        mock_mps.return_value = False
        mock_pipeline = MagicMock()
        mock_pipeline.to.return_value = mock_pipeline
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        engine = FluxInferenceEngine()
        engine.load()

        mock_pipeline.to.assert_called_once_with("cpu")
        mock_pipeline.enable_model_cpu_offload.assert_not_called()


class TestCpuWarningLog:
    """Tests for CPU warning log property."""

    @patch("textbrush.inference.flux.logger")
    @patch("textbrush.inference.flux.FluxPipeline")
    @patch("torch.cuda.is_available")
    @patch("torch.backends.mps.is_available")
    def test_cpu_logs_warning(self, mock_mps, mock_cuda, mock_pipeline_class, mock_logger):
        """Loading on CPU logs a warning."""
        mock_cuda.return_value = False
        mock_mps.return_value = False
        mock_pipeline = MagicMock()
        mock_pipeline.to.return_value = mock_pipeline
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        engine = FluxInferenceEngine()
        engine.load()

        mock_logger.warning.assert_called_once_with("Running on CPU - inference will be slow")

    @patch("textbrush.inference.flux.logger")
    @patch("textbrush.inference.flux.FluxPipeline")
    @patch("torch.cuda.is_available")
    @patch("torch.backends.mps.is_available")
    def test_cuda_does_not_log_warning(self, mock_mps, mock_cuda, mock_pipeline_class, mock_logger):
        """Loading on CUDA does not log warning."""
        mock_cuda.return_value = True
        mock_mps.return_value = False
        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        engine = FluxInferenceEngine()
        engine.load()

        mock_logger.warning.assert_not_called()

    @patch("textbrush.inference.flux.logger")
    @patch("textbrush.inference.flux.FluxPipeline")
    @patch("torch.cuda.is_available")
    @patch("torch.backends.mps.is_available")
    def test_mps_does_not_log_warning(self, mock_mps, mock_cuda, mock_pipeline_class, mock_logger):
        """Loading on MPS does not log warning."""
        mock_cuda.return_value = False
        mock_mps.return_value = True
        mock_pipeline = MagicMock()
        mock_pipeline.to.return_value = mock_pipeline
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        engine = FluxInferenceEngine()
        engine.load()

        mock_logger.warning.assert_not_called()


class TestModelIdInvariant:
    """Tests for MODEL_ID invariant."""

    @patch("textbrush.inference.flux.FluxPipeline")
    @patch("torch.cuda.is_available")
    @patch("torch.backends.mps.is_available")
    def test_loads_correct_model_id(self, mock_mps, mock_cuda, mock_pipeline_class):
        """Pipeline is loaded from correct MODEL_ID."""
        mock_cuda.return_value = False
        mock_mps.return_value = False
        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        engine = FluxInferenceEngine()
        engine.load()

        mock_pipeline_class.from_pretrained.assert_called_once()
        call_args = mock_pipeline_class.from_pretrained.call_args
        assert call_args[0][0] == FluxInferenceEngine.MODEL_ID
        assert call_args[0][0] == "black-forest-labs/FLUX.1-schnell"


class TestDevicePropertyConsistency:
    """Tests for device property consistency."""

    @patch("textbrush.inference.flux.FluxPipeline")
    @patch("torch.cuda.is_available")
    @patch("torch.backends.mps.is_available")
    def test_device_property_reflects_internal_device(
        self, mock_mps, mock_cuda, mock_pipeline_class
    ):
        """device property returns the same value as _device."""
        mock_cuda.return_value = False
        mock_mps.return_value = False
        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        engine = FluxInferenceEngine()
        engine.load()

        assert engine.device == engine._device

    @patch("textbrush.inference.flux.FluxPipeline")
    @patch("torch.cuda.is_available")
    @patch("torch.backends.mps.is_available")
    @pytest.mark.parametrize(
        "cuda_available,mps_available,expected_device",
        [
            (True, False, "cuda"),
            (False, True, "mps"),
            (False, False, "cpu"),
            (True, True, "cuda"),
        ],
    )
    def test_device_property_matches_detection_result(
        self,
        mock_mps,
        mock_cuda,
        mock_pipeline_class,
        cuda_available,
        mps_available,
        expected_device,
    ):
        """device property reflects detected hardware."""
        mock_cuda.return_value = cuda_available
        mock_mps.return_value = mps_available
        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        engine = FluxInferenceEngine()
        engine.load()

        assert engine.device == expected_device


class TestLoadUnloadLoadCycle:
    """Tests for load-unload-load cycle property."""

    @patch("textbrush.inference.flux.FluxPipeline")
    @patch("torch.cuda.is_available")
    @patch("torch.backends.mps.is_available")
    def test_load_unload_load_cycle(self, mock_mps, mock_cuda, mock_pipeline_class):
        """Load, unload, load cycle works correctly."""
        mock_cuda.return_value = False
        mock_mps.return_value = False
        mock_pipeline1 = MagicMock()
        mock_pipeline2 = MagicMock()
        mock_pipeline_class.from_pretrained.side_effect = [mock_pipeline1, mock_pipeline2]

        engine = FluxInferenceEngine()

        engine.load()
        assert engine.is_loaded()
        assert engine._device == "cpu"

        engine.unload()
        assert not engine.is_loaded()
        assert engine._device is None

        engine.load()
        assert engine.is_loaded()
        assert engine._device == "cpu"
        assert mock_pipeline_class.from_pretrained.call_count == 2

    @patch("textbrush.inference.flux.FluxPipeline")
    @patch("torch.cuda.is_available")
    @patch("torch.backends.mps.is_available")
    @pytest.mark.parametrize("n", [1, 2, 3, 5])
    def test_multiple_load_unload_cycles(self, mock_mps, mock_cuda, mock_pipeline_class, n):
        """Multiple load-unload cycles work correctly."""
        mock_cuda.return_value = False
        mock_mps.return_value = False
        mock_pipelines = [MagicMock() for _ in range(n)]
        mock_pipeline_class.from_pretrained.side_effect = mock_pipelines

        engine = FluxInferenceEngine()

        for i in range(n):
            engine.load()
            assert engine.is_loaded()

            engine.unload()
            assert not engine.is_loaded()

        assert mock_pipeline_class.from_pretrained.call_count == n
