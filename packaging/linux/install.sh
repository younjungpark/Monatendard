#!/usr/bin/env bash
set -euo pipefail

# Pinned official stable release metadata (updated by packaging/linux/update_linux.py).
RELEASE_VERSION="0.4.0"
STANDARD_URL="https://github.com/younjungpark/Monatendard/releases/download/v0.4.0/Monatendard-v0.4.0-Desktop.zip"
STANDARD_SHA256="fe514af8d973ab664beb5395591331d2201bb9b9b909758ca2e1b3a805b63cc9"
NERD_URL="https://github.com/younjungpark/Monatendard/releases/download/v0.4.0/Monatendard-v0.4.0-Desktop-Nerd.zip"
NERD_SHA256="0137cc1de55ddd9a93440bcb346f3c00ed3ed9600eb5efaa36185e6d260f2311"

STANDARD_FONTS=(
    "fonts/Monatendard-Bold.ttf"
    "fonts/Monatendard-BoldItalic.ttf"
    "fonts/Monatendard-ExtraBold.ttf"
    "fonts/Monatendard-ExtraBoldItalic.ttf"
    "fonts/Monatendard-ExtraLight.ttf"
    "fonts/Monatendard-ExtraLightItalic.ttf"
    "fonts/Monatendard-Italic.ttf"
    "fonts/Monatendard-Light.ttf"
    "fonts/Monatendard-LightItalic.ttf"
    "fonts/Monatendard-Medium.ttf"
    "fonts/Monatendard-MediumItalic.ttf"
    "fonts/Monatendard-Regular.ttf"
    "fonts/Monatendard-SemiBold.ttf"
    "fonts/Monatendard-SemiBoldItalic.ttf"
)

NERD_FONTS=(
    "fonts/MonatendardNFM-Bold.ttf"
    "fonts/MonatendardNFM-BoldItalic.ttf"
    "fonts/MonatendardNFM-ExtraBold.ttf"
    "fonts/MonatendardNFM-ExtraBoldItalic.ttf"
    "fonts/MonatendardNFM-ExtraLight.ttf"
    "fonts/MonatendardNFM-ExtraLightItalic.ttf"
    "fonts/MonatendardNFM-Italic.ttf"
    "fonts/MonatendardNFM-Light.ttf"
    "fonts/MonatendardNFM-LightItalic.ttf"
    "fonts/MonatendardNFM-Medium.ttf"
    "fonts/MonatendardNFM-MediumItalic.ttf"
    "fonts/MonatendardNFM-Regular.ttf"
    "fonts/MonatendardNFM-SemiBold.ttf"
    "fonts/MonatendardNFM-SemiBoldItalic.ttf"
)

MARKER_NAME=".monatendard-managed"
WORK_DIR=""
STAGE_DIRS=()
BACKUP_DIRS=()

cleanup() {
    local dir
    if [[ -n "$WORK_DIR" && -d "$WORK_DIR" ]]; then
        rm -rf "$WORK_DIR"
    fi
    for dir in "${STAGE_DIRS[@]:-}"; do
        if [[ -n "$dir" && -d "$dir" ]]; then
            rm -rf "$dir"
        fi
    done
    for dir in "${BACKUP_DIRS[@]:-}"; do
        if [[ -n "$dir" && -d "$dir" ]]; then
            rm -rf "$dir"
        fi
    done
}
trap cleanup EXIT

die() {
    printf 'Monatendard: %s\n' "$1" >&2
    exit 1
}

usage() {
    cat <<'EOF'
Monatendard Linux font installer (user scope only)

Usage:
  install.sh [options]
  curl -fsSL https://raw.githubusercontent.com/younjungpark/Monatendard/main/packaging/linux/install.sh | bash
  curl -fsSL https://raw.githubusercontent.com/younjungpark/Monatendard/main/packaging/linux/install.sh | bash -s -- [options]

Options:
  (default)     Install or update Monatendard (standard family)
  --nerd        Target Monatendard Nerd Font Mono instead of standard
  --all         Target both Monatendard and Monatendard Nerd Font Mono
  --uninstall   Remove managed installation for the selected family
  --status      Show installation status for selected families and exit
  --dry-run     Show planned actions without modifying files or font cache
  --version     Print the pinned release version and exit
  -h, --help    Show this help message and exit
EOF
}

