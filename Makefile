
NAME = udi-virtual-pg3x
ENTRY = udi-virtual-pg3x.py
XML_FILES = profile/*/*.xml

.PHONY: all check clean format fulltest install install-eisy lint test coverage coverage-html coverage-report zip sync-version

all: lint test

# sudo apt-get install libxml2-utils libxml2-dev
check:
	echo ${XML_FILES}
	xmllint --noout ${XML_FILES}

install:
	uv sync --dev --group lint

install-eisy:
	uv sync --dev

lint:
	uv run ruff check .

format:
	uv run ruff format .

clean:
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	rm -rf .coverage


zip:
	@test -f zip_exclude.lst || (echo "zip_exclude.lst missing" && exit 1)
	zip -x@zip_exclude.lst -r ${NAME}.zip *

test:
	uv run pytest -n auto

coverage:
	uv run pytest -n auto --cov=nodes --cov=utils --cov-report=term-missing

coverage-html:
	uv run pytest -n auto --cov=nodes --cov=utils --cov-report=html --cov-report=term-missing
	@echo ""
	@echo "Coverage report generated! Open htmlcov/index.html in your browser."

coverage-report: coverage-html
	open htmlcov/index.html

fulltest:
	uv run pre-commit run --all-files

sync-version:
	uv run python scripts/sync_version.py --entry $(ENTRY)
