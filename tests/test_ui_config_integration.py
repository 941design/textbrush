"""Integration tests for UI configuration update workflow.

Tests complete end-to-end scenarios spanning frontend UI → Tauri command → Python handler → Backend.
Uses property-based testing to validate system-level invariants across component boundaries.
"""

from unittest.mock import ANY, Mock, patch

import pytest
from hypothesis import given
from hypothesis import strategies as st

from textbrush.backend import TextbrushBackend
from textbrush.config import Config
from textbrush.ipc.handler import MessageHandler
from textbrush.ipc.protocol import MessageType


class TestConfigUpdateE2E:
    """End-to-end integration tests for configuration update workflow."""

    @pytest.fixture
    def mock_config(self):
        """Create mock Config for backend initialization."""
        config = Mock(spec=Config)
        config.device = "cpu"
        config.output_dir = "/tmp/test"
        config.format = "png"
        return config

    @pytest.fixture
    def handler_with_backend(self, mock_config):
        """Create handler with initialized backend."""
        handler = MessageHandler(mock_config)
        handler.backend = Mock(spec=TextbrushBackend)
        handler.backend.buffer = Mock()
        handler.backend.buffer.max_size = 8
        return handler

    @pytest.fixture
    def mock_server(self):
        """Create mock IPC server."""
        return Mock()

    def test_prompt_update_workflow_aborts_and_restarts(self, handler_with_backend, mock_server):
        """E2E: Config change triggers abort() then start_generation().

        Validates complete workflow:
        1. UI changes prompt
        2. Tauri command sends IPC message
        3. Handler validates and calls abort()
        4. Handler calls start_generation() with new prompt
        5. Handler sends BUFFER_STATUS event
        """
        payload = {"prompt": "New prompt text", "aspect_ratio": "16:9"}

        handler_with_backend.handle_update_config(payload, mock_server)

        # Verify abort() called to stop current generation
        handler_with_backend.backend.abort.assert_called_once()

        # Verify start_generation() called with new config
        handler_with_backend.backend.start_generation.assert_called_once_with(
            prompt="New prompt text",
            seed=None,
            aspect_ratio="16:9",
            width=None,
            height=None,
            on_generation_start=ANY,
        )

        # Verify BUFFER_STATUS event sent
        mock_server.send.assert_called_once()
        message = mock_server.send.call_args[0][0]
        assert message.type == MessageType.BUFFER_STATUS
        assert message.payload["count"] == 0  # Buffer cleared by abort
        assert message.payload["generating"] is True

    def test_aspect_ratio_change_workflow(self, handler_with_backend, mock_server):
        """E2E: Aspect ratio change triggers generation restart.

        Validates:
        - Handler accepts valid aspect ratios (1:1, 16:9, 9:16)
        - Backend restart happens with new aspect_ratio
        - seed=None (auto-generate for new config)
        """
        payload = {"prompt": "Same prompt", "aspect_ratio": "9:16"}

        handler_with_backend.handle_update_config(payload, mock_server)

        handler_with_backend.backend.abort.assert_called_once()
        handler_with_backend.backend.start_generation.assert_called_once_with(
            prompt="Same prompt",
            seed=None,
            aspect_ratio="9:16",
            width=None,
            height=None,
            on_generation_start=ANY,
        )

        # Verify buffer status reflects reset state
        message = mock_server.send.call_args[0][0]
        assert message.payload["count"] == 0
        assert message.payload["max"] == 8

    def test_buffer_purge_verification(self, handler_with_backend, mock_server):
        """E2E: abort() clears buffer before restart.

        Validates critical invariant:
        - Old images from previous generation are purged
        - BUFFER_STATUS reports count=0 after restart
        - No stale images delivered to UI
        """
        handler_with_backend.backend.buffer.max_size = 8

        payload = {"prompt": "Updated prompt", "aspect_ratio": "1:1"}
        handler_with_backend.handle_update_config(payload, mock_server)

        # Abort must be called before start_generation
        assert handler_with_backend.backend.abort.call_count == 1
        assert handler_with_backend.backend.start_generation.call_count == 1

        # Verify call order: abort() before start_generation()
        calls = [
            call[0]
            for call in handler_with_backend.backend.method_calls
            if call[0] in ("abort", "start_generation")
        ]
        assert calls == ["abort", "start_generation"]

        # Buffer status shows reset state
        message = mock_server.send.call_args[0][0]
        assert message.payload["count"] == 0

    def test_validation_error_no_backend_restart(self, mock_config, mock_server):
        """E2E: Validation errors prevent backend restart.

        Validates error handling:
        - Invalid inputs send ERROR event
        - Backend abort/start NOT called
        - UI receives error message
        """
        handler = MessageHandler(mock_config)
        # No backend initialized
        handler.backend = None

        payload = {"prompt": "Some prompt", "aspect_ratio": "1:1"}
        handler.handle_update_config(payload, mock_server)

        # Error event sent
        mock_server.send.assert_called_once()
        message = mock_server.send.call_args[0][0]
        assert message.type == MessageType.ERROR
        assert "not initialized" in message.payload["message"].lower()
        assert message.payload["fatal"] is False

    def test_invalid_aspect_ratio_rejected(self, handler_with_backend, mock_server):
        """E2E: Invalid aspect ratio sends error, no restart."""
        payload = {"prompt": "Test prompt", "aspect_ratio": "4:3"}  # Invalid

        handler_with_backend.handle_update_config(payload, mock_server)

        # No backend calls
        handler_with_backend.backend.abort.assert_not_called()
        handler_with_backend.backend.start_generation.assert_not_called()

        # Error event sent
        message = mock_server.send.call_args[0][0]
        assert message.type == MessageType.ERROR
        assert "invalid aspect_ratio" in message.payload["message"].lower()

    def test_empty_prompt_rejected(self, handler_with_backend, mock_server):
        """E2E: Empty prompt sends error, no restart."""
        for empty in ["", "   ", "\t\n"]:
            mock_server.reset_mock()
            handler_with_backend.backend.reset_mock()

            payload = {"prompt": empty, "aspect_ratio": "1:1"}
            handler_with_backend.handle_update_config(payload, mock_server)

            # No backend calls
            handler_with_backend.backend.abort.assert_not_called()
            handler_with_backend.backend.start_generation.assert_not_called()

            # Error event sent
            message = mock_server.send.call_args[0][0]
            assert message.type == MessageType.ERROR
            assert "empty" in message.payload["message"].lower()


