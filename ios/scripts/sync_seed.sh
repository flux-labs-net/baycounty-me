#!/usr/bin/env bash
# Copies the site's latest published data into the app as its first-launch seed.
# Run after a site rebuild (data/build.py + site/build_site.py), before an App Store build.
set -euo pipefail
cd "$(dirname "$0")/../.."
src=site/public/downloads
dst=ios/BayCountyMe/Resources/Seed
for f in index government-profiles meetings cra-payments schools school-calendar school-enrollment; do
  cp "$src/$f.json" "$dst/$f.json"
done
# Every /data/app file except its index (about 650 KB), so each app screen works offline on first launch.
# The client looks seeds up by file name, so these must not share a name with a dataset.
for f in tax address amendment3 glossary pages updates vendors people donor-contracts money-map; do
  cp "site/public/data/app/$f.json" "$dst/$f.json"
done
# The Accountability console reads the site's own console file.
cp site/public/data/accountability.json "$dst/accountability.json"
echo "Seed updated from $src ($(python3 -c "import json;print(json.load(open('$src/index.json'))['updated'])"))"
