.PHONY: test preflight zip clean

test:
	pytest --cov=dinarledger --cov-report=term-missing --cov-fail-under=80

preflight:
	pytest --co -q
	flake8 src/ tests/

zip:
	python -c "import subprocess; subprocess.run(['git', 'archive', '--format=zip', '--prefix=DinarLedger/', 'HEAD', '-o', 'DinarLedger.zip'])"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov
