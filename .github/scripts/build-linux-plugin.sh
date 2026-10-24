#!/usr/bin/env bash

set -euxo pipefail

: "${ARCHIVE_DIR:?ARCHIVE_DIR is required}"
: "${FIND_ALL_COMPONENTS:?FIND_ALL_COMPONENTS is required}"

cmake \
  -S . \
  -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/workspace/install \
  -DCMAKE_PREFIX_PATH=/builds/gitlab-kitware-sciviz-ci/build/install \
  -DPARAVIEW_MCP_FIND_ALL_PARAVIEW_COMPONENTS="$FIND_ALL_COMPONENTS" \
  -DBUILD_TESTING=ON
cmake --build build --parallel 2 --verbose
QT_QPA_PLATFORM=offscreen ctest --test-dir build --output-on-failure --no-tests=error -E PythonIntegration
cmake --install build

plugin=$(find install -name ParaViewMCP.so -print -quit)
plugin_xml=$(find install -name ParaViewMCP.plugins.xml -print -quit)
test -n "$plugin"
readelf -d "$plugin"
if readelf -d "$plugin" | grep -E '(RPATH|RUNPATH).*(/builds|/paraview)'; then
  echo "Plugin contains a build-environment runtime path" >&2
  exit 1
fi

mkdir -p "$ARCHIVE_DIR"
cp "$plugin" "$ARCHIVE_DIR/"
[[ -z "$plugin_xml" ]] || cp "$plugin_xml" "$ARCHIVE_DIR/"
cp LICENSE THIRD-PARTY-NOTICES.txt "$ARCHIVE_DIR/"
cp -r LICENSES "$ARCHIVE_DIR/"
cp .github/INSTALL_PLUGIN.md "$ARCHIVE_DIR/INSTALL.md"
tar czf "${ARCHIVE_DIR}.tar.gz" "$ARCHIVE_DIR"
sha256sum "${ARCHIVE_DIR}.tar.gz" > "${ARCHIVE_DIR}.tar.gz.sha256"
