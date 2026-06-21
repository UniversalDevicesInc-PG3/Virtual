#!/usr/bin/env bash
# Run the test suite with the Pipenv virtualenv Python (3.11), not system Python.
# Used by pre-commit pre-push so git hooks match `pipenv run pytest`.

set -u

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

export PATH="${HOME}/.local/bin:/usr/local/bin:/opt/homebrew/bin:${PATH}"

if ! command -v pipenv >/dev/null 2>&1; then
  echo "pipenv not found; install pipenv or run: pipenv run pytest" >&2
  exit 1
fi

VENV="$(pipenv --venv)"
PYTHON="${VENV}/bin/python"

if [ ! -x "$PYTHON" ]; then
  echo "Pipenv venv python not found at ${PYTHON}; run: pipenv install" >&2
  exit 1
fi

"$PYTHON" -m pytest "$@"
status=$?

# pytest exit code 5 = no tests collected (treat as success for empty suites)
if [ "$status" -eq 5 ]; then
  exit 0
fi

exit "$status"
