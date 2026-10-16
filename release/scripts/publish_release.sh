#!/usr/bin/env bash
# Veroeffentlicht den Release-Entwurf des aktuellen Tags.
#
# Laeuft erst, wenn alle Plattform-Builds ihre Pakete angehaengt haben - so
# wird nie ein halbfertiges Release oeffentlich sichtbar.
set -euo pipefail

TAG="${GITHUB_REF_NAME:?GITHUB_REF_NAME nicht gesetzt}"
# Releases liegen im oeffentlichen Release-Repo (RELEASE_REPO); der Quellcode
# ist in einem privaten Repo. Ohne RELEASE_REPO wird das eigene Repo benutzt.
REPO="${RELEASE_REPO:-${GITHUB_REPOSITORY:?GITHUB_REPOSITORY nicht gesetzt}}"

echo "Assets am Release $TAG:"
gh release view "$TAG" --repo "$REPO" --json assets \
   --jq '.assets[] | "  \(.name)  \(.size) Bytes"'

# Tags mit Bindestrich (z. B. v1.10.0-beta.1) sind Vorabversionen: als
# "Pre-release" veroeffentlichen und NICHT als neuestes Release markieren.
if [[ "$TAG" == *-* ]]; then
  gh release edit "$TAG" --repo "$REPO" --draft=false --prerelease --latest=false
else
  gh release edit "$TAG" --repo "$REPO" --draft=false --latest
fi
echo "Release $TAG veroeffentlicht."
