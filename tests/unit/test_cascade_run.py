"""Tests for agentpipe.cascade_run — CLI entry point."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agentpipe.cascade import CascadeResult, ModelTier
from agentpipe.cascade_run import _tier_from_name, main


class TestTierFromName:
    def test_free(self):
        assert _tier_from_name("free") == ModelTier.FREE

    def test_cheap(self):
        assert _tier_from_name("cheap") == ModelTier.CHEAP

    def test_mid(self):
        assert _tier_from_name("mid") == ModelTier.MID

    def test_premium(self):
        assert _tier_from_name("premium") == ModelTier.PREMIUM

    def test_unknown_raises(self):
        with pytest.raises(KeyError):
            _tier_from_name("nonexistent")


class TestCascadeRunMain:
    @patch(
        "agentpipe.cascade_run.cascade",
        new_callable=AsyncMock,
        return_value=CascadeResult(
            text="hello world",
            successful_model="opencode/big-pickle",
            successful_provider="opencode-free",
        ),
    )
    def test_main_default(self, mock_cascade, capsys):
        with patch("sys.argv", ["cascade_run", "test prompt"]):
            main()
        captured = capsys.readouterr()
        assert "hello world" in captured.out
        assert "opencode-free" in captured.out

    @patch(
        "agentpipe.cascade_run.cascade",
        new_callable=AsyncMock,
        return_value=CascadeResult(
            text="json result",
            successful_model="opencode/big-pickle",
            successful_provider="opencode-free",
        ),
    )
    def test_main_json_output(self, mock_cascade, capsys):
        with patch("sys.argv", ["cascade_run", "--json", "test prompt"]):
            main()
        captured = capsys.readouterr()
        assert '"text": "json result"' in captured.out

    @patch(
        "agentpipe.cascade_run.cascade",
        new_callable=AsyncMock,
        return_value=CascadeResult(
            text="from custom models",
            successful_model="model-a",
            successful_provider="opencode-free",
        ),
    )
    def test_main_custom_models(self, mock_cascade, capsys):
        with patch("sys.argv", ["cascade_run", "--models", "model-a,model-b", "test"]):
            main()
        mock_cascade.assert_called_once()
        call_kwargs = mock_cascade.call_args
        assert call_kwargs[1]["models"] == ["model-a", "model-b"]

    @patch(
        "agentpipe.cascade_run.cascade",
        new_callable=AsyncMock,
        return_value=CascadeResult(text="free", successful_model="m", successful_provider="p"),
    )
    def test_main_free_only(self, mock_cascade, capsys):
        with patch("sys.argv", ["cascade_run", "--free-only", "test"]):
            main()
        assert mock_cascade.call_args[1]["profile"] == "free-only"

    @patch(
        "agentpipe.cascade_run.cascade",
        new_callable=AsyncMock,
        return_value=CascadeResult(text="capped", successful_model="m", successful_provider="p"),
    )
    def test_main_max_tier(self, mock_cascade, capsys):
        with patch("sys.argv", ["cascade_run", "--max-tier", "cheap", "test"]):
            main()
        assert mock_cascade.call_args[1]["max_tier"] == ModelTier.CHEAP

    @patch(
        "agentpipe.cascade_run.cascade",
        new_callable=AsyncMock,
        return_value=CascadeResult(text="ok", successful_model="m", successful_provider="p"),
    )
    def test_main_max_cost(self, mock_cascade, capsys):
        with patch("sys.argv", ["cascade_run", "--max-cost", "0.50", "test"]):
            main()
        assert mock_cascade.call_args[1]["max_cost_usd"] == 0.50