family_display_name() {
    case "$1" in
        monatendard) printf 'Monatendard' ;;
        monatendard-nerd) printf 'Monatendard Nerd Font Mono' ;;
        *) die "Unknown family: $1" ;;
    esac
}

family_glob() {
    case "$1" in
        monatendard) printf 'Monatendard-*.ttf' ;;
        monatendard-nerd) printf 'MonatendardNFM-*.ttf' ;;
        *) die "Unknown family: $1" ;;
    esac
}

family_url() {
    case "$1" in
        monatendard) printf '%s' "$STANDARD_URL" ;;
        monatendard-nerd) printf '%s' "$NERD_URL" ;;
        *) die "Unknown family: $1" ;;
    esac
}

family_sha256() {
    case "$1" in
        monatendard) printf '%s' "$STANDARD_SHA256" ;;
        monatendard-nerd) printf '%s' "$NERD_SHA256" ;;
        *) die "Unknown family: $1" ;;
    esac
}

print_expected_fonts() {
    local font
    case "$1" in
        monatendard)
            for font in "${STANDARD_FONTS[@]}"; do
                printf '%s\n' "$font"
            done
            ;;
        monatendard-nerd)
            for font in "${NERD_FONTS[@]}"; do
                printf '%s\n' "$font"
            done
            ;;
        *) die "Unknown family: $1" ;;
    esac
}

check_environment() {
    local os_name uid
    os_name="$(uname -s 2>/dev/null || true)"
    if [[ "$os_name" != "Linux" ]]; then
        die "This installer supports Linux only (detected: ${os_name:-unknown}). Use Homebrew on macOS or Scoop on Windows."
    fi

    uid="$(id -u)"
    if [[ "$uid" -eq 0 ]]; then
        die "Do not run as root or with sudo. This installer installs fonts for the current user only."
    fi

    if [[ -z "${HOME:-}" || "${HOME:0:1}" != "/" ]]; then
        die "HOME must be set to an absolute path."
    fi

    if [[ -n "${XDG_DATA_HOME:-}" && "${XDG_DATA_HOME:0:1}" != "/" ]]; then
        die "XDG_DATA_HOME must be an absolute path when set."
    fi
}

check_tools() {
    local action="$1"
    local missing=()
    local tool

    if [[ "$action" == "status" ]]; then
        return 0
    fi

    if ! command -v fc-cache >/dev/null 2>&1; then
        missing+=("fc-cache (fontconfig)")
    fi

    if [[ "$action" == "install" ]]; then
        if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then
            missing+=("curl or wget")
        fi
        for tool in unzip sha256sum; do
            if ! command -v "$tool" >/dev/null 2>&1; then
                missing+=("$tool")
            fi
        done
    fi

    if [[ "${#missing[@]}" -gt 0 ]]; then
        local joined
        joined="$(printf '%s, ' "${missing[@]}")"
        joined="${joined%, }"
        die "Missing required tool(s): ${joined}. Install them with your distribution package manager and retry."
    fi
}

