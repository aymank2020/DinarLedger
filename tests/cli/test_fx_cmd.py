"""Tests for the FX CLI commands."""

from __future__ import annotations

import json

import pytest

from dinarledger.cli import store
from dinarledger.cli.main import main


@pytest.fixture(autouse=True)
def _reset_store():
    store.reset()
    yield
    store.reset()


class TestFxRates:
    def test_rates_empty(self, capsys):
        result = main(["fx", "rates"])
        assert result == 0
        captured = capsys.readouterr()
        assert "No FX rates" in captured.out

    def test_rates_with_data(self, capsys):
        from datetime import date
        from decimal import Decimal
        from dinarledger.fx.rates import FXRate

        store.fx_rates.append(
            FXRate(base="USD", quote="KWD", rate=Decimal("0.307"), rate_date=date(2025, 1, 1))
        )
        result = main(["fx", "rates"])
        assert result == 0
        captured = capsys.readouterr()
        assert "USD" in captured.out
        assert "KWD" in captured.out


class TestFxConvert:
    def test_convert_usd_to_kwd(self, capsys):
        result = main([
            "fx", "convert",
            "--amount", "100.00",
            "--from", "USD",
            "--to", "KWD",
            "--rate", "0.307",
        ])
        assert result == 0
        captured = capsys.readouterr()
        assert "30.70" in captured.out
        assert "KWD" in captured.out

    def test_convert_json_output(self, capsys):
        result = main([
            "--format", "json",
            "fx", "convert",
            "--amount", "1000.00",
            "--from", "EUR",
            "--to", "USD",
            "--rate", "1.10",
        ])
        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["source"] == "1,000.00 EUR"
        assert data["target"] == "1,100.00 USD"
