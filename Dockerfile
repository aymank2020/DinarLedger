FROM python:3.12.7-slim-bookworm

WORKDIR /app

RUN pip install --no-cache-dir \
    pip==24.0 \
    setuptools==75.1.0 \
    wheel==0.44.0

COPY pyproject.toml pytest.ini Makefile ./
COPY src/ src/
COPY tests/ tests/

RUN pip install --no-cache-dir \
    pytest==9.0.3 \
    pytest-cov==7.1.0 \
    hypothesis==6.153.6 \
    && pip install --no-cache-dir -e .

CMD ["pytest"]
