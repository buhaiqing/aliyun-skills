#!/bin/bash
#
# redis-cli-install.sh — Idempotent redis-cli installer for Alibaba Cloud ECS
#
# Source of truth for ALL redis-cli install/upgrade logic in alicloud-redis-ops.
# Spec & user guide: alicloud-redis-ops/references/redis-cli-install.md
#
# Usage:
#   1. Source mode (recommended for local scripts):
#        source redis-cli-install.sh
#        ensure_redis_cli || exit $?
#
#   2. Direct execute mode (for testing only; requires explicit autorun flag):
#        REDIS_CLI_INSTALL_AUTORUN=1 bash redis-cli-install.sh
#
#   3. Cat-inline into Cloud Assistant RunCommand (production pattern):
#        # On your local machine, build the combined script:
#        cat alicloud-redis-ops/scripts/redis-cli-install.sh > /tmp/combined.sh
#        cat >> /tmp/combined.sh <<'BIZ'
#        ensure_redis_cli || exit $?
#        <your business logic here, e.g. redis-cli -h ... DEL key>
#        BIZ
#        # Then submit via Cloud Assistant:
#        aliyun ecs RunCommand --InstanceIds '["i-xxx"]' \
#          --CommandContent "$(cat /tmp/combined.sh)"
#
#   4. Optional environment variables (read by ensure_redis_cli):
#        REQUIRED_VERSION    — Minimum redis-cli version (e.g. "6.0"); default = any
#        REDIS_CLI_BIN_URL   — Offline binary URL for air-gapped environments
#        REDIS_CLI_INSTALL_AUTORUN — Set to "1" to auto-run on script execution
#
# Exit codes:
#   0   — Already installed (version OK) OR install/upgrade succeeded
#   20  — Install failed (pkg manager + source fallback all failed)
#   21  — Source compilation deps (gcc/make) missing AND auto-install failed
#   22  — Offline REDIS_CLI_BIN_URL download failed
#
# Diagnostic format: [HH:MM:SS] [PHASE] key=value
#   PHASE: DIAG | INSTALL | WARN | ERROR | RESULT
#

# ============================================================
# Utility functions
# ============================================================

# version_gte 6.2 5.0  → 0 (true: 6.2 >= 5.0)
version_gte() {
  [ "$(printf '%s\n%s' "$1" "$2" | sort -V | head -1)" = "$2" ]
}

# Detect Alibaba Cloud ECS via metadata endpoint (1s timeout)
# Returns "yes" or "no" on stdout
detect_aliyun_ecs() {
  if curl -fsS -m 1 -o /dev/null \
      http://100.100.100.200/latest/meta-data/instance-id 2>/dev/null; then
    echo "yes"
  else
    echo "no"
  fi
}

# Switch apt sources to Aliyun internal mirror (Aliyun ECS only)
# Backs up sources.list once before modification (idempotent)
use_aliyun_apt_mirror() {
  local mirror="http://mirrors.cloud.aliyuncs.com"
  [ -f /etc/apt/sources.list ] || return 0
  [ -f /etc/apt/sources.list.bak.redis-install ] \
    || cp /etc/apt/sources.list /etc/apt/sources.list.bak.redis-install
  sed -i -E \
    -e "s#https?://[a-zA-Z0-9.-]+\.ubuntu\.com#${mirror}#g" \
    -e "s#https?://[a-zA-Z0-9.-]+\.debian\.org#${mirror}#g" \
    /etc/apt/sources.list
  echo "[$(date +%H:%M:%S)] [INSTALL] apt_mirror=aliyun-internal"
}

