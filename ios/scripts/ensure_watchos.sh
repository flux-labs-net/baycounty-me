#!/bin/bash
# The iPhone app carries the Apple Watch app, so every build needs Xcode's watchOS platform. Xcode leaves it out
# by default; this downloads it once (a few GB) and is a no-op after that. Used by the Mac CI jobs.
set -euo pipefail
if xcrun simctl list runtimes | grep -q "watchOS"; then
  echo "watchOS platform is installed."
else
  echo "Downloading Xcode's watchOS platform (one time on this Mac)..."
  xcodebuild -downloadPlatform watchOS
fi
