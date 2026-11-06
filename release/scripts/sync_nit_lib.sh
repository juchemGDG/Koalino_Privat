#!/usr/bin/env bash
# Übernimmt die MicroPython-Bibliotheken (nitbw_*.py) aus dem Repository
# NIT_Bibliotheken in Koalino.
#
#   bash release/scripts/sync_nit_lib.sh ../NIT_Bibliotheken
#
# Koalino liefert die Bibliotheken mit, damit der Deploy (iPad-Programmierung,
# Bibliotheks-Manager) ohne Internet und ohne GitHub-API-Limit funktioniert.
# Der Stand steht danach in koalino/assets/nit_lib/VERSION. Nach Änderungen an
# NIT_Bibliotheken dieses Skript laufen lassen und das Ergebnis committen
# (in der CI läuft es bei jedem Build).
set -euo pipefail

SRC="${1:?Pfad zum NIT_Bibliotheken-Repository angeben, z. B. ../NIT_Bibliotheken}"
DEST="$(cd "$(dirname "$0")/../.." && pwd)/koalino/assets/nit_lib"

N=$(find "$SRC" -mindepth 2 -maxdepth 2 -name 'nitbw_*.py' | wc -l)
[ "$N" -gt 0 ] || { echo "Keine nitbw_*.py unter $SRC gefunden." >&2; exit 1; }

rm -rf "$DEST"
mkdir -p "$DEST"
# Nur die Bibliotheks-Module (ohne Beispiele, READMEs und Hilfsskripte)
find "$SRC" -mindepth 2 -maxdepth 2 -name 'nitbw_*.py' -exec cp {} "$DEST"/ \;

STAND="$(git -C "$SRC" describe --tags --always 2>/dev/null || echo unbekannt)"
printf 'NIT_Bibliotheken %s (%s Module)\nQuelle: https://github.com/juchemGDG/NIT_Bibliotheken\nÜbernommen mit release/scripts/sync_nit_lib.sh – nicht von Hand ändern.\n' \
  "$STAND" "$N" > "$DEST/VERSION"
echo "NIT_Bibliotheken ($STAND, $N Module) nach $DEST übernommen."
