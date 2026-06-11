#!/usr/bin/env bash
# Build the distributable skill archives from source.
#
# The repo root IS the skill: SKILL.md + scripts/ + references/. This script
# verifies the engine, then packs those files into:
#   deep-understanding-tutor.skill  — the skill bundle (a zip of the dir)
#   deep-understanding-tutor.zip    — SKILL.md + the .skill, for upload/sharing
# Both are gitignored; regenerate them on demand or attach to a GitHub release.
set -euo pipefail

cd "$(dirname "$0")"
NAME=deep-understanding-tutor
SKILL="$NAME.skill"
ZIP="$NAME.zip"

echo "==> Verifying engine"
python3 scripts/tutor_engine.py selftest

echo "==> Building $SKILL"
rm -rf "_build/$NAME" "$SKILL" "$ZIP"
mkdir -p "_build/$NAME"
cp -R SKILL.md scripts references "_build/$NAME/"
( cd _build && zip -rq "../$SKILL" "$NAME" )

echo "==> Building $ZIP"
zip -q "$ZIP" SKILL.md "$SKILL"

rm -rf _build
echo "==> Done: $SKILL, $ZIP"
