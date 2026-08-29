# Contributing / release workflow

## Version numbering

**Single source of truth:** `VERSION` in the bootstrap script
(`udi-virtual-pg3x.py`).

After changing `VERSION`, sync mirrors:

```bash
make sync-version
# or
python scripts/sync_version.py --entry udi-virtual-pg3x.py
```

Or bump in one step:

```bash
python scripts/bump_version.py 3.2.0 --entry udi-virtual-pg3x.py
```

### Files updated automatically

| File | Purpose |
|------|---------|
| `profile/version.txt` | ISY/Easy UI profile sync |
| `server.json` → `credits[0].version` | Store manifest |

### Files you edit manually each release

| File | Purpose |
|------|---------|
| Bootstrap `VERSION` | Runtime version passed to `polyglot.start()` |
| `CHANGELOG.md` | Human-readable release notes |

CI (`test/test_profile.py`) fails if bootstrap `VERSION` ≠ `profile/version.txt`.

## Branch naming

Use **`main`** as the default branch. The gitea mirror uses `main`; the UDI store org repo (`Virtual`) may still list `master` as default until an org admin switches it.

**Do not** change controller node addresses (`controller`) on shipped plugins.

## Dev commands

```bash
make install    # uv sync --dev
make lint       # ruff
make test       # pytest
make fulltest   # pre-commit all files
```

## direnv + Emacs (optional, recommended)

Per-machine setup (once):

```bash
mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/direnv"
cp direnv/direnvrc.example "${XDG_CONFIG_HOME:-$HOME/.config}/direnv/direnvrc"
```

Each repo includes a `.envrc` with `layout uv`. After clone on a new machine:

```bash
direnv allow
```

See [`direnv/direnvrc.example`](direnv/direnvrc.example) for the full global helper and install notes.

### EISY / FreeBSD dev note

`.python-version` is pinned to **`3.11`** (any 3.11.x), not a specific patch, so uv can use the system interpreter on EISY (`/usr/local/bin/python3.11`) as well as pyenv on macOS.

**One-time on EISY** (recommended — add to `~/.zshrc`):

```bash
export UV_PYTHON=/usr/local/bin/python3.11
export UV_SYNC_LINT=0    # skip ruff; no FreeBSD wheel
```

After `git pull`, bootstrap each repo:

```bash
cd ~/polyglot/nodeservers/udi-virtual-pg3x
make install-eisy UV_PYTHON="$UV_PYTHON"
direnv allow .
```

## server.json GitHub URLs

| Stage | Org | Repo |
|-------|-----|------|
| Development | `sejgit-udi-plugins` | `udi-virtual-pg3x` |
| Published on UDI store | `UniversalDevicesInc-PG3` | `Virtual` |

Update `docs`, `credits[0].source`, and `credits[0].license` when migrating between orgs.
`sync_version.py` only updates `credits[0].version`, not URLs.