validate_managed_dir() {
    local family="$1"
    local target_dir="$2"
    local marker_path="${target_dir}/${MARKER_NAME}"

    if [[ -L "$target_dir" ]]; then
        die "Refusing to modify symlinked font directory: ${target_dir}"
    fi
    if [[ ! -d "$target_dir" ]]; then
        die "Refusing to overwrite non-directory path: ${target_dir}"
    fi
    if [[ ! -f "$marker_path" || -L "$marker_path" ]]; then
        die "Existing directory is not managed by this installer (manual installation detected): ${target_dir}. Remove it manually and retry."
    fi

    local marker_family=""
    local marker_files=""
    local line
    while IFS= read -r line; do
        case "$line" in
            family=*) marker_family="${line#family=}" ;;
            files=*) marker_files="${line#files=}" ;;
        esac
    done < "$marker_path"

    if [[ "$marker_family" != "$family" ]]; then
        die "Managed marker family mismatch in ${target_dir}. Remove it manually and retry."
    fi

    local -a allowed=()
    IFS=',' read -r -a allowed <<< "$marker_files"

    local entry base matched expected_file
    while IFS= read -r -d '' entry; do
        base="${entry##*/}"
        if [[ -L "$entry" || ! -f "$entry" ]]; then
            die "Unexpected non-file entry found in managed directory (${entry}). Remove unmanaged entries manually and retry."
        fi
        case "$base" in
            "$MARKER_NAME"|.uuid|fonts.dir|fonts.scale|encodings.dir|fonts.cache-*)
                continue
                ;;
        esac
        matched=0
        for expected_file in "${allowed[@]:-}"; do
            if [[ -n "$expected_file" && "$base" == "$expected_file" ]]; then
                matched=1
                break
            fi
        done
        if [[ "$matched" -ne 1 ]]; then
            die "Unexpected file found in managed directory (${entry}). Remove unmanaged files manually and retry."
        fi
    done < <(find "$target_dir" -mindepth 1 -maxdepth 1 -print0)
}

check_conflicts_for_family() {
    local family="$1"
    local user_font_root="$2"
    local target_dir="${user_font_root}/${family}"
    local glob_pattern
    glob_pattern="$(family_glob "$family")"

    if [[ -e "$target_dir" || -L "$target_dir" ]]; then
        validate_managed_dir "$family" "$target_dir"
    fi

    local scan_roots=()
    if [[ -d "$user_font_root" ]]; then
        scan_roots+=("$user_font_root")
    fi
    local home_norm="${HOME%/}"
    local legacy_root="${home_norm}/.fonts"
    if [[ -d "$legacy_root" && "$legacy_root" != "$user_font_root" ]]; then
        scan_roots+=("$legacy_root")
    fi

    local conflicts=()
    local root_dir found
    for root_dir in "${scan_roots[@]:-}"; do
        if [[ -z "$root_dir" ]]; then
            continue
        fi
        while IFS= read -r -d '' found; do
            case "$found" in
                "${target_dir}/"*) continue ;;
                *) conflicts+=("$found") ;;
            esac
        done < <(find -H "$root_dir" -mindepth 1 \( -type f -o -type l \) -name "$glob_pattern" -print0)
    done

    if [[ "${#conflicts[@]}" -gt 0 ]]; then
        printf 'Monatendard: Manual installation conflict detected for %s:\n' "$(family_display_name "$family")" >&2
        local path
        for path in "${conflicts[@]}"; do
            printf '  - %s\n' "$path" >&2
        done
        die "Remove the manual font files listed above and retry."
    fi
}

download_archive() {
    local url="$1"
    local destination="$2"

    if command -v curl >/dev/null 2>&1; then
        curl -fsSL --proto '=https' --tlsv1.2 --connect-timeout 30 --max-time 300 -o "$destination" "$url"
    elif command -v wget >/dev/null 2>&1; then
        wget --https-only --secure-protocol=TLSv1_2 --timeout=30 -qO "$destination" "$url"
    else
        die "Neither curl nor wget is available."
    fi
}

verify_sha256() {
    local archive="$1"
    local expected="$2"
    local line actual
    line="$(sha256sum "$archive")"
    actual="${line%% *}"
    if [[ "${actual,,}" != "${expected,,}" ]]; then
        die "SHA256 mismatch for downloaded archive (expected ${expected}, got ${actual})."
    fi
}

