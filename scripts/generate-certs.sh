#!/usr/bin/env bash
# ============================================================================
# Generate self-signed TLS certificates for local development
# ============================================================================
# Usage:  ./scripts/generate-certs.sh [DOMAIN]
#
# Defaults to "local.dev" which matches the Traefik dynamic config.
# Certificates are written to  traefik/certs/
# ============================================================================
set -euo pipefail

DOMAIN="${1:-local.dev}"
CERT_DIR="$(cd "$(dirname "$0")/.." && pwd)/volumes/traefik/certs"

mkdir -p "$CERT_DIR"

echo "==> Generating self-signed certificate for *.${DOMAIN}"

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "${CERT_DIR}/local-key.pem" \
  -out "${CERT_DIR}/local-cert.pem" \
  -subj "/CN=${DOMAIN}" \
  -addext "subjectAltName=DNS:*.${DOMAIN},DNS:${DOMAIN},DNS:mlflow.${DOMAIN},DNS:minio.${DOMAIN},DNS:s3.${DOMAIN},DNS:traefik.${DOMAIN},DNS:localai.${DOMAIN},DNS:chat.${DOMAIN},DNS:label-studio.${DOMAIN}"

chmod 600 "${CERT_DIR}/local-key.pem"

echo "==> Certificates written to ${CERT_DIR}/"
echo "    local-cert.pem  (public)"
echo "    local-key.pem   (private, 600)"
echo ""
echo "Tip: on macOS you can trust the cert system-wide with:"
echo "    sudo security add-trusted-cert -d -r trustRoot \\"
echo "        -k /Library/Keychains/System.keychain ${CERT_DIR}/local-cert.pem"
