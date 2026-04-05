import os

SPARK_NAMESPACE            = os.environ.get("SPARK_NAMESPACE", "spark")
SPARK_HISTORY_URL          = os.environ.get("SPARK_HISTORY_URL", "http://localhost:32080")
SPARK_HISTORY_EXTERNAL_URL = os.environ.get("SPARK_HISTORY_EXTERNAL_URL", "http://localhost:32080")
DASHBOARD_NAMESPACES       = os.environ.get("DASHBOARD_NAMESPACES", SPARK_NAMESPACE).split(",")