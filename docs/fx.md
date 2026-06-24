# FX Rate Semantics

DinarLedger uses a **consistent rate convention** across all FX operations.
This document explains the rate model, conversion direction, cross-rate
derivation, and month-end revaluation workflow.

---

## Rate Convention

An `FXRate` is expressed as:

```
1 unit of base = rate units of quote
```

For example, `FXRate(base="KWD", quote="USD", rate=3.26)` means
1 KWD = 3.26 USD.

This convention applies everywhere:

- `FXRate.rate` — the multiplier
- `convert()` — always multiplies `amount × rate`
- `cross_rate()` — multiplies (or inverts and multiplies) rates

---

## Conversion Direction

`convert(money, target_currency, rate)` computes:

```python
result = money.amount × rate
```

The caller is responsible for passing the correct rate direction.  To
convert 100 USD → KWD using the KWD/USD quote above, you need the inverse:

```python
kwd_usd = FXRate("KWD", "USD", Decimal("3.26"), date.today())
usd_kwd = kwd_usd.invert()          # rate ≈ 0.306748
kwd_amount = convert(usd_amount, "KWD", usd_kwd.rate)
```

### Inversion

`FXRate.invert()` swaps base/quote and takes the reciprocal, quantised to
6 decimal places using `ROUND_HALF_UP`:

```python
inverted_rate = (1 / self.rate).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
```

---

## Cross Rate Derivation

`cross_rate(rate1, rate2)` derives a rate between two currencies that share
a common leg.  Four pairings are checked:

| Pairing | Derivation |
|---------|-----------|
| `rate1.base == rate2.quote` | `rate2.rate × rate1.rate` |
| `rate1.quote == rate2.base` | `rate1.rate × rate2.rate` |
| `rate1.base == rate2.base` | invert rate2, then `inv.rate × rate1.rate` |
| `rate1.quote == rate2.quote` | invert rate1, then `inv.rate × rate2.rate` |

If no common currency exists, `ValueError` is raised.

**Example:** Derive EUR/KWD from EUR/USD and KWD/USD:

```python
eur_usd = FXRate("EUR", "USD", Decimal("1.08"), date.today())
kwd_usd = FXRate("KWD", "USD", Decimal("3.26"), date.today())
# rate1.base (EUR) ≠ rate2.base (KWD), but rate1.quote == rate2.quote (USD)
cross = cross_rate(eur_usd, kwd_usd)   # EUR/KWD
```

The function inverts `eur_usd` (getting USD/EUR) and multiplies by
`kwd_usd.rate`.

---

## Month-End Revaluation Workflow

At each reporting date, foreign-currency receivables must be revalued at
the closing rate.  The `fx.revaluation` module provides:

### `unrealized_gain(invoice, current_rate, original_rate)`

Computes the base-currency difference between the invoice valued at the
original rate vs. the current (closing) rate:

```python
original_base = invoice_amount / original_rate
current_base  = invoice_amount / current_rate
gain = current_base - original_base
```

- **Positive** → unrealised gain (receivable appreciated in base terms)
- **Negative** → unrealised loss

### `revalue_ar(invoices, rates, base_currency)`

Batch-revalues a list of invoices:

1. Skip invoices already in `base_currency`.
2. Skip invoices whose currency has no entry in `rates`.
3. For each eligible invoice, call `unrealized_gain()`.
4. Return `[(invoice_id, gain_amount), ...]`.

### Typical Month-End Process

```python
from decimal import Decimal
from dinarledger.fx.revaluation import revalue_ar

closing_rates = {"EUR": Decimal("1.07"), "KWD": Decimal("3.28")}
adjustments = revalue_ar(open_invoices, closing_rates, base_currency="USD")

for invoice_id, gain in adjustments:
    if gain.is_negative():
        print(f"{invoice_id}: unrealised loss of {abs(gain)}")
    else:
        print(f"{invoice_id}: unrealised gain of {gain}")
```

---

## Rounding

All FX conversions quantise to 2 decimal places with `ROUND_HALF_UP`.
Cross rates and inversions quantise to 6 decimal places (`0.000001`) to
preserve precision through chain computations before the final conversion
step reduces to 2 places.
