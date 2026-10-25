#!/usr/bin/env bash
# Commit and push a scheduled refresh. Used by refresh-meetings.yml and refresh-weekly.yml.
#   push_refresh.sh "<commit message>" <fetched source path>...
# Commits whatever the rebuild changed under data/ and site/public, then pushes to main. If main moved while the
# refresh ran (a pull request merged), the push is rejected: start again from the new main, put back only this run's
# fetched source files, rebuild everything derived from them, and try again (3 tries). Writes pushed=true to
# $GITHUB_OUTPUT when a commit reached main.
set -euo pipefail
msg="$1"; shift
src=("$@")
built="data site/public"

rebuild() {
  (cd data && python build.py > /dev/null && python prep_dash.py > /dev/null)
  (cd site && python build_site.py > /dev/null)
}

git config user.name "BayCounty.me bot"
git config user.email "211150+jeremymcs@users.noreply.github.com"
git add -A $built
git commit -qm "$msg"
for try in 1 2 3; do
  if git push -q origin HEAD:main; then
    echo "pushed=true" >> "$GITHUB_OUTPUT"
    exit 0
  fi
  echo "Push rejected (try $try): main moved; rebuilding on top of it"
  ours=$(git rev-parse HEAD)
  git fetch -q origin main
  git reset -q --hard origin/main
  git checkout "$ours" -- "${src[@]}"
  rebuild
  git add -A $built
  if git diff --cached --quiet; then echo "Nothing left to commit on the new main"; exit 0; fi
  git commit -qm "$msg"
done
echo "::error title=Push::Could not push the refresh after 3 tries"
exit 1
