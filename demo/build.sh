#!/usr/bin/env bash
# Assembles the static playground: page, styles, the ccmt sources and samples.
set -euo pipefail
cd "$(dirname "$0")/.."
out="${1:-site}"
rm -rf "$out" && mkdir -p "$out/ccmt" "$out/samples"
cp demo/index.html demo/base.css demo/styles.css demo/app.js demo/tour.js demo/bridge.py "$out/"
cp src/ccmt/*.py "$out/ccmt/"
cp samples/*.yaml samples/*.csv "$out/samples/"
echo "built $out"
