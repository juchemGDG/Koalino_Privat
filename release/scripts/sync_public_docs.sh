#!/usr/bin/env bash
# Kopiert Dokumente aus dem Quell-Repo in den Branch des oeffentlichen Release-Repos.
#
# Hintergrund: Koalino verlinkt aus dem Ueber-Dialog auf
# https://github.com/<RELEASE_REPO>/blob/main/docs/datenschutz.md. Diese Datei
# soll dort immer dem Stand des gerade veroeffentlichten Release entsprechen.
# Es wird nur geschrieben, wenn sich der Inhalt geaendert hat (kein leerer Commit).
#
# Aufruf:  sync_public_docs.sh docs/datenschutz.md [weitere Dateien ...]
# Umgebung: RELEASE_REPO (z. B. juchemGDG/Koalino), GH_TOKEN mit Schreibrecht
#           auf dessen Inhalt; optional DOCS_BRANCH (Standard: main) und
#           GITHUB_REF_NAME (Tag, nur fuer die Commit-Nachricht).
set -euo pipefail

REPO="${RELEASE_REPO:?RELEASE_REPO nicht gesetzt}"
BRANCH="${DOCS_BRANCH:-main}"
TAG="${GITHUB_REF_NAME:-}"
[ $# -gt 0 ] || { echo "Keine Dateien angegeben." >&2; exit 1; }

for file in "$@"; do
  [ -f "$file" ] || { echo "Datei fehlt: $file" >&2; exit 1; }
  api="repos/$REPO/contents/$file"
  new="$(base64 -w0 "$file")"

  # Vorhandene Datei (falls es sie gibt): Inhalt zum Vergleichen, SHA zum Ueberschreiben.
  remote="$(gh api "$api?ref=$BRANCH" 2>/dev/null || true)"
  sha="$(jq -r '.sha // empty' <<<"$remote")"
  old="$(jq -r '.content // empty' <<<"$remote" | tr -d '\n')"

  if [ -n "$old" ] && [ "$old" = "$new" ]; then
    echo "$file in $REPO ist aktuell."
    continue
  fi

  args=(-X PUT "$api" -f message="docs: $file aus Koalino ${TAG:-} uebernommen"
        -f content="$new" -f branch="$BRANCH")
  [ -n "$sha" ] && args+=(-f sha="$sha")
  gh api "${args[@]}" --jq '"\(.content.path) -> \(.commit.sha[0:7])"'
done