verify_and_extract_archive() {
    local family="$1"
    local archive="$2"
    local extract_dir="$3"

    local raw_list sorted_list unique_list
    raw_list="$(unzip -Z1 "$archive")" || die "Downloaded file is not a valid ZIP archive."
    sorted_list="$(printf '%s\n' "$raw_list" | LC_ALL=C sort)"
    unique_list="$(printf '%s\n' "$sorted_list" | LC_ALL=C sort -u)"
    if [[ "$sorted_list" != "$unique_list" ]]; then
        die "Duplicate entries detected in ZIP archive."
    fi

    local entry
    while IFS= read -r entry; do
        [[ -z "$entry" ]] && continue
        if [[ "$entry" == /* || "$entry" == *\\* || "$entry" == ".." || "$entry" == ../* || "$entry" == */.. || "$entry" == */../* ]]; then
            die "Unsafe path detected in ZIP archive: ${entry}"
        fi
    done <<< "$raw_list"

    local zipinfo_output line
    zipinfo_output="$(unzip -Z "$archive")" || die "Failed to inspect ZIP archive metadata."
    while IFS= read -r line; do
        if [[ "$line" == l* ]]; then
            die "Symlink entry detected in ZIP archive."
        fi
    done <<< "$zipinfo_output"

    local actual_fonts expected_fonts
    actual_fonts="$(printf '%s\n' "$sorted_list" | grep -E '\.[Tt][Tt][Ff]$' || true)"
    expected_fonts="$(print_expected_fonts "$family" | LC_ALL=C sort)"
    if [[ "$actual_fonts" != "$expected_fonts" ]]; then
        die "ZIP archive font list does not match expected 14 TTF files for $(family_display_name "$family")."
    fi

    local extract_args=()
    while IFS= read -r entry; do
        [[ -n "$entry" ]] && extract_args+=("$entry")
    done <<< "$expected_fonts"

    mkdir -p "$extract_dir"
    unzip -qq -o "$archive" "${extract_args[@]}" -d "$extract_dir" || die "Failed to extract TTF files from ZIP archive."

    local extracted_path
    for entry in "${extract_args[@]}"; do
        extracted_path="${extract_dir}/${entry}"
        if [[ ! -f "$extracted_path" || -L "$extracted_path" || ! -s "$extracted_path" ]]; then
            die "Extracted font file is missing, empty, or invalid: ${entry}"
        fi
    done
}

install_family() {
    local family="$1"
    local user_font_root="$2"
    local dry_run="$3"
    local target_dir="${user_font_root}/${family}"
    local display_name url expected_sha
    display_name="$(family_display_name "$family")"
    url="$(family_url "$family")"
    expected_sha="$(family_sha256 "$family")"

    if [[ "$dry_run" -eq 1 ]]; then
        if [[ -d "$target_dir" ]]; then
            printf '[dry-run] Would download %s (v%s), verify SHA256, and atomically update %s\n' \
                "$display_name" "$RELEASE_VERSION" "$target_dir"
        else
            printf '[dry-run] Would download %s (v%s), verify SHA256, and install to %s\n' \
                "$display_name" "$RELEASE_VERSION" "$target_dir"
        fi
        return 0
    fi

    local archive_path="${WORK_DIR}/${family}.zip"
    local extract_dir="${WORK_DIR}/${family}-extract"
    download_archive "$url" "$archive_path"
    verify_sha256 "$archive_path" "$expected_sha"
    verify_and_extract_archive "$family" "$archive_path" "$extract_dir"

    mkdir -p "$user_font_root"
    local stage_dir
    stage_dir="$(mktemp -d "${user_font_root}/.monatendard-staging-XXXXXX")"
    STAGE_DIRS+=("$stage_dir")

    local font_paths=()
    local font_basenames=()
    local entry base
    while IFS= read -r entry; do
        [[ -n "$entry" ]] || continue
        font_paths+=("$entry")
        base="${entry##*/}"
        font_basenames+=("$base")
        cp "${extract_dir}/${entry}" "${stage_dir}/${base}"
        chmod 0644 "${stage_dir}/${base}"
    done < <(print_expected_fonts "$family" | LC_ALL=C sort)

    local joined_files
    joined_files="$(IFS=','; printf '%s' "${font_basenames[*]}")"
    cat > "${stage_dir}/${MARKER_NAME}" <<EOF
schema=1
family=${family}
version=${RELEASE_VERSION}
files=${joined_files}
EOF
    chmod 0644 "${stage_dir}/${MARKER_NAME}"

    local backup_dir=""
    if [[ -d "$target_dir" ]]; then
        backup_dir="$(mktemp -d "${user_font_root}/.monatendard-backup-XXXXXX")"
        BACKUP_DIRS+=("$backup_dir")
        mv "$target_dir" "${backup_dir}/previous"
    fi

    if ! mv "$stage_dir" "$target_dir"; then
        if [[ -n "$backup_dir" && -d "${backup_dir}/previous" ]]; then
            mv "${backup_dir}/previous" "$target_dir" || true
        fi
        die "Failed to install ${display_name} into ${target_dir}."
    fi

    if [[ -n "$backup_dir" && -d "$backup_dir" ]]; then
        rm -rf "$backup_dir"
    fi

    printf 'Monatendard: Installed %s v%s (%d font files) to %s.\n' \
        "$display_name" "$RELEASE_VERSION" "${#font_paths[@]}" "$target_dir"
}

uninstall_family() {
    local family="$1"
    local user_font_root="$2"
    local dry_run="$3"
    local target_dir="${user_font_root}/${family}"
    local display_name
    display_name="$(family_display_name "$family")"

    if [[ ! -e "$target_dir" && ! -L "$target_dir" ]]; then
        printf 'Monatendard: %s is not installed; nothing to uninstall.\n' "$display_name"
        return 1
    fi

    if [[ "$dry_run" -eq 1 ]]; then
        printf '[dry-run] Would remove managed installation of %s at %s\n' "$display_name" "$target_dir"
        return 0
    fi

    rm -rf "$target_dir" || die "Failed to remove ${display_name} at ${target_dir}."
    printf 'Monatendard: Uninstalled %s from %s.\n' "$display_name" "$target_dir"
    return 0
}

status_family() {
    local family="$1"
    local user_font_root="$2"
    local target_dir="${user_font_root}/${family}"
    local marker_path="${target_dir}/${MARKER_NAME}"
    local display_name glob_pattern
    display_name="$(family_display_name "$family")"
    glob_pattern="$(family_glob "$family")"

    local scan_roots=()
    if [[ -d "$user_font_root" ]]; then
        scan_roots+=("$user_font_root")
    fi
    local home_norm="${HOME%/}"
    local legacy_root="${home_norm}/.fonts"
    if [[ -d "$legacy_root" && "$legacy_root" != "$user_font_root" ]]; then
        scan_roots+=("$legacy_root")
    fi

    local external_files=()
    local root_dir found
    for root_dir in "${scan_roots[@]:-}"; do
        if [[ -z "$root_dir" ]]; then
            continue
        fi
        while IFS= read -r -d '' found; do
            case "$found" in
                "${target_dir}/"*) continue ;;
                *) external_files+=("$found") ;;
            esac
        done < <(find -H "$root_dir" -mindepth 1 \( -type f -o -type l \) -name "$glob_pattern" -print0)
    done

    local path
    if [[ -e "$target_dir" || -L "$target_dir" ]]; then
        if ( validate_managed_dir "$family" "$target_dir" ) >/dev/null 2>&1; then
            local installed_version="unknown"
            local line
            while IFS= read -r line; do
                case "$line" in
                    version=*) installed_version="${line#version=}" ;;
                esac
            done < "$marker_path"

            if [[ "${#external_files[@]}" -gt 0 ]]; then
                printf '%s: conflict (managed v%s at %s; manual files also found)\n' \
                    "$display_name" "$installed_version" "$target_dir"
                for path in "${external_files[@]}"; do
                    printf '  - %s\n' "$path"
                done
            elif [[ "$installed_version" == "$RELEASE_VERSION" ]]; then
                printf '%s: installed (managed, v%s, up-to-date) at %s\n' \
                    "$display_name" "$installed_version" "$target_dir"
            else
                printf '%s: installed (managed, v%s, update available: v%s) at %s\n' \
                    "$display_name" "$installed_version" "$RELEASE_VERSION" "$target_dir"
            fi
        else
            printf '%s: manual or unmanaged installation detected (%s)\n' \
                "$display_name" "$target_dir"
            for path in "${external_files[@]:-}"; do
                if [[ -n "$path" ]]; then
                    printf '  - %s\n' "$path"
                fi
            done
        fi
    elif [[ "${#external_files[@]}" -gt 0 ]]; then
        printf '%s: manual installation detected\n' "$display_name"
        for path in "${external_files[@]}"; do
            printf '  - %s\n' "$path"
        done
    else
        printf '%s: not installed\n' "$display_name"
    fi
}

