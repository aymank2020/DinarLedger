# Contributing to DinarLedger

Thank you for your interest!  This guide covers setting up a development
environment, running the test suite, and the conventions we follow.

---

## Development Environment

1. **Python 3.11+** (3.11 and 3.12 are tested in CI).

2. Clone and create a virtual environment:

   ```bash
   git clone https://github.com/aymank2020/DinarLedger.git
   cd DinarLedger
   python -m venv .venv
   source .venv/bin/activate
   ```

3. Install in editable mode with dev dependencies:

   ```bash
   pip install -e ".[dev]"
   ```

4. Install pre-commit hooks:

   ```bash
   pre-commit install
   ```

---

## Running Tests

### Unit tests

```bash
pytest tests/ -v
```

### With coverage

```bash
pytest --cov=dinarledger --cov-report=term-missing
```

### Property-based tests (Hypothesis)

```bash
pytest tests/properties/ -v
```

### Markers

- `@pytest.mark.slow` — long-running tests (skip with `-m "not slow"`)
- `@pytest.mark.integration` — tests that hit storage backends

### Type checking

```bash
mypy src/dinarledger
```

### Linting

```bash
ruff check src/dinarledger
```

---

## Code Style

- **Formatter:** Black (line length 88)
- **Linter:** Ruff
- **Type hints:** All public functions must have complete type annotations.
- **Imports:** Use `from __future__ import annotations` in every module.
- **Docstrings:** Google/numpy-style for all public classes and functions.
- **Decimal precision:** Never use `float` for money — always `decimal.Decimal`.
- **Immutability:** Domain types must be frozen dataclasses.

---

## Commit Messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) spec:

```
feat(billing): add credit note support
fix(fx): correct cross-rate derivation for same-base pairs
docs(readme): add CLI usage section
test(revenue): add property tests for residual allocation
refactor(storage): extract snapshot logic from UnitOfWork
```

---

## Pull Request Process

1. **Fork** the repository and create a feature branch from `main`.
2. **Write tests** for any new functionality — aim for > 90% coverage on
   changed files.
3. **Run the full suite** locally: `pytest --cov`, `mypy`, `ruff check`.
4. **Update documentation** if your change affects public APIs or behaviour.
5. **Open a PR** with a clear description of the change and the motivation.
6. A maintainer will review; address feedback and push fixes.
7. Once approved and CI passes, a maintainer will merge.

---

## Reporting Issues

- Use [GitHub Issues](https://github.com/aymank2020/DinarLedger/issues).
- Include Python version, OS, and a minimal reproduction.
- For security vulnerabilities, email ayman.dev@proton.me directly.
