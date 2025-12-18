
NAME = Virtual
XML_FILES = profile/*/*.xml

.PHONY: all check clean format fulltest install lint test coverage coverage-html coverage-report zip

all: lint test

# sudo apt-get install libxml2-utils libxml2-dev
check:
	echo ${XML_FILES}
	xmllint --noout ${XML_FILES}

install:
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
	zip -x@zip_exclude.lst -r ${NAME}.zip *

test:
	uv run pytest

coverage:
	uv run pytest --cov=nodes --cov=utils --cov-report=term-missing

coverage-html:
	uv run pytest --cov=nodes --cov=utils --cov-report=html --cov-report=term-missing
	@echo ""
	@echo "Coverage report generated! Open htmlcov/index.html in your browser."

coverage-report: coverage-html
	open htmlcov/index.html

fulltest:
	uv run pre-commit run --all-files