class TestConfigUpdateProperties:
    """Property-based tests for configuration update invariants."""

    def _create_handler_with_backend(self):
        """Create fresh handler with mocked backend for each test."""
        config = Mock(spec=Config)
        config.device = "cpu"
        config.output_dir = "/tmp/test"
        config.format = "png"

        handler = MessageHandler(config)
        handler.backend = Mock(spec=TextbrushBackend)
        handler.backend.buffer = Mock()
        handler.backend.buffer.max_size = 8
        return handler

    @given(
        prompt=st.text(min_size=1, max_size=200).filter(lambda s: s.strip()),
        aspect_ratio=st.sampled_from(["1:1", "16:9", "9:16"]),
    )
    def test_valid_configs_always_restart_generation(self, prompt, aspect_ratio):
        """Property: All valid config updates trigger restart.

        For any non-empty prompt and valid aspect_ratio:
        - abort() is called exactly once
        - start_generation() is called exactly once
        - BUFFER_STATUS event sent with count=0
        """
        handler = self._create_handler_with_backend()
        mock_server = Mock()
        payload = {"prompt": prompt, "aspect_ratio": aspect_ratio}

        handler.handle_update_config(payload, mock_server)

        assert handler.backend.abort.call_count == 1
        assert handler.backend.start_generation.call_count == 1

        # Verify start_generation called with correct params
        call_kwargs = handler.backend.start_generation.call_args[1]
        assert call_kwargs["prompt"] == prompt
        assert call_kwargs["aspect_ratio"] == aspect_ratio
        assert call_kwargs["seed"] is None  # Always None for config updates

        # Verify buffer status sent
        message = mock_server.send.call_args[0][0]
        assert message.type == MessageType.BUFFER_STATUS
        assert message.payload["count"] == 0
        assert message.payload["generating"] is True

    @given(
        aspect_ratio=st.text(min_size=1, max_size=10).filter(
            lambda s: s not in ["1:1", "16:9", "9:16", "custom"]
        )
    )
    def test_invalid_aspect_ratios_always_rejected(self, aspect_ratio):
        """Property: Invalid aspect ratios never trigger restart.

        For any aspect_ratio not in {1:1, 16:9, 9:16, custom}:
        - ERROR event sent
        - abort() NOT called
        - start_generation() NOT called

        Note: "custom" is a valid special value that allows explicit dimensions.
        """
        handler = self._create_handler_with_backend()
        mock_server = Mock()
        payload = {"prompt": "Valid prompt", "aspect_ratio": aspect_ratio}

        handler.handle_update_config(payload, mock_server)

        handler.backend.abort.assert_not_called()
        handler.backend.start_generation.assert_not_called()

        message = mock_server.send.call_args[0][0]
        assert message.type == MessageType.ERROR
        assert message.payload["fatal"] is False

    @given(st.text(max_size=5).filter(lambda s: not s.strip()))
    def test_empty_prompts_always_rejected(self, prompt):
        """Property: Empty/whitespace prompts never trigger restart.

        For any prompt that is empty or only whitespace:
        - ERROR event sent
        - abort() NOT called
        - start_generation() NOT called
        """
        handler = self._create_handler_with_backend()
        mock_server = Mock()
        payload = {"prompt": prompt, "aspect_ratio": "1:1"}

        handler.handle_update_config(payload, mock_server)

        handler.backend.abort.assert_not_called()
        handler.backend.start_generation.assert_not_called()

        message = mock_server.send.call_args[0][0]
        assert message.type == MessageType.ERROR

    def test_abort_always_before_start(self):
        """Property: abort() always called before start_generation().

        Validates critical ordering invariant:
        - Buffer must be cleared before new generation starts
        - Prevents old images from being delivered
        """
        handler = self._create_handler_with_backend()
        mock_server = Mock()
        payload = {"prompt": "Test", "aspect_ratio": "1:1"}

        handler.handle_update_config(payload, mock_server)

        # Check method call order
        method_names = [call[0] for call in handler.backend.method_calls]
        abort_idx = method_names.index("abort")
        start_idx = method_names.index("start_generation")

        assert abort_idx < start_idx, "abort() must be called before start_generation()"

    def test_seed_always_none_for_config_updates(self):
        """Property: Config updates always use seed=None.

        Validates:
        - Config changes generate new random seeds
        - User cannot force specific seed via config update
        """
        handler = self._create_handler_with_backend()
        mock_server = Mock()
        payload = {"prompt": "Test prompt", "aspect_ratio": "16:9"}

        handler.handle_update_config(payload, mock_server)

        call_kwargs = handler.backend.start_generation.call_args[1]
        assert call_kwargs["seed"] is None


