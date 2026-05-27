# Changelog

All notable changes to DinarLedger are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.9.0] — 2026-05-27

First public alpha release. Stabilises the public API across the core,
billing, revenue, payment, FX, tax, and reporting modules.

### Added

- Subscription lifecycle management: trial → active, cancel (immediate
  or end-of-period), reactivate, expire.
- Per-seat plan pricing with mid-cycle add/remove proration.
- Invoice generation with subscription charges, seat overage, optional
  setup fee, and per-line tax.
- Multi-currency support with FX rate management (`FXRate`),
  `convert()`, cross-rate derivation, and AR revaluation.
- IFRS 15 revenue recognition: performance obligations, SSP-based
  allocation (proportional and residual), ratable and point-in-time
  recognition, and deferred revenue calculation.
- Monthly deferred revenue roll-forward schedule with stub-period
  handling.
- Payment allocation strategies (`oldest_first`, `highest_first`) and
  bank reconciliation with tolerance matching.
- Tax engine with per-item rounding plus customer-level and
  jurisdiction-based exemptions.
- Customer credit-limit checks and history-based limit recalculation.
- AR aging report, MRR breakdown report, and deferred revenue waterfall.
- Decimal arithmetic throughout via the `Money` value object with
  banker's rounding by default.
- Test suite covering core money/period/proration arithmetic plus the
  invoice generation, subscription lifecycle, and revenue recognition
  paths.

### Notes

- Dependency footprint kept minimal — the runtime requires no
  third-party packages; the test extras pull in `pytest`, `pytest-cov`,
  and `hypothesis`.
- Targets Python 3.11 and 3.12.

[Unreleased]: https://github.com/aymank2020/DinarLedger/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/aymank2020/DinarLedger/releases/tag/v0.9.0
