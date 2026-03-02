ARG MLFLOW_VERSION=v3.10.0
FROM ghcr.io/mlflow/mlflow:${MLFLOW_VERSION}

RUN pip install --no-cache-dir \
    psycopg2-binary \
    boto3 \
    "mlflow[genai]" \
    "mlflow[auth]"