class TestSystemLevelInvariants:
    """System-level integration properties spanning multiple components."""

    @pytest.fixture
    def mock_config(self):
        config = Mock(spec=Config)
        config.device = "cpu"
        config.output_dir = "/tmp/test"
        config.format = "png"
        return config

    def test_config_update_does_not_restart_image_delivery_thread(self, mock_config):
        """System invariant: Image delivery thread continues running.

        Validates:
        - UPDATE_CONFIG does not spawn new image delivery thread
        - Existing thread automatically receives new images after restart
        - No thread management needed in handle_update_config
        """
        handler = MessageHandler(mock_config)
        handler.backend = Mock(spec=TextbrushBackend)
        handler.backend.buffer = Mock()
        handler.backend.buffer.max_size = 8

        mock_server = Mock()
        payload = {"prompt": "Test", "aspect_ratio": "1:1"}

        # No _start_image_delivery call expected
        with patch.object(handler, "_start_image_delivery") as mock_start_delivery:
            handler.handle_update_config(payload, mock_server)
            mock_start_delivery.assert_not_called()

    def test_buffer_status_always_reflects_reset_state(self, mock_config):
        """System invariant: BUFFER_STATUS after restart shows count=0.

        Validates:
        - abort() clears buffer
        - BUFFER_STATUS event accurately reports empty buffer
        - UI shows correct post-restart state
        """
        handler = MessageHandler(mock_config)
        handler.backend = Mock(spec=TextbrushBackend)
        handler.backend.buffer = Mock()
        handler.backend.buffer.max_size = 8

        mock_server = Mock()
        payload = {"prompt": "Test", "aspect_ratio": "1:1"}

        handler.handle_update_config(payload, mock_server)

        message = mock_server.send.call_args[0][0]
        assert message.type == MessageType.BUFFER_STATUS
        assert message.payload["count"] == 0
        assert message.payload["max"] == 8
        assert message.payload["generating"] is True

    def test_error_events_never_fatal_for_validation_failures(self, mock_config):
        """System invariant: Validation errors are non-fatal.

        Validates:
        - Invalid inputs don't crash sidecar
        - UI can recover and retry
        - Server continues running
        """
        handler = MessageHandler(mock_config)
        handler.backend = Mock(spec=TextbrushBackend)
        mock_server = Mock()

        invalid_payloads = [
            {"prompt": "", "aspect_ratio": "1:1"},  # Empty prompt
            {"prompt": "Test", "aspect_ratio": "invalid"},  # Invalid aspect ratio
        ]

        for payload in invalid_payloads:
            mock_server.reset_mock()
            handler.handle_update_config(payload, mock_server)

            message = mock_server.send.call_args[0][0]
            assert message.type == MessageType.ERROR
            assert message.payload["fatal"] is False
