#!/usr/bin/env bash
# Record a resolved wayfinder ticket: close it and add its line to the map's "Decisions so far".
# Usage: scripts/record-resolution.sh <ticket> "<one-line gist>" [research-doc-url]
# Env: MAP=<map issue number, default 1>, DRY_RUN=1 to print the new map body instead of pushing it.
set -euo pipefail

ticket=${1:?ticket number}
gist=${2:?one-line gist}
detail=${3:-}
map=${MAP:-1}

[ "$(gh issue view "$ticket" --json comments --jq '.comments | length')" -gt 0 ] ||
    { echo "ticket #$ticket has no resolution comment yet" >&2; exit 1; }

title=$(gh issue view "$ticket" --json title --jq .title)
url=$(gh issue view "$ticket" --json url --jq .url)
line="- [$title]($url): $gist"
[ -n "$detail" ] && line="$line Details: [research notes]($detail)."

body=$(gh issue view "$map" --json body --jq .body)
grep -qF "($url)" <<<"$body" && { echo "ticket #$ticket is already on the map" >&2; exit 1; }

# insert after the last line of "Decisions so far", before the blank line that precedes the next heading
new=$(awk -v l="$line" '
    { lines[NR] = $0 }
    /^## Not yet specified/ { stop = NR }
    END {
        last = stop - 1
        while (last > 0 && lines[last] ~ /^[[:space:]]*$/) last--
        for (i = 1; i <= NR; i++) { print lines[i]; if (i == last) print l }
    }' <<<"$body")

if [ -n "${DRY_RUN:-}" ]; then printf '%s\n' "$new"; exit 0; fi

gh issue close "$ticket" --reason completed >/dev/null
gh issue edit "$map" --body "$new" >/dev/null
gh issue view "$map" --json body --jq .body | grep -qF "($url)" ||
    { echo "map update did not take" >&2; exit 1; }
echo "recorded #$ticket on map #$map"
