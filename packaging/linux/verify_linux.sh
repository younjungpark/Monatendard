#!/usr/bin/env bash
# Linux CI and local E2E verifier for packaging/linux/install.sh.
# Runs in an isolated temporary HOME / XDG_DATA_HOME / XDG_CACHE_HOME.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALLER="${SCRIPT_DIR}/install.sh"
SANDBOX="$(mktemp -d "${RUNNER_TEMP:-/tmp}/monatendard-linux-verify-XXXXXX")"

cleanup() {
    rm -rf "$SANDBOX"
}
trap cleanup EXIT

export HOME="${SANDBOX}/home"
export XDG_DATA_HOME="${SANDBOX}/data"
export XDG_CACHE_HOME="${SANDBOX}/cache"
mkdir -p "$HOME" "$XDG_DATA_HOME" "$XDG_CACHE_HOME"

FONT_ROOT="${XDG_DATA_HOME}/fonts"
STYLES=(
    Bold BoldItalic ExtraBold ExtraBoldItalic ExtraLight ExtraLightItalic
    Italic Light LightItalic Medium MediumItalic Regular SemiBold SemiBoldItalic
)

bash -n "$INSTALLER"
bash -n "${SCRIPT_DIR}/verify_linux.sh"
if command -v shellcheck >/dev/null 2>&1; then
    shellcheck "$INSTALLER" "${SCRIPT_DIR}/verify_linux.sh"
fi

# 1. Help, version, and dry-run leave disk clean.
bash "$INSTALLER" --help >/dev/null
VERSION_OUT="$(bash "$INSTALLER" --version)"
[[ "$VERSION_OUT" == *"Monatendard Linux installer"* ]]
bash "$INSTALLER" --all --dry-run >/dev/null
[[ ! -e "${FONT_ROOT}/monatendard" && ! -e "${FONT_ROOT}/monatendard-nerd" ]]

# 2. Default install via stdin pipe downloads official v0.3.1+ Standard ZIP and registers font.
bash -s < "$INSTALLER"
for style in "${STYLES[@]}"; do
    test -s "${FONT_ROOT}/monatendard/Monatendard-${style}.ttf"
done
test -f "${FONT_ROOT}/monatendard/.monatendard-managed"
fc-list : family | grep -Fx "Monatendard" >/dev/null

# 3. Simulated upgrade from older managed marker updates cleanly.
sed -i 's/^version=.*/version=0.0.0/' "${FONT_ROOT}/monatendard/.monatendard-managed"
bash "$INSTALLER"
! grep -Fx "version=0.0.0" "${FONT_ROOT}/monatendard/.monatendard-managed"

# 4. Nerd install coexists alongside Standard and registers with fontconfig.
bash "$INSTALLER" --nerd
for style in "${STYLES[@]}"; do
    test -s "${FONT_ROOT}/monatendard/Monatendard-${style}.ttf"
    test -s "${FONT_ROOT}/monatendard-nerd/MonatendardNFM-${style}.ttf"
done
fc-list : family | grep -Fx "Monatendard Nerd Font Mono" >/dev/null

# 5. External manual installation conflict blocks install without touching managed dirs.
mkdir -p "${FONT_ROOT}/manual-conflict"
cp "${FONT_ROOT}/monatendard/Monatendard-Regular.ttf" \
    "${FONT_ROOT}/manual-conflict/Monatendard-Regular.ttf"
if bash "$INSTALLER" >/dev/null 2>&1; then
    echo "FAIL: Expected manual conflict to abort installation" >&2
    exit 1
fi
test -s "${FONT_ROOT}/monatendard/Monatendard-Regular.ttf"
rm -rf "${FONT_ROOT}/manual-conflict"

# 6. Uninstall --all removes both managed directories and exits 0 idempotently on repeat.
bash "$INSTALLER" --all --uninstall
[[ ! -e "${FONT_ROOT}/monatendard" && ! -e "${FONT_ROOT}/monatendard-nerd" ]]
bash "$INSTALLER" --all --uninstall

echo "PASS: Linux installer syntax, official ZIP install/upgrade, coexistence, conflict, and uninstall verified."
