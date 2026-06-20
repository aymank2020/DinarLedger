"""Smoke tests for the example scripts.

Each test imports and executes an example's ``main()`` function (or the
module-level code) to verify it runs without raising an exception.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from pathlib import Path

import pytest


EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"


def _load_example(module_name: str, file_path: Path) -> ModuleType:
    """Import an example module by file path."""
    import sys

    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    assert spec is not None, f"Could not create spec for {file_path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


class TestQuickstart:
    def test_runs_without_error(self) -> None:
        module = _load_example(
            "example_01_quickstart",
            EXAMPLES_DIR / "01_quickstart.py",
        )
        module.main()

    def test_produces_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        module = _load_example(
            "example_01_quickstart_b",
            EXAMPLES_DIR / "01_quickstart.py",
        )
        module.main()
        out = capsys.readouterr().out
        assert "QUICKSTART SUMMARY" in out
        assert "PAID IN FULL" in out


class TestSaasCompany:
    def test_runs_without_error(self) -> None:
        module = _load_example(
            "example_02_saas",
            EXAMPLES_DIR / "02_saas_company.py",
        )
        module.run_simulation()

    def test_produces_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        module = _load_example(
            "example_02_saas_b",
            EXAMPLES_DIR / "02_saas_company.py",
        )
        module.run_simulation()
        out = capsys.readouterr().out
        assert "YEAR 1 SUMMARY" in out


class TestMultiCurrency:
    def test_runs_without_error(self) -> None:
        module = _load_example(
            "example_03_multi",
            EXAMPLES_DIR / "03_multi_currency.py",
        )
        module.main()

    def test_produces_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        module = _load_example(
            "example_03_multi_b",
            EXAMPLES_DIR / "03_multi_currency.py",
        )
        module.main()
        out = capsys.readouterr().out
        assert "MULTI-CURRENCY SUMMARY" in out


class TestIFRS15Bundle:
    def test_runs_without_error(self) -> None:
        module = _load_example(
            "example_04_ifrs15",
            EXAMPLES_DIR / "04_ifrs15_bundle.py",
        )
        module.main()

    def test_produces_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        module = _load_example(
            "example_04_ifrs15_b",
            EXAMPLES_DIR / "04_ifrs15_bundle.py",
        )
        module.main()
        out = capsys.readouterr().out
        assert "PROPORTIONAL ALLOCATION" in out


class TestPaymentReconciliation:
    def test_runs_without_error(self) -> None:
        module = _load_example(
            "example_05_recon",
            EXAMPLES_DIR / "05_payment_reconciliation.py",
        )
        module.main()

    def test_produces_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        module = _load_example(
            "example_05_recon_b",
            EXAMPLES_DIR / "05_payment_reconciliation.py",
        )
        module.main()
        out = capsys.readouterr().out
        assert "RECONCILIATION REPORT" in out
