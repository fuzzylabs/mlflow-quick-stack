#!/usr/bin/env python3
"""
Example: Create an MLflow experiment, log parameters/metrics/artifacts,
then verify the artifact landed in the MinIO S3 bucket.

Prerequisites:
    pip install mlflow boto3

Usage:
    python examples/experiment_with_s3_validation.py

What it does:
    1. Creates (or reuses) an experiment called "quick-stack-demo"
    2. Starts a run and logs parameters, metrics, and a text artifact
    3. Queries the run back via the MLflow API
    4. Lists objects in the MinIO S3 bucket to confirm the artifact was stored
    5. Prints a pass/fail summary
"""

import json
import sys
import tempfile
from pathlib import Path

import mlflow

# ── Setup ────────────────────────────────────────────────────────────────────

# Allow running from the project root or from examples/
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import configure_mlflow, get_s3_client, S3_BUCKET

tracking_uri = configure_mlflow()
print(f"MLflow tracking URI : {tracking_uri}")
print(f"S3 bucket           : {S3_BUCKET}")
print()

# ── 1. Create experiment ─────────────────────────────────────────────────────

EXPERIMENT_NAME = "quick-stack-demo"
mlflow.set_experiment(EXPERIMENT_NAME)
experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
print(f"[1/5] Experiment '{EXPERIMENT_NAME}' (id={experiment.experiment_id})")

# ── 2. Run: log params, metrics, and an artifact ────────────────────────────

print("[2/5] Starting a run...")

with mlflow.start_run(run_name="demo-run") as run:
    # Parameters
    mlflow.log_param("model_type", "random-forest")
    mlflow.log_param("n_estimators", 100)
    mlflow.log_param("max_depth", 10)

    # Metrics (log a few steps to show metric history)
    for step in range(5):
        mlflow.log_metric("accuracy", 0.80 + step * 0.03, step=step)
        mlflow.log_metric("loss", 0.50 - step * 0.08, step=step)

    # Artifact: a small JSON file
    artifact_content = {
        "description": "MLflow Quick Stack demo artifact",
        "model_config": {
            "model_type": "random-forest",
            "n_estimators": 100,
            "max_depth": 10,
        },
        "metrics_summary": {
            "final_accuracy": 0.92,
            "final_loss": 0.18,
        },
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_path = Path(tmpdir) / "model_config.json"
        artifact_path.write_text(json.dumps(artifact_content, indent=2))
        mlflow.log_artifact(str(artifact_path), artifact_path="config")

    run_id = run.info.run_id
    print(f"      Run ID: {run_id}")

# ── 3. Query the run back ───────────────────────────────────────────────────

print("[3/5] Querying run from MLflow API...")
fetched_run = mlflow.get_run(run_id)
assert fetched_run.info.status == "FINISHED", f"Run status: {fetched_run.info.status}"
assert fetched_run.data.params["model_type"] == "random-forest"
assert float(fetched_run.data.metrics["accuracy"]) == 0.92
print(f"      Status: {fetched_run.info.status}")
print(f"      Params: {dict(fetched_run.data.params)}")
print(f"      Metrics: {dict(fetched_run.data.metrics)}")

# ── 4. List artifacts in MLflow ──────────────────────────────────────────────

print("[4/5] Listing artifacts via MLflow...")
client = mlflow.tracking.MlflowClient()
artifacts = client.list_artifacts(run_id)
artifact_names = [a.path for a in artifacts]
print(f"      Artifacts: {artifact_names}")
assert "config" in artifact_names, "Expected 'config' artifact directory"

config_files = client.list_artifacts(run_id, path="config")
config_names = [a.path for a in config_files]
print(f"      config/: {config_names}")
assert any("model_config.json" in name for name in config_names), \
    "Expected model_config.json in config/ artifact directory"

# ── 5. Validate directly in S3 / MinIO ──────────────────────────────────────

print("[5/5] Checking S3 bucket for artifact files...")
s3 = get_s3_client()

# List objects under the experiment's artifact path
prefix = f"{experiment.experiment_id}/{run_id}/artifacts/config/"
response = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)

s3_keys = [obj["Key"] for obj in response.get("Contents", [])]
print(f"      S3 prefix: s3://{S3_BUCKET}/{prefix}")
print(f"      S3 objects: {s3_keys}")

assert len(s3_keys) > 0, f"No objects found in S3 under {prefix}"
assert any("model_config.json" in key for key in s3_keys), \
    "model_config.json not found in S3"

# ── Summary ──────────────────────────────────────────────────────────────────

print()
print("=" * 60)
print("  ALL CHECKS PASSED")
print("=" * 60)
print(f"  Experiment : {EXPERIMENT_NAME}")
print(f"  Run ID     : {run_id}")
print(f"  Params     : {len(fetched_run.data.params)} logged")
print(f"  Metrics    : {len(fetched_run.data.metrics)} logged")
print(f"  Artifacts  : {len(s3_keys)} file(s) in S3")
print(f"  S3 bucket  : s3://{S3_BUCKET}/{prefix}")
print("=" * 60)
