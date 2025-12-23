#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/release.sh <version> [options]

Examples:
  scripts/release.sh 0.4.0
  scripts/release.sh v0.4.0 --lock --commit --tag

Options:
  --allow-dirty   Allow running with a dirty git worktree
  --lock          Run `uv lock` after bumping version refs
  --commit        Create a release prep commit
  --tag           Create an annotated tag (vX.Y.Z)
  --push          Push HEAD and tag to origin
  -m, --message   Commit message (default: "Prepare vX.Y.Z release")
  -h, --help      Show this help
EOF
}

log() { echo "[release] $*"; }
die() { echo "[release] ERROR: $*" >&2; exit 1; }

VERSION=""
ALLOW_DIRTY=0
DO_LOCK=0
DO_COMMIT=0
DO_TAG=0
DO_PUSH=0
COMMIT_MSG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --allow-dirty) ALLOW_DIRTY=1; shift ;;
    --lock) DO_LOCK=1; shift ;;
    --commit) DO_COMMIT=1; shift ;;
    --tag) DO_TAG=1; shift ;;
    --push) DO_PUSH=1; shift ;;
    -m|--message) COMMIT_MSG="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *)
      if [[ -z "${VERSION}" ]]; then
        VERSION="$1"; shift
      else
        die "Unknown arg: $1"
      fi
      ;;
  esac
done

[[ -n "${VERSION}" ]] || { usage; exit 1; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if ! command -v python3 >/dev/null 2>&1; then
  die "python3 is required"
fi
if ! command -v git >/dev/null 2>&1; then
  die "git is required"
fi

TAG="${VERSION}"
if [[ "${VERSION}" == v* ]]; then
  VERSION="${VERSION#v}"
else
  TAG="v${VERSION}"
fi

if [[ ! "${VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+([-.][0-9A-Za-z.-]+)?$ ]]; then
  die "Version must be semver-like, got: ${VERSION}"
fi

if [[ "${ALLOW_DIRTY}" -eq 0 ]]; then
  if [[ -n "$(git status --porcelain)" ]]; then
    die "Working tree is dirty. Commit/stash or re-run with --allow-dirty."
  fi
fi

replace_in_file() {
  local file="$1"
  local pattern="$2"
  local replacement="$3"
  python3 - "$file" "$pattern" "$replacement" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
pattern = sys.argv[2]
replacement = sys.argv[3]

text = path.read_text()
new_text, n = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
if n == 0:
    raise SystemExit(f"No match for pattern in {path}")
path.write_text(new_text)
PY
}

log "Bumping version to ${VERSION} (${TAG})"
replace_in_file "pyproject.toml" '^version\s*=\s*".*"' "version = \"${VERSION}\""
replace_in_file "scripts/install.sh" '^REF_DEFAULT="v[^"]+"' "REF_DEFAULT=\"${TAG}\""
replace_in_file "README.md" '--ref v[0-9]+\.[0-9]+\.[0-9]+([-.][0-9A-Za-z.-]+)?' "--ref ${TAG}"

if [[ "${DO_LOCK}" -eq 1 ]]; then
  if ! command -v uv >/dev/null 2>&1; then
    die "uv not found; install uv or run without --lock"
  fi
  log "Updating uv.lock"
  uv lock
fi

if [[ "${DO_COMMIT}" -eq 1 ]]; then
  git add pyproject.toml scripts/install.sh README.md
  if [[ "${DO_LOCK}" -eq 1 && -f uv.lock ]]; then
    git add uv.lock
  fi
  if [[ -z "${COMMIT_MSG}" ]]; then
    COMMIT_MSG="Prepare ${TAG} release"
  fi
  git commit -m "${COMMIT_MSG}"
fi

if [[ "${DO_TAG}" -eq 1 ]]; then
  if git rev-parse -q --verify "refs/tags/${TAG}" >/dev/null; then
    die "Tag ${TAG} already exists"
  fi
  git tag -a "${TAG}" -m "Release ${TAG}"
fi

if [[ "${DO_PUSH}" -eq 1 ]]; then
  git push origin HEAD
  if [[ "${DO_TAG}" -eq 1 ]]; then
    git push origin "${TAG}"
  fi
fi

log "Done. Review changes with: git status -sb && git diff"
