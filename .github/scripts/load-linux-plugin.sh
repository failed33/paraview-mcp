#!/usr/bin/env bash

set -euxo pipefail

: "${ARCHIVE_NAME:?ARCHIVE_NAME is required}"

runtime_root=$(mktemp -d)
plugin_root=$(mktemp -d)

tar -xzf /runtime/paraview-runtime.tar.gz -C "$runtime_root"
tar -xzf "/workspace/$ARCHIVE_NAME" -C "$plugin_root"

pvpython=$(find "$runtime_root" -path '*/bin/pvpython' -print -quit)
plugin=$(find "$plugin_root" -name ParaViewMCP.so -print -quit)
test -x "$pvpython"
test -f "$plugin"

"$pvpython" /workspace/Testing/Smoke/load_plugin.py "$plugin"
