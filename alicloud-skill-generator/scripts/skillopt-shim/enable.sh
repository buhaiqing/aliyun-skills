#!/bin/bash
# enable.sh — persistently install the skillopt shim into the user's shell rc.
# Idempotent: re-running is a no-op. To uninstall, run enable.sh uninstall.
#
# Usage:
#   ./enable.sh            # install for current user (zsh + bash)
#   ./enable.sh uninstall  # remove the shim block from rc files

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHIM_PATH="${SCRIPT_DIR}/aliyun-shim.sh"
MARKER_BEGIN="# >>> skillopt-shim >>>"
MARKER_END="# <<< skillopt-shim <<<"
RC_FILES=("${HOME}/.zshrc" "${HOME}/.bashrc")

_install() {
  local rc
  for rc in "${RC_FILES[@]}"; do
    [[ -f "$rc" ]] || continue
    if grep -qF "$MARKER_BEGIN" "$rc" 2>/dev/null; then
      echo "[skillopt-shim] already installed in $rc"
      continue
    fi
    cat >> "$rc" <<EOF

$MARKER_BEGIN
# Auto-installed by alicloud-skill-generator/scripts/skillopt-shim/enable.sh
# DO NOT EDIT THIS BLOCK MANUALLY — re-run enable.sh to manage.
# Disable: ./enable.sh uninstall
if [ -f "$SHIM_PATH" ]; then
  source "$SHIM_PATH"
fi
$MARKER_END
EOF
    echo "[skillopt-shim] installed in $rc"
  done
  echo
  echo "Reload your shell or run:  source $SHIM_PATH"
  echo "Verify with:               type aliyun"
  echo "Enable logging:            export SKILLOPT_SHIM_LOG=1"
}

_uninstall() {
  local rc
  for rc in "${RC_FILES[@]}"; do
    [[ -f "$rc" ]] || continue
    if ! grep -qF "$MARKER_BEGIN" "$rc" 2>/dev/null; then
      continue
    fi
    # Delete the block between markers (inclusive).
    # Uses a temp file because BSD/GNU sed -i differ.
    local tmp
    tmp="$(mktemp)"
    awk -v begin="$MARKER_BEGIN" -v end="$MARKER_END" '
      $0 == begin { in_block = 1; next }
      $0 == end   { in_block = 0; next }
      !in_block   { print }
    ' "$rc" > "$tmp"
    mv "$tmp" "$rc"
    echo "[skillopt-shim] removed from $rc"
  done
}

case "${1:-install}" in
  install|"")   _install ;;
  uninstall|rm) _uninstall ;;
  *)
    echo "Usage: $0 [install|uninstall]" >&2
    exit 2
    ;;
esac
