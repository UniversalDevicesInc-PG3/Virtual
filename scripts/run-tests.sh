#!/usr/bin/env bash
# Run the test suite with the Pipenv virtualenv Python (3.11), not system Python.
# Used by pre-commit pre-push so git hooks match `pipenv run pytest`.
#
# Emacs/Magit on macOS often invokes git hooks with a minimal PATH and may inherit
# VIRTUAL_ENV from the editor session. Pipenv may then resolve a stale 3.14 venv
# under ~/.local/share/virtualenvs instead of the 3.11 venv under ~/.virtualenvs.

set -u

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT" || exit

PROJECT_NAME="$(basename "${ROOT}")"

# Match a typical login-shell PATH so pipenv/pyenv work outside Terminal.
export PATH="${HOME}/.local/bin:/usr/local/bin:/opt/homebrew/bin:${HOME}/.pyenv/shims:${HOME}/.pyenv/bin:${PATH}"

# Avoid picking up the wrong interpreter from an active editor/IDE venv.
unset VIRTUAL_ENV
unset PIPENV_ACTIVE
export PIPENV_IGNORE_VIRTUALENVS=1

if [ "${RUN_TESTS_DEBUG:-}" = "1" ]; then
  echo "run-tests: ROOT=${ROOT}" >&2
  echo "run-tests: PROJECT_NAME=${PROJECT_NAME}" >&2
  echo "run-tests: PATH=${PATH}" >&2
fi

python_has_pytest() {
  "${1}" -m pytest --version >/dev/null 2>&1
}

python_is_311() {
  "${1}" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 11) else 1)' 2>/dev/null
}

python_is_valid() {
  python_has_pytest "${1}" && python_is_311 "${1}"
}

resolve_python() {
  local candidates=()
  local py seen="|"
  local base dir venv

  if [ -x "${ROOT}/.venv/bin/python" ]; then
    candidates+=("${ROOT}/.venv/bin/python")
  fi

  for base in "${HOME}/.virtualenvs" "${HOME}/.local/share/virtualenvs"; do
    if [ ! -d "${base}" ]; then
      continue
    fi
    for dir in "${base}/${PROJECT_NAME}-"*; do
      if [ -d "${dir}" ] && [ -x "${dir}/bin/python" ]; then
        candidates+=("${dir}/bin/python")
      fi
    done
  done

  if command -v pipenv >/dev/null 2>&1; then
    venv="$(pipenv --venv 2>/dev/null || true)"
    if [ -n "${venv}" ] && [ -x "${venv}/bin/python" ]; then
      candidates+=("${venv}/bin/python")
    fi
  fi

  for py in "${candidates[@]}"; do
    if [[ "${seen}" == *"|${py}|"* ]]; then
      continue
    fi
    seen="${seen}${py}|"

    if [ "${RUN_TESTS_DEBUG:-}" = "1" ]; then
      echo "run-tests: candidate ${py} ($("${py}" --version 2>&1))" >&2
    fi

    if python_is_valid "${py}"; then
      echo "${py}"
      return 0
    fi
  done

  return 1
}

if ! PYTHON="$(resolve_python)"; then
  echo "Could not find Python 3.11 with pytest installed." >&2
  echo "EISY targets Python 3.11; a stale 3.14 pipenv venv may exist under" >&2
  echo "~/.local/share/virtualenvs. From ${ROOT}, run:" >&2
  echo "  pipenv --rm && pipenv install --dev" >&2
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
