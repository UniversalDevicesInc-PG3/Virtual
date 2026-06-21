#!/usr/bin/env bash
# Run the test suite with the Pipenv virtualenv Python (3.11), not system Python.
# Used by pre-commit pre-push so git hooks match `pipenv run pytest`.
#
# Emacs/Magit on macOS often invokes git hooks with a minimal PATH and may inherit
# VIRTUAL_ENV from the editor session, which can send pytest to the wrong Python.

set -u

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT" || exit

# Match a typical login-shell PATH so pipenv/pyenv work outside Terminal.
export PATH="${HOME}/.local/bin:/usr/local/bin:/opt/homebrew/bin:${HOME}/.pyenv/shims:${HOME}/.pyenv/bin:${PATH}"

# Avoid picking up the wrong interpreter from an active editor/IDE venv.
unset VIRTUAL_ENV
unset PIPENV_ACTIVE
export PIPENV_IGNORE_VIRTUALENVS=1

if [ "${RUN_TESTS_DEBUG:-}" = "1" ]; then
  echo "run-tests: ROOT=${ROOT}" >&2
  echo "run-tests: PATH=${PATH}" >&2
fi

python_has_pytest() {
  "${1}" -m pytest --version >/dev/null 2>&1
}

resolve_python() {
  local candidates=()

  if [ -x "${ROOT}/.venv/bin/python" ]; then
    candidates+=("${ROOT}/.venv/bin/python")
  fi

  if command -v pipenv >/dev/null 2>&1; then
    local venv
    venv="$(pipenv --venv 2>/dev/null || true)"
    if [ -n "${venv}" ] && [ -x "${venv}/bin/python" ]; then
      candidates+=("${venv}/bin/python")
    fi
  fi

  local py
  for py in "${candidates[@]}"; do
    if python_has_pytest "${py}"; then
      echo "${py}"
      return 0
    fi
  done

  return 1
}

if ! PYTHON="$(resolve_python)"; then
  echo "Could not find a Python with pytest installed." >&2
  echo "From ${ROOT}, run: pipenv install --dev" >&2
  exit 1
fi

if [ "${RUN_TESTS_DEBUG:-}" = "1" ]; then
  echo "run-tests: PYTHON=${PYTHON}" >&2
  "${PYTHON}" --version >&2
fi

"${PYTHON}" -m pytest "$@"
status=$?

# pytest exit code 5 = no tests collected (treat as success for empty suites)
if [ "$status" -eq 5 ]; then
  exit 0
fi

exit "$status"
