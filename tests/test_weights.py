"""Property-based tests for model weights management."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from textbrush.model.weights import (
    TokenRequiredError,
    _mask_token,
    download_flux_weights,
    get_cache_info,
)


class TestDownloadFailureHandling:
    """Tests for download failure scenarios."""

    def test_network_timeout_error(self):
        """Network timeout raises RuntimeError with helpful message."""
        with patch.dict(os.environ, {"HF_TOKEN": "hf_test_token"}):
            with patch("textbrush.model.weights.is_flux_available", return_value=False):
                with patch("textbrush.model.weights.snapshot_download") as mock_download:
                    mock_download.side_effect = TimeoutError("Connection timed out")

                    with pytest.raises(RuntimeError) as exc_info:
                        download_flux_weights(force=False)

                    error_msg = str(exc_info.value)
                    assert "Failed to download FLUX.1 Schnell model" in error_msg
                    assert "Network timeout" in error_msg
                    assert "Cache location" in error_msg

    def test_authentication_error_generic(self):
        """Generic PermissionError raises RuntimeError (not TokenRequiredError)."""
        with patch.dict(os.environ, {"HF_TOKEN": "hf_test_token"}):
            with patch("textbrush.model.weights.is_flux_available", return_value=False):
                with patch("textbrush.model.weights.snapshot_download") as mock_download:
                    mock_download.side_effect = PermissionError("Permission denied")

                    with pytest.raises(RuntimeError) as exc_info:
                        download_flux_weights(force=False)

                    error_msg = str(exc_info.value)
                    assert "Failed to download FLUX.1 Schnell model" in error_msg

    def test_disk_space_error(self):
        """Disk space error raises RuntimeError with helpful message."""
        with patch.dict(os.environ, {"HF_TOKEN": "hf_test_token"}):
            with patch("textbrush.model.weights.is_flux_available", return_value=False):
                with patch("textbrush.model.weights.snapshot_download") as mock_download:
                    mock_download.side_effect = OSError("No space left on device")

                    with pytest.raises(RuntimeError) as exc_info:
                        download_flux_weights(force=False)

                    error_msg = str(exc_info.value)
                    assert "Failed to download FLUX.1 Schnell model" in error_msg
                    assert "Insufficient disk space" in error_msg

    def test_generic_download_error(self):
        """Generic download error raises RuntimeError with helpful message."""
        with patch.dict(os.environ, {"HF_TOKEN": "hf_test_token"}):
            with patch("textbrush.model.weights.is_flux_available", return_value=False):
                with patch("textbrush.model.weights.snapshot_download") as mock_download:
                    mock_download.side_effect = Exception("Unexpected error")

                    with pytest.raises(RuntimeError) as exc_info:
                        download_flux_weights(force=False)

                    error_msg = str(exc_info.value)
                    assert "Failed to download FLUX.1 Schnell model" in error_msg
                    assert "Unexpected error" in error_msg

    def test_download_success_returns_path(self):
        """Successful download returns Path to snapshot directory."""
        with patch.dict(os.environ, {"HF_TOKEN": "hf_test_token"}):
            with patch("textbrush.model.weights.is_flux_available", return_value=False):
                with patch("textbrush.model.weights.snapshot_download") as mock_download:
                    mock_download.return_value = "/tmp/hf_cache/models--test/snapshots/abc123"

                    result = download_flux_weights(force=False)

                    assert isinstance(result, Path)
                    assert str(result) == "/tmp/hf_cache/models--test/snapshots/abc123"
                    assert mock_download.called

    def test_force_download_overrides_cache_check(self):
        """Force download re-downloads even if cached."""
        with patch.dict(os.environ, {"HF_TOKEN": "hf_test_token"}):
            with patch("textbrush.model.weights.is_flux_available", return_value=True):
                with patch("textbrush.model.weights.snapshot_download") as mock_download:
                    mock_download.return_value = "/tmp/hf_cache/models--test/snapshots/abc123"

                    result = download_flux_weights(force=True)

                    # Should call download even though is_flux_available returns True
                    assert mock_download.called
                    assert mock_download.call_args[1]["force_download"] is True
                    assert isinstance(result, Path)

    def test_skip_download_if_cached_no_token_needed(self):
        """Skip download if already cached — HF_TOKEN not required for cache reads."""
        with patch("textbrush.model.weights.is_flux_available", return_value=True):
            with patch("textbrush.model.weights.snapshot_download") as mock_download:
                with patch("textbrush.model.weights.get_cache_info") as mock_cache_info:
                    mock_cache_dir = MagicMock()
                    mock_cache_dir.__truediv__ = MagicMock(
                        return_value=MagicMock(
                            is_dir=MagicMock(return_value=False)
                        )
                    )
                    mock_cache_info.return_value = {
                        "cache_dir": mock_cache_dir,
                        "custom_location": False,
                        "env_var": None,
                    }
                    # Ensure HF_TOKEN is NOT set
                    env = {k: v for k, v in os.environ.items() if k != "HF_TOKEN"}
                    with patch.dict(os.environ, env, clear=True):
                        # Should not raise TokenRequiredError when already cached
                        download_flux_weights(force=False)

                    # Should not call download
                    assert not mock_download.called


class TestTokenRequiredError:
    """Tests for TokenRequiredError exception class and related behavior."""

    def test_token_required_error_is_exception(self):
        """TokenRequiredError inherits from Exception."""
        err = TokenRequiredError("test message")
        assert isinstance(err, Exception)
        assert str(err) == "test message"

    def test_raises_token_required_when_no_hf_token(self):
        """TokenRequiredError raised when HF_TOKEN not set and download needed."""
        with patch("textbrush.model.weights.is_flux_available", return_value=False):
            env = {k: v for k, v in os.environ.items() if k != "HF_TOKEN"}
            with patch.dict(os.environ, env, clear=True):
                with pytest.raises(TokenRequiredError) as exc_info:
                    download_flux_weights(force=False)

                assert "HF_TOKEN" in str(exc_info.value)

    def test_raises_token_required_on_gated_repo_error(self):
        """GatedRepoError from HF hub raises TokenRequiredError."""
        from huggingface_hub.utils import GatedRepoError

        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch.dict(os.environ, {"HF_TOKEN": "hf_test_token"}):
            with patch("textbrush.model.weights.is_flux_available", return_value=False):
                with patch("textbrush.model.weights.snapshot_download") as mock_download:
                    mock_download.side_effect = GatedRepoError(
                        "Repository access restricted", response=mock_response
                    )

                    with pytest.raises(TokenRequiredError) as exc_info:
                        download_flux_weights(force=False)

                    assert "Access denied" in str(exc_info.value)
                    assert "license" in str(exc_info.value)

    def test_raises_token_required_on_hf_http_401(self):
        """HfHubHTTPError with 401 status raises TokenRequiredError."""
        from huggingface_hub.utils import HfHubHTTPError

        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch.dict(os.environ, {"HF_TOKEN": "hf_invalid_token"}):
            with patch("textbrush.model.weights.is_flux_available", return_value=False):
                with patch("textbrush.model.weights.snapshot_download") as mock_download:
                    mock_download.side_effect = HfHubHTTPError(
                        "Unauthorized", response=mock_response
                    )

                    with pytest.raises(TokenRequiredError) as exc_info:
                        download_flux_weights(force=False)

                    assert "401" in str(exc_info.value)

    def test_raises_token_required_on_hf_http_403(self):
        """HfHubHTTPError with 403 status raises TokenRequiredError."""
        from huggingface_hub.utils import HfHubHTTPError

        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch.dict(os.environ, {"HF_TOKEN": "hf_test_token"}):
            with patch("textbrush.model.weights.is_flux_available", return_value=False):
                with patch("textbrush.model.weights.snapshot_download") as mock_download:
                    mock_download.side_effect = HfHubHTTPError(
                        "Forbidden", response=mock_response
                    )

                    with pytest.raises(TokenRequiredError) as exc_info:
                        download_flux_weights(force=False)

                    assert "403" in str(exc_info.value)

    def test_hf_http_non_auth_error_raises_runtime_error(self):
        """HfHubHTTPError with non-auth status code raises RuntimeError (not TokenRequiredError)."""
        from huggingface_hub.utils import HfHubHTTPError

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.dict(os.environ, {"HF_TOKEN": "hf_test_token"}):
            with patch("textbrush.model.weights.is_flux_available", return_value=False):
                with patch("textbrush.model.weights.snapshot_download") as mock_download:
                    mock_download.side_effect = HfHubHTTPError(
                        "Internal Server Error", response=mock_response
                    )

                    with pytest.raises(RuntimeError):
                        download_flux_weights(force=False)


class TestTokenMasking:
    """Tests for token masking in error messages."""

    def test_mask_none_token(self):
        """None token is displayed as 'None'."""
        assert _mask_token(None) == "None"

    def test_mask_short_token(self):
        """Short tokens are fully masked."""
        assert _mask_token("short") == "***"
        assert _mask_token("1234567") == "***"
        assert _mask_token("12345678") == "***"

    def test_mask_long_token(self):
        """Long tokens show first 4 and last 4 characters."""
        token = "hf_abcdefghijklmnopqrstuvwxyz"
        masked = _mask_token(token)

        assert masked.startswith("hf_a")
        assert masked.endswith("wxyz")
        assert "..." in masked
        assert len(masked) < len(token)

    def test_mask_preserves_security(self):
        """Masked token doesn't expose the middle portion."""
        token = "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123"
        masked = _mask_token(token)

        # Middle should not be visible
        assert "Middle" not in masked
        assert "Secret" not in masked.replace("hf_S", "")
        assert "Hidden" not in masked


