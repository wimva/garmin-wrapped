#!/usr/bin/env bash
# Build web/garmin-wrapped-kit.zip: the files an assistant needs (prompt, style guide, kit), nothing else.
set -euo pipefail
cd "$(dirname "$0")/.."
rm -f web/garmin-wrapped-kit.zip
mkdir -p web
zip -qr web/garmin-wrapped-kit.zip PROMPT.md STYLEGUIDE.md README.md kit -x '*/__pycache__/*' '*.DS_Store'
ls -lh web/garmin-wrapped-kit.zip
