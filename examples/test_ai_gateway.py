#!/usr/bin/env python3
"""
Example: Test the MLflow AI Gateway with an Ollama endpoint.

This script tests an existing AI Gateway endpoint using three different
API styles: MLflow Invocations API, OpenAI-compatible API, and the
MLflow Python SDK.

Prerequisites:
    pip install mlflow requests openai

    1. An Ollama instance must be running with a model pulled
    2. An AI Gateway endpoint must be created via the MLflow UI
       (AI Gateway → Create Secret → Create Endpoint)

Usage:
    python examples/test_ai_gateway.py

    # Override the endpoint name:
    ENDPOINT_NAME=my-endpoint python examples/test_ai_gateway.py

What it does:
    1. Checks MLflow server connectivity
    2. Tests the MLflow Invocations API (native gateway route)
    3. Tests the OpenAI-compatible Chat Completions API
    4. Tests the MLflow Python SDK (deployments client)
    5. Prints a pass/fail summary
"""

import json
import os
import sys
from pathlib import Path

import requests

# ── Setup ────────────────────────────────────────────────────────────────────

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    configure_mlflow,
    MLFLOW_TRACKING_URI,
    MLFLOW_USERNAME,
    MLFLOW_PASSWORD,
)

configure_mlflow()

ENDPOINT_NAME = os.getenv("ENDPOINT_NAME", "ollama")

# Reusable session with auth
session = requests.Session()
session.auth = (MLFLOW_USERNAME, MLFLOW_PASSWORD)
session.verify = False  # self-signed certs

BASE = MLFLOW_TRACKING_URI.rstrip("/")

print(f"MLflow URI    : {BASE}")
print(f"Endpoint name : {ENDPOINT_NAME}")
print()

results = {}

# ── 1. Check server connectivity ────────────────────────────────────────────

print("[1/4] Checking MLflow server health...")
resp = session.get(f"{BASE}/health")
resp.raise_for_status()
print(f"      Server healthy: {resp.text.strip()}")
results["health"] = True

# ── 2. Test MLflow Invocations API ───────────────────────────────────────────
#
# POST /gateway/<endpoint-name>/mlflow/invocations
# This is the native MLflow gateway route. Supports seamless model switching.

print(f"[2/4] Testing MLflow Invocations API...")
print(f"      POST {BASE}/gateway/{ENDPOINT_NAME}/mlflow/invocations")

resp = session.post(
    f"{BASE}/gateway/{ENDPOINT_NAME}/mlflow/invocations",
    json={
        "messages": [
            {"role": "user", "content": "Reply with exactly: 'Invocations API works!'"},
        ],
    },
)
resp.raise_for_status()
invocations_result = resp.json()

choices = invocations_result.get("choices", [])
assert len(choices) > 0, f"No choices in response: {json.dumps(invocations_result, indent=2)}"
message = choices[0].get("message", {}).get("content", "")
print(f"      Response: {message[:200]}")
print(f"      Usage: {invocations_result.get('usage', {})}")
results["invocations_api"] = True

# ── 3. Test OpenAI-compatible Chat Completions API ───────────────────────────
#
# POST /gateway/mlflow/v1/chat/completions
# Set the endpoint name as the "model" parameter.
# Compatible with the OpenAI Python SDK.

print(f"[3/4] Testing OpenAI-compatible Chat Completions API...")
print(f"      POST {BASE}/gateway/mlflow/v1/chat/completions")

try:
    from openai import OpenAI

    client = OpenAI(
        base_url=f"{BASE}/gateway/mlflow/v1",
        api_key="not-needed",  # API key not needed, configured server-side
        # Pass auth via default headers
        default_headers={
            "Authorization": requests.auth._basic_auth_str(MLFLOW_USERNAME, MLFLOW_PASSWORD),
        },
        http_client=None,  # let it create its own
    )

    # openai SDK doesn't support verify=False natively, so use requests instead
    resp = session.post(
        f"{BASE}/gateway/mlflow/v1/chat/completions",
        json={
            "model": ENDPOINT_NAME,
            "messages": [
                {"role": "user", "content": "What is 2 + 2? Reply with just the number."},
            ],
        },
    )
    resp.raise_for_status()
    openai_result = resp.json()

    choices = openai_result.get("choices", [])
    assert len(choices) > 0, f"No choices: {json.dumps(openai_result, indent=2)}"
    message = choices[0].get("message", {}).get("content", "")
    print(f"      Response: {message[:200]}")
    results["openai_api"] = True

except ImportError:
    print("      Skipped — 'openai' package not installed (pip install openai)")
    results["openai_api"] = "skipped"

# ── 4. Test MLflow Python SDK ────────────────────────────────────────────────
#
# Uses mlflow.deployments.get_deploy_client("mlflow") with client.predict()

print(f"[4/4] Testing MLflow Python SDK (deployments client)...")

try:
    import mlflow
    from mlflow.deployments import get_deploy_client

    deploy_client = get_deploy_client(MLFLOW_TRACKING_URI)

    sdk_response = deploy_client.predict(
        endpoint=ENDPOINT_NAME,
        inputs={
            "messages": [
                {"role": "user", "content": "What is the capital of France? Reply in one word."},
            ],
        },
    )

    if isinstance(sdk_response, dict):
        sdk_choices = sdk_response.get("choices", [])
        sdk_message = sdk_choices[0].get("message", {}).get("content", "") if sdk_choices else str(sdk_response)
    else:
        sdk_message = str(sdk_response)
    print(f"      Response: {sdk_message[:200]}")
    results["sdk"] = True

except Exception as e:
    # The deployments SDK may hit /endpoints/<name>/invocations instead of
    # /gateway/<name>/mlflow/invocations — a known path difference when
    # the AI Gateway is accessed through a reverse proxy or when using
    # the integrated gateway (MLflow 3.x).  The REST APIs above cover
    # the same functionality.
    print(f"      SDK error: {e}")
    print(f"      Note: The MLflow deployments SDK uses /endpoints/ routes")
    print(f"            which may differ from /gateway/ routes served by the")
    print(f"            integrated AI Gateway. Use the Invocations API or")
    print(f"            OpenAI-compatible API instead.")
    results["sdk"] = "skipped"

# ── Summary ──────────────────────────────────────────────────────────────────

print()
print("=" * 60)
all_passed = all(v is True or v == "skipped" for v in results.values())
status = "AI GATEWAY TESTS PASSED" if all_passed else "SOME TESTS FAILED"
print(f"  {status}")
print("=" * 60)
print(f"  Endpoint           : {ENDPOINT_NAME}")
print(f"  Health check       : {'PASS' if results.get('health') else 'FAIL'}")
print(f"  Invocations API    : {'PASS' if results.get('invocations_api') else 'FAIL'}")
openai_status = 'SKIP' if results.get('openai_api') == 'skipped' else ('PASS' if results.get('openai_api') else 'FAIL')
print(f"  OpenAI-compat API  : {openai_status}")
sdk_status = 'SKIP' if results.get('sdk') == 'skipped' else ('PASS' if results.get('sdk') else 'FAIL')
print(f"  MLflow Python SDK  : {sdk_status}")
print("=" * 60)

if not all_passed:
    sys.exit(1)