class TestCacheInfo:
    """Tests for cache information retrieval."""

    def test_default_cache_location(self):
        """Default cache location is in home directory."""
        original_hf_home = os.environ.get("HF_HOME")
        original_hf_hub_cache = os.environ.get("HF_HUB_CACHE")

        try:
            # Clear env vars to test default
            if "HF_HOME" in os.environ:
                del os.environ["HF_HOME"]
            if "HF_HUB_CACHE" in os.environ:
                del os.environ["HF_HUB_CACHE"]

            cache_info = get_cache_info()

            assert cache_info["custom_location"] is False
            assert cache_info["env_var"] is None
            assert ".cache/huggingface/hub" in str(cache_info["cache_dir"])

        finally:
            # Restore original env vars
            if original_hf_home:
                os.environ["HF_HOME"] = original_hf_home
            if original_hf_hub_cache:
                os.environ["HF_HUB_CACHE"] = original_hf_hub_cache

    def test_custom_hf_hub_cache_location(self):
        """HF_HUB_CACHE env var sets custom cache location."""
        original = os.environ.get("HF_HUB_CACHE")

        try:
            os.environ["HF_HUB_CACHE"] = "/custom/cache"

            cache_info = get_cache_info()

            assert cache_info["custom_location"] is True
            assert cache_info["env_var"] == "HF_HUB_CACHE"
            assert str(cache_info["cache_dir"]) == "/custom/cache"

        finally:
            if original:
                os.environ["HF_HUB_CACHE"] = original
            else:
                del os.environ["HF_HUB_CACHE"]

    def test_custom_hf_home_location(self):
        """HF_HOME env var sets custom cache location."""
        original_home = os.environ.get("HF_HOME")
        original_cache = os.environ.get("HF_HUB_CACHE")

        try:
            # Clear HF_HUB_CACHE to test HF_HOME fallback
            if "HF_HUB_CACHE" in os.environ:
                del os.environ["HF_HUB_CACHE"]

            os.environ["HF_HOME"] = "/custom/home"

            cache_info = get_cache_info()

            assert cache_info["custom_location"] is True
            assert cache_info["env_var"] == "HF_HOME"
            assert str(cache_info["cache_dir"]) == "/custom/home/hub"

        finally:
            if original_home:
                os.environ["HF_HOME"] = original_home
            elif "HF_HOME" in os.environ:
                del os.environ["HF_HOME"]

            if original_cache:
                os.environ["HF_HUB_CACHE"] = original_cache
