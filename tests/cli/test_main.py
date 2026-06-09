"""Tests for the CLI main entry point and argument parsing."""

from __future__ import annotations

import subprocess
import sys

import pytest

from dinarledger.cli.main import build_parser, main


class TestHelpOutput:
    """Verify that --help works for all commands."""

    def test_main_help(self, capsys):
        """Top-level --help should exit cleanly."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "dinarledger" in captured.out.lower() or "usage" in captured.out.lower()

    def test_customer_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["customer", "--help"])
        assert exc_info.value.code == 0

    def test_plan_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["plan", "--help"])
        assert exc_info.value.code == 0

    def test_subscription_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["subscription", "--help"])
        assert exc_info.value.code == 0

    def test_invoice_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["invoice", "--help"])
        assert exc_info.value.code == 0

    def test_payment_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["payment", "--help"])
        assert exc_info.value.code == 0

    def test_revenue_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["revenue", "--help"])
        assert exc_info.value.code == 0

    def test_fx_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["fx", "--help"])
        assert exc_info.value.code == 0

    def test_report_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["report", "--help"])
        assert exc_info.value.code == 0


class TestUnknownCommand:
    """Unknown commands should produce an error."""

    def test_unknown_command_returns_nonzero(self):
        """An unknown subcommand should return a non-zero exit code."""
        # argparse will raise SystemExit for unknown commands
        with pytest.raises(SystemExit) as exc_info:
            main(["nonexistent"])
        assert exc_info.value.code != 0

    def test_no_command_returns_zero(self, capsys):
        """No command at all should print help and return 0."""
        result = main([])
        assert result == 0


class TestPythonModule:
    """Test ``python -m dinarledger`` entry point."""

    def test_module_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "dinarledger", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "dinarledger" in result.stdout.lower() or "usage" in result.stdout.lower()
