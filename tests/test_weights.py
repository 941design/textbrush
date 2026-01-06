"""Property-based tests for model weights management."""

from unittest.mock import patch

import pytest

from textbrush.model.weights import (
    _mask_token,
    download_flux_weights,
    get_cache_info,
)


class TestDownloadFailureHandling:
    """Tests for download failure scenarios."""

    def test_network_timeout_error(self):
        """Network timeout raises RuntimeError with helpful message."""
        with patch("textbrush.model.weights.is_flux_available", return_value=False):
            with patch("textbrush.model.weights.snapshot_download") as mock_download:
                mock_download.side_effect = TimeoutError("Connection timed out")

                with pytest.raises(RuntimeError) as exc_info:
                    download_flux_weights(force=False)

                error_msg = str(exc_info.value)
                assert "Failed to download FLUX.1 Schnell model" in error_msg
                assert "Network timeout" in error_msg
                assert "Cache location" in error_msg

    def test_authentication_error(self):
        """Authentication error raises RuntimeError with helpful message."""
        with patch("textbrush.model.weights.is_flux_available", return_value=False):
            with patch("textbrush.model.weights.snapshot_download") as mock_download:
                mock_download.side_effect = PermissionError("401 Unauthorized")

                with pytest.raises(RuntimeError) as exc_info:
                    download_flux_weights(force=False)

                error_msg = str(exc_info.value)
                assert "Failed to download FLUX.1 Schnell model" in error_msg
                assert "Authentication required" in error_msg
                assert "HF_TOKEN" in error_msg

    def test_disk_space_error(self):
        """Disk space error raises RuntimeError with helpful message."""
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
        with patch("textbrush.model.weights.is_flux_available", return_value=False):
            with patch("textbrush.model.weights.snapshot_download") as mock_download:
                mock_download.side_effect = Exception("Unexpected error")

                with pytest.raises(RuntimeError) as exc_info:
                    download_flux_weights(force=False)

                error_msg = str(exc_info.value)
                assert "Failed to download FLUX.1 Schnell model" in error_msg
                assert "Unexpected error" in error_msg

    def test_download_success_after_retry(self):
        """Download succeeds after error is resolved."""
        with patch("textbrush.model.weights.is_flux_available", return_value=False):
            with patch("textbrush.model.weights.snapshot_download") as mock_download:
                # First call succeeds
                mock_download.return_value = None

                # Should not raise
                download_flux_weights(force=False)

                assert mock_download.called

    def test_force_download_overrides_cache_check(self):
        """Force download re-downloads even if cached."""
        with patch("textbrush.model.weights.is_flux_available", return_value=True):
            with patch("textbrush.model.weights.snapshot_download") as mock_download:
                mock_download.return_value = None

                download_flux_weights(force=True)

                # Should call download even though is_flux_available returns True
                assert mock_download.called
                assert mock_download.call_args[1]["force_download"] is True

    def test_skip_download_if_cached(self):
        """Skip download if already cached and force=False."""
        with patch("textbrush.model.weights.is_flux_available", return_value=True):
            with patch("textbrush.model.weights.snapshot_download") as mock_download:
                download_flux_weights(force=False)

                # Should not call download
                assert not mock_download.called


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
        import os

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
        import os

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
        import os

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
