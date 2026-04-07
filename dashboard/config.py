import os

SPARK_NAMESPACE            = os.environ.get("SPARK_NAMESPACE", "spark")
SPARK_HISTORY_URL          = os.environ.get("SPARK_HISTORY_URL", "http://localhost:32080")
SPARK_HISTORY_EXTERNAL_URL = os.environ.get("SPARK_HISTORY_EXTERNAL_URL", "http://localhost:32080")
DASHBOARD_NAMESPACES       = os.environ.get("DASHBOARD_NAMESPACES", SPARK_NAMESPACE).split(",")

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "localhost:32090")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "sparkadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "sparkadmin123")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "spark-jobs")
MINIO_EXTERNAL_URL = os.environ.get("MINIO_EXTERNAL_URL", "https://minio.codelabuk.dev/")

# Internal MinIO endpoint for Spark driver/executor pods
MINIO_SPARK_ENDPOINT = os.environ.get(
    "MINIO_SPARK_ENDPOINT",
    "http://minio.minio.svc.cluster.local:9000"
)