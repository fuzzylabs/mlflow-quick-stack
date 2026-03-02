#!/usr/bin/env bash
# ============================================================================
# Manage /etc/hosts entries for MLflow Quick Stack
# ============================================================================
# Usage:
#   ./scripts/hosts.sh add       # Add entries (requires sudo)
#   ./scripts/hosts.sh remove    # Remove entries (requires sudo)
#   ./scripts/hosts.sh status    # Check if entries exist
# ============================================================================
set -euo pipefail

DOMAINS=(
  "mlflow.local.dev"
  "minio.local.dev"
  "s3.local.dev"
  "traefik.local.dev"
)

MARKER="# mlflow-quick-stack"
HOSTS_FILE="/etc/hosts"

add_entries() {
  for domain in "${DOMAINS[@]}"; do
    if grep -q "$domain" "$HOSTS_FILE" 2>/dev/null; then
      echo "  ✓ $domain already exists"
    else
      echo "127.0.0.1  $domain  $MARKER" | sudo tee -a "$HOSTS_FILE" > /dev/null
      echo "  + $domain added"
    fi
  done
  echo ""
  echo "Done. Services available at:"
  echo "  https://mlflow.local.dev"
  echo "  https://minio.local.dev"
  echo "  https://s3.local.dev"
  echo "  https://traefik.local.dev"
}

remove_entries() {
  if grep -q "$MARKER" "$HOSTS_FILE" 2>/dev/null; then
    sudo sed -i.bak "/$MARKER/d" "$HOSTS_FILE"
    sudo rm -f "${HOSTS_FILE}.bak"
    echo "  ✓ All mlflow-quick-stack entries removed from $HOSTS_FILE"
  else
    echo "  – No mlflow-quick-stack entries found"
  fi
}

status() {
  echo "Checking $HOSTS_FILE for mlflow-quick-stack entries:"
  echo ""
  local found=0
  for domain in "${DOMAINS[@]}"; do
    if grep -q "$domain" "$HOSTS_FILE" 2>/dev/null; then
      echo "  ✓ $domain"
      found=1
    else
      echo "  ✗ $domain (missing)"
    fi
  done
  echo ""
  if [[ $found -eq 1 ]]; then
    echo "At least some entries exist. Run '$0 remove' to clean up."
  else
    echo "No entries found. Run '$0 add' to set up."
  fi
}

case "${1:-}" in
  add)
    echo "Adding /etc/hosts entries (may require password)..."
    add_entries
    ;;
  remove)
    echo "Removing /etc/hosts entries (may require password)..."
    remove_entries
    ;;
  status)
    status
    ;;
  *)
    echo "Usage: $0 {add|remove|status}"
    exit 1
    ;;
esac
