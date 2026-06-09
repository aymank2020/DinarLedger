"""Tests for the CLI output formatters."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest

from dinarledger.cli.formatters import (
    format_csv,
    format_date,
    format_json,
    format_money,
    format_table,
    output,
    resolve_format,
)
from dinarledger.core.money import Money


class TestFormatMoney:
    def test_positive(self):
        m = Money(amount=Decimal("1234.56"), currency="KWD")
        assert format_money(m) == "1,234.56 KWD"

    def test_zero(self):
        m = Money(amount=Decimal("0"), currency="USD")
        assert format_money(m) == "0.00 USD"

    def test_negative(self):
        m = Money(amount=Decimal("-50.00"), currency="EUR")
        assert format_money(m) == "-50.00 EUR"

    def test_large_amount(self):
        m = Money(amount=Decimal("1000000.00"), currency="USD")
        assert format_money(m) == "1,000,000.00 USD"


class TestFormatDate:
    def test_iso_format(self):
        d = date(2025, 3, 15)
        assert format_date(d) == "2025-03-15"


class TestFormatTable:
    def test_basic_table(self):
        headers = ["Name", "Amount"]
        rows = [["Alice", "100"], ["Bob", "200"]]
        result = format_table(headers, rows)
        assert "Name" in result
        assert "Alice" in result
        assert "Bob" in result
        # Should contain separator lines
        assert "+" in result
        assert "|" in result

    def test_empty_rows(self):
        headers = ["A", "B"]
        rows = []
        result = format_table(headers, rows)
        assert "A" in result
        assert "B" in result

    def test_money_cells(self):
        headers = ["Item", "Price"]
        rows = [["Widget", Money(amount=Decimal("9.99"), currency="USD")]]
        result = format_table(headers, rows)
        assert "9.99 USD" in result

    def test_date_cells(self):
        headers = ["Date"]
        rows = [[date(2025, 1, 1)]]
        result = format_table(headers, rows)
        assert "2025-01-01" in result


class TestFormatJson:
    def test_basic_dict(self):
        data = {"key": "value", "number": 42}
        result = format_json(data)
        parsed = json.loads(result)
        assert parsed["key"] == "value"
        assert parsed["number"] == 42

    def test_money_serialization(self):
        data = {"price": Money(amount=Decimal("10.50"), currency="KWD")}
        result = format_json(data)
        parsed = json.loads(result)
        assert parsed["price"]["amount"] == "10.50"
        assert parsed["price"]["currency"] == "KWD"

    def test_date_serialization(self):
        data = {"date": date(2025, 6, 1)}
        result = format_json(data)
        parsed = json.loads(result)
        assert parsed["date"] == "2025-06-01"


class TestFormatCsv:
    def test_basic_csv(self):
        headers = ["Name", "Amount"]
        rows = [["Alice", "100"], ["Bob", "200"]]
        result = format_csv(headers, rows)
        lines = result.split("\n")
        assert lines[0] == "Name,Amount"
        assert "Alice,100" in lines[1]

    def test_money_in_csv(self):
        headers = ["Price"]
        rows = [[Money(amount=Decimal("5.00"), currency="USD")]]
        result = format_csv(headers, rows)
        assert "5.00 USD" in result


class TestResolveFormat:
    def test_cli_format_takes_priority(self):
        assert resolve_format("json") == "json"

    def test_default_is_table(self):
        assert resolve_format() == "table"

    def test_env_var(self, monkeypatch):
        monkeypatch.setenv("OUTPUT_FORMAT", "csv")
        assert resolve_format() == "csv"


class TestOutput:
    def test_json_output(self):
        data = {"a": 1}
        result = output(data, fmt="json")
        assert json.loads(result)["a"] == 1

    def test_table_output(self):
        result = output(
            data=None,
            headers=["H1"], rows=[["v1"]], fmt="table",
        )
        assert "H1" in result
        assert "v1" in result

    def test_csv_output(self):
        result = output(
            data=None,
            headers=["H1", "H2"], rows=[["v1", "v2"]], fmt="csv",
        )
        assert "H1,H2" in result
        assert "v1,v2" in result
