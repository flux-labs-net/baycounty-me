#!/usr/bin/env bash
# Copies the site's latest published data into the app as its first-launch seed.
# Run after a site rebuild (data/build.py + site/build_site.py), before an App Store build.
set -euo pipefail
cd "$(dirname "$0")/../.."
src=site/public/downloads
dst=ios/BayCountyMe/Resources/Seed
for f in index government-profiles meetings cra-payments; do
  cp "$src/$f.json" "$dst/$f.json"
done
echo "Seed updated from $src ($(python3 -c "import json;print(json.load(open('$src/index.json'))['updated'])"))"
