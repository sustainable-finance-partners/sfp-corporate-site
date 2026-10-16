#!/usr/bin/env bash
# published_tree_probe.sh - the host serves site/ and nothing else.
#
# Usage (from the repository root, which git ls-files needs):
#   bash .github/scripts/published_tree_probe.sh <base_url> [<base_url> ...]
#
# Cloudflare Pages publishes site/ (the project's build output directory). For
# each base URL this probe asserts, without following redirects:
#   404  /CLAUDE.md, /README.md, /skills/setup.md (ruled by name, whether or not
#        this repository carries them) and every tracked file outside site/
#        (README.md, .gitattributes, .github/*), at its repository path;
#   404  one path that exists nowhere. Without site/404.html, Cloudflare Pages
#        treats the site as a single-page app and answers 200 with index.html for
#        every unknown path, so every check above would read 200;
#   200  every tracked file under site/ at its served path (x.html at /x,
#        index.html at /), except 404.html and the Pages control files
#        (_headers, _redirects, _routes.json, _worker.js), which Pages does not
#        serve as files.
# Prints one line per probe; exits 0 only when every probe matches.
set -uo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <base_url> [<base_url> ...]" >&2
  exit 2
fi

UA="Mozilla/5.0 (compatible; agent)"
RULED_ABSENT=(CLAUDE.md README.md skills/setup.md)
UNKNOWN_PATH="__published_tree_probe__/no-such-path"

mapfile -t outside < <(git ls-files | grep -v '^site/')
mapfile -t inside < <(git ls-files site | sed 's#^site/##')

if [[ ${#inside[@]} -eq 0 ]]; then
  echo "FAIL: git ls-files lists nothing under site/; the published tree must be site/"
  exit 1
fi

status_of() {
  local code
  code=$(curl -sS -o /dev/null -w '%{http_code}' -A "$UA" --max-time 30 "$1" 2>/dev/null) || true
  echo "${code:-000}"
}

served_path() {
  case "$1" in
    index.html) echo "" ;;
    */index.html) echo "${1%index.html}" ;;
    *.html) echo "${1%.html}" ;;
    *) echo "$1" ;;
  esac
}

failed=0
checked=0
expect() {
  local url="$1" want="$2" got
  got=$(status_of "$url")
  checked=$((checked + 1))
  if [[ "$got" == "$want" ]]; then
    echo "PASS $got $url"
  else
    echo "FAIL $got (expected $want) $url"
    failed=$((failed + 1))
  fi
}

for base in "$@"; do
  base="${base%/}"
  echo "--- $base"
  declare -A seen=()
  for p in "${RULED_ABSENT[@]}" "${outside[@]}" "$UNKNOWN_PATH"; do
    [[ -n "${seen[$p]:-}" ]] && continue
    seen[$p]=1
    expect "$base/$p" 404
  done
  unset seen
  for f in "${inside[@]}"; do
    case "$f" in
      404.html | _headers | _redirects | _routes.json | _worker.js) continue ;;
    esac
    expect "$base/$(served_path "$f")" 200
  done
done

echo "checked=$checked failed=$failed"
if [[ $failed -ne 0 ]]; then
  echo "FAIL: the host does not serve exactly site/ (see the FAIL lines above)"
  exit 1
fi
echo "PASS: repository files outside site/ answer 404; every file in site/ answers 200"