main() {
    local target="default"
    local action="install"
    local dry_run=0
    local show_help=0
    local show_version=0

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --nerd)
                if [[ "$target" != "default" && "$target" != "nerd" ]]; then
                    die "Conflicting options: cannot combine --nerd with --all."
                fi
                target="nerd"
                ;;
            --all)
                if [[ "$target" != "default" && "$target" != "all" ]]; then
                    die "Conflicting options: cannot combine --all with --nerd."
                fi
                target="all"
                ;;
            --uninstall)
                if [[ "$action" == "status" ]]; then
                    die "Conflicting options: cannot combine --uninstall with --status."
                fi
                action="uninstall"
                ;;
            --status)
                if [[ "$action" == "uninstall" ]]; then
                    die "Conflicting options: cannot combine --status with --uninstall."
                fi
                action="status"
                ;;
            --dry-run)
                dry_run=1
                ;;
            --version)
                show_version=1
                ;;
            -h|--help)
                show_help=1
                ;;
            *)
                die "Unknown option or argument: $1 (use --help for usage)"
                ;;
        esac
        shift
    done

    if [[ "$show_help" -eq 1 ]]; then
        if [[ "$target" != "default" || "$action" != "install" || "$dry_run" -eq 1 || "$show_version" -eq 1 ]]; then
            die "--help cannot be combined with other options."
        fi
        usage
        exit 0
    fi

    if [[ "$show_version" -eq 1 ]]; then
        if [[ "$target" != "default" || "$action" != "install" || "$dry_run" -eq 1 ]]; then
            die "--version cannot be combined with other options."
        fi
        printf 'Monatendard Linux installer %s\n' "$RELEASE_VERSION"
        exit 0
    fi

    if [[ "$action" == "status" && "$dry_run" -eq 1 ]]; then
        die "--dry-run cannot be combined with --status."
    fi

    check_environment
    check_tools "$action"

    local home_norm="${HOME%/}"
    local data_home="${XDG_DATA_HOME:-${home_norm}/.local/share}"
    data_home="${data_home%/}"
    local user_font_root="${data_home}/fonts"

    local families=()
    case "$target" in
        default)
            if [[ "$action" == "status" ]]; then
                families=("monatendard" "monatendard-nerd")
            else
                families=("monatendard")
            fi
            ;;
        nerd) families=("monatendard-nerd") ;;
        all) families=("monatendard" "monatendard-nerd") ;;
    esac

    local family
    if [[ "$action" == "status" ]]; then
        for family in "${families[@]}"; do
            status_family "$family" "$user_font_root"
        done
        return 0
    fi

    # Preflight conflict check across every selected family before touching disk.
    for family in "${families[@]}"; do
        check_conflicts_for_family "$family" "$user_font_root"
    done

    if [[ "$action" == "install" ]]; then
        if [[ "$dry_run" -eq 0 ]]; then
            WORK_DIR="$(mktemp -d)"
        fi
        for family in "${families[@]}"; do
            install_family "$family" "$user_font_root" "$dry_run"
        done
        if [[ "$dry_run" -eq 1 ]]; then
            printf '[dry-run] Would refresh font cache with fc-cache -f %s\n' "$user_font_root"
        else
            fc-cache -f "$user_font_root"
            printf 'Monatendard: Font cache refreshed. Restart your editor and terminal.\n'
        fi
    else
        local removed_any=0
        for family in "${families[@]}"; do
            if uninstall_family "$family" "$user_font_root" "$dry_run"; then
                removed_any=1
            fi
        done
        if [[ "$removed_any" -eq 1 ]]; then
            if [[ "$dry_run" -eq 1 ]]; then
                printf '[dry-run] Would refresh font cache with fc-cache -f %s\n' "$user_font_root"
            else
                if [[ -d "$user_font_root" ]]; then
                    fc-cache -f "$user_font_root"
                else
                    fc-cache -f
                fi
                printf 'Monatendard: Font cache refreshed.\n'
            fi
        fi
    fi
}

main "$@"
