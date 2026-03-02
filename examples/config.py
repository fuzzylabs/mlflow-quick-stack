"""
Shared configuration for MLflow Quick Stack examples.

Reads connection details from environment variables with sensible defaults
matching the stock .env.example values.

Usage:
    from config import configure_mlflow, S3_ENDPOINT_URL, S3_BUCKET
"""

import os
import urllib3

# ── MLflow connection ────────────────────────────────────────────────────────

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "https://mlflow.local.dev")
MLFLOW_USERNAME = os.getenv("MLFLOW_TRACKING_USERNAME", "admin")
MLFLOW_PASSWORD = os.getenv("MLFLOW_TRACKING_PASSWORD", "admin-s3cr3t!")

# ── S3 / MinIO connection ───────────────────────────────────────────────────

S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "https://s3.local.dev")
S3_BUCKET = os.getenv("S3_BUCKET_MLFLOW", "mlflow")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "minio-s3cr3t!")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")


def configure_mlflow():
    """
    Set up MLflow environment variables and return the tracking URI.
    Call this before any mlflow.* operations.
    """
    import mlflow

    os.environ["MLFLOW_TRACKING_USERNAME"] = MLFLOW_USERNAME
    os.environ["MLFLOW_TRACKING_PASSWORD"] = MLFLOW_PASSWORD
    os.environ["MLFLOW_TRACKING_INSECURE_TLS"] = "true"  # self-signed certs

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

    # Suppress only the InsecureRequestWarning from urllib3 (self-signed certs)
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    return MLFLOW_TRACKING_URI


def get_s3_client():
    """
    Return a boto3 S3 client pointed at MinIO.
    """
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT_URL,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_DEFAULT_REGION,
        verify=False,  # self-signed certs
    )
