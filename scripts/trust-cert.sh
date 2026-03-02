#!/usr/bin/env bash
# ============================================================================
# Trust the self-signed TLS certificate in the OS certificate store
# ============================================================================
# Usage:  sudo ./scripts/trust-cert.sh [remove]
#
# Supports:
#   - macOS   (security add-trusted-cert / remove-trusted-cert)
#   - RHEL / CentOS / Fedora / Rocky / Alma  (update-ca-trust)
#
# Run without arguments to add trust, or with "remove" to revoke it.
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CERT_FILE="${PROJECT_DIR}/volumes/traefik/certs/local-cert.pem"
ACTION="${1:-add}"

# ── Preflight checks ────────────────────────────────────────────────────────

if [[ ! -f "$CERT_FILE" ]]; then
  echo "Error: Certificate not found at ${CERT_FILE}"
  echo "Run ./scripts/generate-certs.sh first."
  exit 1
fi

if [[ "$EUID" -ne 0 ]]; then
  echo "Error: This script must be run as root (use sudo)."
  echo "  sudo $0 ${ACTION}"
  exit 1
fi

# ── Detect OS ────────────────────────────────────────────────────────────────

detect_os() {
  case "$(uname -s)" in
    Darwin)
      echo "macos"
      ;;
    Linux)
      if [[ -f /etc/redhat-release ]] || grep -qi 'rhel\|centos\|fedora\|rocky\|alma' /etc/os-release 2>/dev/null; then
        echo "rhel"
      else
        echo "linux-unknown"
      fi
      ;;
    *)
      echo "unknown"
      ;;
  esac
}

OS="$(detect_os)"

# ── macOS ────────────────────────────────────────────────────────────────────

macos_add() {
  echo "==> [macOS] Adding certificate to System keychain..."
  security add-trusted-cert -d -r trustRoot \
    -k /Library/Keychains/System.keychain "$CERT_FILE"
  echo "    Done. Certificate is now trusted system-wide."
  echo "    You may need to restart your browser for it to take effect."
}

macos_remove() {
  echo "==> [macOS] Removing certificate from System keychain..."
  security remove-trusted-cert -d "$CERT_FILE" 2>/dev/null || true
  local sha1
  sha1=$(openssl x509 -in "$CERT_FILE" -noout -fingerprint -sha1 2>/dev/null | cut -d= -f2 | tr -d ':')
  if [[ -n "$sha1" ]]; then
    security delete-certificate -Z "$sha1" /Library/Keychains/System.keychain 2>/dev/null || true
  fi
  echo "    Done. Certificate trust removed."
}

# ── RHEL / CentOS / Fedora / Rocky / Alma ────────────────────────────────────

RHEL_TRUST_DIR="/etc/pki/ca-trust/source/anchors"
RHEL_CERT_NAME="mlflow-quick-stack-local.pem"

rhel_add() {
  echo "==> [RHEL] Adding certificate to ${RHEL_TRUST_DIR}..."
  if ! command -v update-ca-trust &>/dev/null; then
    echo "    Installing ca-certificates..."
    dnf install -y ca-certificates 2>/dev/null || yum install -y ca-certificates
  fi
  cp "$CERT_FILE" "${RHEL_TRUST_DIR}/${RHEL_CERT_NAME}"
  chmod 644 "${RHEL_TRUST_DIR}/${RHEL_CERT_NAME}"
  update-ca-trust extract
  echo "    Done. Certificate is now in the system trust store."
  echo "    Verify with: trust list | grep -i 'local.dev'"
}

rhel_remove() {
  echo "==> [RHEL] Removing certificate from ${RHEL_TRUST_DIR}..."
  if [[ -f "${RHEL_TRUST_DIR}/${RHEL_CERT_NAME}" ]]; then
    rm -f "${RHEL_TRUST_DIR}/${RHEL_CERT_NAME}"
    update-ca-trust extract
    echo "    Done. Certificate removed from trust store."
  else
    echo "    Certificate not found in trust store — nothing to remove."
  fi
}

# ── Dispatch ─────────────────────────────────────────────────────────────────

case "${OS}" in
  macos)
    case "${ACTION}" in
      add)    macos_add ;;
      remove) macos_remove ;;
      *)      echo "Usage: sudo $0 [add|remove]"; exit 1 ;;
    esac
    ;;
  rhel)
    case "${ACTION}" in
      add)    rhel_add ;;
      remove) rhel_remove ;;
      *)      echo "Usage: sudo $0 [add|remove]"; exit 1 ;;
    esac
    ;;
  linux-unknown)
    echo "Error: Unsupported Linux distribution."
    echo "This script supports RHEL, CentOS, Fedora, Rocky Linux, and AlmaLinux."
    echo ""
    echo "For Debian/Ubuntu, manually run:"
    echo "  sudo cp ${CERT_FILE} /usr/local/share/ca-certificates/mlflow-quick-stack.crt"
    echo "  sudo update-ca-certificates"
    exit 1
    ;;
  *)
    echo "Error: Unsupported operating system: $(uname -s)"
    exit 1
    ;;
esac
