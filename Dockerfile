FROM python:3.12.7-slim-bookworm

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

COPY pyproject.toml pytest.ini Makefile ./
COPY src/ src/
COPY tests/ tests/

RUN pip install --no-cache-dir -e ".[dev]"

CMD ["pytest"]
