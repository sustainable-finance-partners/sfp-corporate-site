#!/usr/bin/env bash
# wait_for_pages_deploy.sh - wait for the Cloudflare Pages deployment of a commit.
#
# Usage: GH_TOKEN=... bash .github/scripts/wait_for_pages_deploy.sh <owner/repo> <sha> [timeout_s]
#
# The Cloudflare Pages GitHub app posts a check run on the commit it built
# ("Cloudflare Pages", app slug cloudflare-workers-and-pages), for PR previews
# and for production alike; its summary carries the deployment's own URL
# (https://<id>.<project>.pages.dev). This polls the newest such check run until
# it completes, then prints that URL on stdout. Exits 1 when the deployment
# failed or no completed check run appears in time. Needs gh only.
set -uo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: $0 <owner/repo> <sha> [timeout_s]" >&2
  exit 2
fi

repo="$1"
sha="$2"
timeout_s="${3:-1200}"
interval_s=20
deadline=$(($(date +%s) + timeout_s))
query='[.check_runs[] | select(.app.slug == "cloudflare-workers-and-pages")]
  | sort_by(.started_at) | last // empty
  | "\(.status)\t\(.conclusion // "")\t\((.output.summary // "") | gsub("[\r\n\t]"; " "))"'

while :; do
  row=$(gh api "repos/$repo/commits/$sha/check-runs?per_page=100" --jq "$query" 2>/dev/null) || row=""
  if [[ -n "$row" ]]; then
    IFS=$'\t' read -r status conclusion summary <<< "$row"
    if [[ "$status" == "completed" ]]; then
      if [[ "$conclusion" != "success" ]]; then
        echo "FAIL: the Cloudflare Pages deployment of $sha concluded '$conclusion'; see its build log." >&2
        echo "      A build whose output directory (site) is absent from the tree fails this way." >&2
        exit 1
      fi
      url=$(grep -oE "https://[0-9a-f]+\.[a-z0-9-]+\.pages\.dev" <<< "$summary" | head -n 1)
      if [[ -z "$url" ]]; then
        echo "FAIL: the Cloudflare Pages check run on $sha completed without a deployment URL." >&2
        exit 1
      fi
      echo "$url"
      exit 0
    fi
  fi
  if [[ $(date +%s) -ge $deadline ]]; then
    echo "FAIL: no completed Cloudflare Pages check run on $sha within ${timeout_s}s." >&2
    exit 1
  fi
  sleep "$interval_s"
done
