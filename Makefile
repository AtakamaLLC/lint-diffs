.PHONY: lint test
	
lint:
	pylint lint_diffs test/test_*.py
	flake8 lint_diffs test/test_*.py

test:
	pytest -v --cov=lint_diffs -n=2 .