# Switch yum/dnf sources to Aliyun internal mirror
# Skips if alinux/anolis (already configured) or already using Aliyun mirror
#
# Note: Uses '|' as sed delimiter (not '#') because '#' appears in commented-out
# baseurl lines and would cause "bad flag in substitute command" errors.
use_aliyun_yum_mirror() {
  local repo_dir=/etc/yum.repos.d
  [ -d "$repo_dir" ] || return 0
  if [ -f /etc/os-release ] && grep -qE 'ID=(alinux|anolis)' /etc/os-release; then
    return 0
  fi
  if ! grep -rq "mirrors.cloud.aliyuncs.com" "$repo_dir" 2>/dev/null; then
    # 1. Comment out mirrorlist lines
    # 2. Uncomment baseurl lines AND replace mirror.centos.org with Aliyun mirror
    sed -i.bak.redis-install \
      -e 's|^mirrorlist=|#mirrorlist=|g' \
      -e 's|^#baseurl=http://mirror.centos.org|baseurl=http://mirrors.cloud.aliyuncs.com|g' \
      "$repo_dir"/*.repo 2>/dev/null || true
    echo "[$(date +%H:%M:%S)] [INSTALL] yum_mirror=aliyun-internal"
  fi
}

# Switch alpine apk repositories to Aliyun public mirror
use_aliyun_apk_mirror() {
  [ -f /etc/apk/repositories ] || return 0
  if ! grep -q "mirrors.aliyun.com" /etc/apk/repositories; then
    sed -i.bak.redis-install \
      's#https\?://dl-cdn\.alpinelinux\.org#https://mirrors.aliyun.com#g' \
      /etc/apk/repositories
    echo "[$(date +%H:%M:%S)] [INSTALL] apk_mirror=aliyun-public"
  fi
}

# Install build toolchain (gcc, make, tar, curl) for source compilation fallback
install_build_tools() {
  echo "[$(date +%H:%M:%S)] [INSTALL] Installing build deps (gcc make tar curl)..."
  if command -v apt-get >/dev/null; then
    apt-get update -qq && apt-get install -y -qq build-essential curl ca-certificates
  elif command -v dnf >/dev/null; then
    dnf install -y -q gcc make tar curl ca-certificates
  elif command -v yum >/dev/null; then
    yum install -y -q gcc make tar curl ca-certificates
  elif command -v zypper >/dev/null; then
    zypper install -y gcc make tar curl ca-certificates
  elif command -v apk >/dev/null; then
    apk add --no-cache gcc make tar curl ca-certificates musl-dev linux-headers
  else
    echo "[$(date +%H:%M:%S)] [ERROR] TYPE=NO_PACKAGE_MANAGER FIX=Cannot install build deps automatically"
    return 1
  fi
}

# ============================================================
# Install strategies (called in priority order by ensure_redis_cli)
# ============================================================

# Strategy 0: Download pre-compiled binary from user-specified URL
# Triggered when REDIS_CLI_BIN_URL is set (offline/air-gapped scenarios)
install_from_offline_url() {
  local url="${REDIS_CLI_BIN_URL:-}"
  [ -z "$url" ] && return 1
  echo "[$(date +%H:%M:%S)] [INSTALL] strategy=offline url=${url}"
  if curl -fsSL -m 120 "$url" -o /tmp/redis-cli.bin; then
    chmod +x /tmp/redis-cli.bin
    install -m 755 /tmp/redis-cli.bin /usr/local/bin/redis-cli
    rm -f /tmp/redis-cli.bin
    return 0
  fi
  echo "[$(date +%H:%M:%S)] [ERROR] TYPE=OFFLINE_DOWNLOAD_FAILED FIX=Check REDIS_CLI_BIN_URL"
  return 22
}

# Strategy 2: Compile redis-cli from source (final fallback)
# Auto-installs build deps; tries Aliyun mirror first, official source as backup
install_from_source() {
  echo "[$(date +%H:%M:%S)] [INSTALL] strategy=source"

  if ! command -v gcc >/dev/null || ! command -v make >/dev/null; then
    install_build_tools || return 21
  fi

  local primary="http://mirrors.aliyun.com/macports/distfiles/redis/redis-stable.tar.gz"
  local fallback="https://download.redis.io/redis-stable.tar.gz"

  if ! curl -fsSL -m 60 "$primary" -o /tmp/redis.tar.gz 2>/dev/null; then
    echo "[$(date +%H:%M:%S)] [WARN] aliyun_mirror_failed, fallback to official"
    if ! curl -fsSL -m 120 "$fallback" -o /tmp/redis.tar.gz; then
      echo "[$(date +%H:%M:%S)] [ERROR] TYPE=SOURCE_DOWNLOAD_FAILED FIX=Set REDIS_CLI_BIN_URL or check network"
      return 22
    fi
  fi

  tar xzf /tmp/redis.tar.gz -C /tmp || return 20
  (
    cd /tmp/redis-stable
    make redis-cli -j"$(nproc 2>/dev/null || echo 2)" \
      && install -m 755 src/redis-cli /usr/local/bin/redis-cli
  )
  local rc=$?
  rm -rf /tmp/redis-stable /tmp/redis.tar.gz
  return $rc
}

# Strategy 1: Use OS package manager (preferred path)
# Picks correct pkg manager per OS; switches to Aliyun mirror if on Aliyun ECS
# Returns 99 for unrecognized OS (triggers source fallback)
install_by_pkg_manager() {
  local os="$1"
  local ver="$2"
  local is_aliyun="$3"

  case "$os" in
    ubuntu|debian)
      [ "$is_aliyun" = "yes" ] && use_aliyun_apt_mirror
      echo "[$(date +%H:%M:%S)] [INSTALL] pkg_manager=apt pkg=redis-tools"
      apt-get update -qq
      apt-get install -y -qq redis-tools
      return $?
      ;;
    alinux)
      [ "$is_aliyun" = "yes" ] && use_aliyun_yum_mirror
      if command -v dnf >/dev/null; then
        echo "[$(date +%H:%M:%S)] [INSTALL] pkg_manager=dnf pkg=redis os=alinux"
        dnf install -y -q redis
      else
        echo "[$(date +%H:%M:%S)] [INSTALL] pkg_manager=yum pkg=redis os=alinux"
        yum install -y -q redis
      fi
      return $?
      ;;
    anolis)
      [ "$is_aliyun" = "yes" ] && use_aliyun_yum_mirror
      echo "[$(date +%H:%M:%S)] [INSTALL] pkg_manager=dnf pkg=redis os=anolis"
      dnf install -y -q redis 2>/dev/null || yum install -y -q redis
      return $?
      ;;
    centos|rhel)
      [ "$is_aliyun" = "yes" ] && use_aliyun_yum_mirror
      if command -v dnf >/dev/null; then
        echo "[$(date +%H:%M:%S)] [INSTALL] pkg_manager=dnf pkg=redis os=${os}${ver}"
        dnf install -y -q redis
      else
        echo "[$(date +%H:%M:%S)] [INSTALL] pkg_manager=yum pkg=redis os=${os}${ver}"
        yum install -y -q epel-release 2>/dev/null || true
        yum install -y -q redis
      fi
      return $?
      ;;
    fedora)
      echo "[$(date +%H:%M:%S)] [INSTALL] pkg_manager=dnf pkg=redis os=fedora"
      dnf install -y -q redis
      return $?
      ;;
    opensuse*|suse|sles)
      echo "[$(date +%H:%M:%S)] [INSTALL] pkg_manager=zypper pkg=redis os=${os}"
      zypper install -y --no-confirm redis
      return $?
      ;;
    alpine)
      [ "$is_aliyun" = "yes" ] && use_aliyun_apk_mirror
      echo "[$(date +%H:%M:%S)] [INSTALL] pkg_manager=apk pkg=redis os=alpine"
      apk add --no-cache redis
      return $?
      ;;
    *)
      echo "[$(date +%H:%M:%S)] [WARN] OS=${os} not recognized, fallback to source"
      return 99
      ;;
  esac
}

# ============================================================
# Main entry: ensure_redis_cli
# ============================================================
# Algorithm:
#   1. If redis-cli exists AND version >= REQUIRED_VERSION → SKIP (return 0)
#   2. Detect OS + whether on Aliyun ECS
#   3. Try strategies in order until one succeeds:
#        Strategy 0: Offline URL (if REDIS_CLI_BIN_URL set)
#        Strategy 1: OS package manager (auto-uses Aliyun mirror)
#        Strategy 2: Source compilation (auto-installs build tools)
#   4. Verify final installation; collect failure diagnostics if all failed

ensure_redis_cli() {
  local required="${REQUIRED_VERSION:-0.0}"

  echo "[$(date +%H:%M:%S)] [DIAG] PHASE=ensure-redis-cli"
  echo "[$(date +%H:%M:%S)] [DIAG] required_version=${required}"

  # ----- 1. Idempotent check: skip if already satisfied -----
  if command -v redis-cli >/dev/null 2>&1; then
    local version_str current
    version_str=$(redis-cli --version 2>/dev/null)
    current=$(echo "$version_str" | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)

    if [ -n "$current" ] && version_gte "$current" "$required"; then
      echo "[$(date +%H:%M:%S)] [RESULT] SKIP_INSTALL=YES"
      echo "[$(date +%H:%M:%S)] [RESULT] REDIS_CLI_PATH=$(command -v redis-cli)"
      echo "[$(date +%H:%M:%S)] [RESULT] REDIS_CLI_VERSION=${current}"
      return 0
    fi
    echo "[$(date +%H:%M:%S)] [WARN] VERSION_TOO_LOW current=${current:-unknown} required=${required} action=upgrade"
  else
    echo "[$(date +%H:%M:%S)] [DIAG] redis-cli not found in PATH=${PATH}"
  fi

  # ----- 2. Detect environment -----
  local os="unknown" os_ver=""
  if [ -f /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    os="${ID:-unknown}"
    os_ver="${VERSION_ID:-}"
  fi
  local is_aliyun
  is_aliyun=$(detect_aliyun_ecs)
  echo "[$(date +%H:%M:%S)] [DIAG] os=${os} version=${os_ver} aliyun_ecs=${is_aliyun}"

  # ----- 3. Install strategy chain -----
  local install_start install_rc=99
  install_start=$(date +%s)

  # Strategy 0: User-specified offline binary (highest priority if set)
  if [ -n "${REDIS_CLI_BIN_URL:-}" ]; then
    if install_from_offline_url; then
      install_rc=0
    else
      install_rc=22
    fi
  fi

  # Strategy 1: OS package manager
  if [ "$install_rc" -ne 0 ]; then
    set +e
    install_by_pkg_manager "$os" "$os_ver" "$is_aliyun"
    install_rc=$?
    set -e
  fi

  # Strategy 2: Source compilation (only if pkg manager failed and binary not yet present)
  if [ "$install_rc" -ne 0 ] && ! command -v redis-cli >/dev/null 2>&1; then
    echo "[$(date +%H:%M:%S)] [WARN] pkg_manager_failed rc=${install_rc}, trying source build..."
    set +e
    install_from_source
    install_rc=$?
    set -e
  fi

  local install_dur=$(( $(date +%s) - install_start ))
  echo "[$(date +%H:%M:%S)] [DIAG] install_duration=${install_dur}s rc=${install_rc}"

  # ----- 4. Verify -----
  if [ "$install_rc" -eq 0 ] && command -v redis-cli >/dev/null 2>&1; then
    local final_ver
    final_ver=$(redis-cli --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
    echo "[$(date +%H:%M:%S)] [RESULT] INSTALL=SUCCESS"
    echo "[$(date +%H:%M:%S)] [RESULT] REDIS_CLI_PATH=$(command -v redis-cli)"
    echo "[$(date +%H:%M:%S)] [RESULT] REDIS_CLI_VERSION=${final_ver}"

    # Final version still below required → warn but don't block
    if [ -n "$final_ver" ] && ! version_gte "$final_ver" "$required"; then
      echo "[$(date +%H:%M:%S)] [WARN] FINAL_VERSION_BELOW_REQUIRED installed=${final_ver} required=${required}"
    fi
    return 0
  fi

  # ----- 5. Failure diagnostics -----
  echo "[$(date +%H:%M:%S)] [RESULT] INSTALL=FAILED rc=${install_rc}"
  echo "[$(date +%H:%M:%S)] [DIAG] disk_free=$(df -h / 2>/dev/null | tail -1 | awk '{print $4}')"
  echo "[$(date +%H:%M:%S)] [DIAG] mem_free=$(free -h 2>/dev/null | awk '/^Mem:/{print $4}')"
  echo "[$(date +%H:%M:%S)] [DIAG] dns_test=$(getent hosts mirrors.cloud.aliyuncs.com 2>/dev/null | head -1 || echo DNS_FAILED)"
  return "${install_rc:-20}"
}

# ============================================================
# Auto-run policy (explicit opt-in to avoid surprises)
# ============================================================
# This script is designed to be SOURCED or CAT-INLINED, not silently auto-run.
# Auto-run is triggered ONLY by environment variable REDIS_CLI_INSTALL_AUTORUN=1.
#
# Why this design:
#   - When cat-inlined into Cloud Assistant scripts, `${BASH_SOURCE[0]}` vs `${0}`
#     behavior is unreliable across environments (sometimes both empty, sometimes
#     differ). Relying on it caused real bugs where ensure_redis_cli would
#     exit before downstream business logic could run.
#   - Explicit opt-in makes intent clear at the call site.
#
# Usage:
#   1. Source mode (functions only, no auto-run):
#        source redis-cli-install.sh
#        ensure_redis_cli || exit $?
#
#   2. Direct execute mode (auto-run):
#        REDIS_CLI_INSTALL_AUTORUN=1 bash redis-cli-install.sh
#
#   3. Cat-inline mode (functions only, business code calls explicitly):
#        cat redis-cli-install.sh > /tmp/combined.sh
#        echo "ensure_redis_cli || exit \$?" >> /tmp/combined.sh
#        echo "<your business logic>" >> /tmp/combined.sh
#        bash /tmp/combined.sh
#
if [ "${REDIS_CLI_INSTALL_AUTORUN:-0}" = "1" ]; then
  ensure_redis_cli
  exit $?
fi
