import io
import os

from flask import Response, Flask, jsonify, request, render_template
from flask_cors import CORS
from kubernetes import client, config
from minio import Minio
import requests as req_lib

from config import (SPARK_NAMESPACE, SPARK_HISTORY_URL, DASHBOARD_NAMESPACES,
                    SPARK_HISTORY_EXTERNAL_URL, MINIO_ENDPOINT, MINIO_ACCESS_KEY,
                    MINIO_SECRET_KEY, MINIO_BUCKET, MINIO_SPARK_ENDPOINT)

app = Flask(__name__, template_folder='templates',
            static_folder='static')
CORS(app)

# Load Kubernetes Config
try:
    config.load_incluster_config()
except config.ConfigException:
    config.load_kube_config()

core_v1 = client.CoreV1Api()
batch_v1 = client.BatchV1Api()
custom_api = client.CustomObjectsApi()

SPARK_GROUP = "sparkoperator.k8s.io"
SPARK_VERSION = "v1beta2"
SPARK_PLURAL = "sparkapplications"


def get_minio():
    return Minio(MINIO_ENDPOINT, access_key=MINIO_ACCESS_KEY,
                 secret_key=MINIO_SECRET_KEY, secure=False)

def ensure_bucket():
    mc = get_minio()
    if not mc.bucket_exists(MINIO_BUCKET):
        mc.make_bucket(MINIO_BUCKET)



@app.route('/')
def index():
    return render_template("index.html")

# ---------------------------health API -------------------
@app.route('/health')
def health():
    return jsonify({"status": "ok"})


# -------------------------Pod API ------------------------
@app.route('/api/pods')
def get_pods():
    ns = request.args.get("namespace", SPARK_NAMESPACE)
    pods = core_v1.list_namespaced_pod(namespace=ns)
    spark_jobs = []
    infrastructure = []
    for pod in pods.items:
        labels = pod.metadata.labels or {}
        pod_data = {
            "name":      pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "status":    pod.status.phase,
            "node":      pod.spec.node_name,
            "created":   pod.metadata.creation_timestamp.isoformat()
                         if pod.metadata.creation_timestamp else None,
            "labels":    labels
        }
        if "spark-role" in labels or "spark-app-name" in labels:
            spark_jobs.append(pod_data)
        else:
            infrastructure.append(pod_data)

    return jsonify({
        "sparkJobs": spark_jobs,
        "infrastructure": infrastructure,
        "all": spark_jobs + infrastructure
    })

@app.route('/api/pods/<name>/logs')
def get_pod_logs(name):
    ns = request.args.get("namespace", SPARK_NAMESPACE)
    try:
        logs = core_v1.read_namespaced_pod_log(
            name=name,
            namespace=ns,
            tail_lines=200
        )
        return jsonify({"logs": logs})
    except Exception as e:
        return jsonify({"logs":"", "error": str(e)}), 200


@app.route('/api/pods/<name>', methods=["DELETE"])
def delete_pod(name):
    ns = request.args.get("namespace", SPARK_NAMESPACE)
    core_v1.delete_namespaced_pod(name=name, namespace=ns)
    return jsonify({"deleted": name})

@app.route('/api/namespaces')
def list_namespace():
    return jsonify(DASHBOARD_NAMESPACES)

@app.route('/api/spark-apps')
def list_spark_apps():
    ns = request.args.get("namespace", SPARK_NAMESPACE)
    try:
        resp = custom_api.list_namespaced_custom_object(
            group=SPARK_GROUP,
            version=SPARK_VERSION,
            namespace=ns,
            plural=SPARK_PLURAL
        )
        result = []
        for item in resp.get("items", []):
            state = item.get("status", {}).get("applicationState",{})
            result.append({
                "name": item["metadata"]["name"],
                "namespace": item["metadata"]["namespace"],
                "state": state.get("state", "UNKNOWN"),
                "message": state.get("errorMessage", ""),
                "type": item["spec"].get("type"),
                "image": item["spec"].get("image"),
                "created": item["metadata"].get("creationTimestamp"),
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e), "items": []}), 200


@app.route('/api/spark-apps', methods=["POST"])
def submit_spark_app():
    body = request.json
    ns = body.get("namespace", SPARK_NAMESPACE)
    # s3a config
    spark_conf = {
        "spark.hadoop.fs.s3a.endpoint": MINIO_SPARK_ENDPOINT,
        "spark.hadoop.fs.s3a.access.key": MINIO_ACCESS_KEY,
        "spark.hadoop.fs.s3a.secret.key": MINIO_SECRET_KEY,
        "spark.hadoop.fs.s3a.path.style.access": "true",
        "spark.hadoop.fs.s3a.impl": "org.apache.hadoop.fs.s3a.S3AFileSystem",
        "spark.hadoop.fs.s3a.aws.credentials.provider":
                "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
        "spark.eventLog.enabled": "true",
        "spark.hadoop.fs.s3a.connection.ssl.enabled": "false",
        "spark.eventLog.dir": "s3a://" + MINIO_BUCKET + "/event-logs",
    }
    if body.get("sparkConf"):
        spark_conf.update(body["sparkConf"])

    spark_app = {
        "apiVersion": f"{SPARK_GROUP}/{SPARK_VERSION}",
        "kind": "SparkApplication",
        "metadata": {
            "name": body["name"],
            "namespace": ns
        },
        "spec": {
            "type": body.get("type", "Scala"),
            "mode": "cluster",
            "image": body.get("image", "spark-jobs:latest"),
            "imagePullPolicy": body.get("imagePullPolicy", "Never"),
            "mainApplicationFile": body["jarPath"],
            "sparkVersion": body.get("sparkVersion","3.5.3"),
            "restartPolicy": {"type": "Never"},
            "sparkConf": spark_conf,
            "driver": {
                "cores": int(body.get("driverCores",1)),
                "memory": body.get("driverMemory","512m"),
                "serviceAccount": "spark"
            },
            "executor": {
                "cores": int(body.get("executorCores",1)),
                "instances": int(body.get("executorInstances",1)),
                "memory": body.get("executorMemory","512m")
            }
        }
    }

    print(f"spark app submitted: {spark_app}")

    if body.get("mainClass"):
        spark_app["spec"]["mainClass"] = body["mainClass"]

    custom_api.create_namespaced_custom_object(
        group=SPARK_GROUP,
        version=SPARK_VERSION,
        namespace=ns,
        plural=SPARK_PLURAL,
        body=spark_app
    )

    return jsonify({"submitted": body["name"]}), 201

@app.route('/api/spark-apps/<name>', methods=["DELETE"])
def delete_spark_app(name):
    ns = request.args.get("namespace", SPARK_NAMESPACE)
    custom_api.delete_namespaced_custom_object(
        group=SPARK_GROUP,
        version=SPARK_VERSION,
        namespace=ns,
        plural=SPARK_PLURAL,
        name=name
    )
    return jsonify({"deleted": name})

@app.route('/api/files')
def list_files():
    try:
        ensure_bucket()
        mc = get_minio()
        prefix = request.args.get("prefix", "jobs/")
        objects = mc.list_objects(MINIO_BUCKET, prefix=prefix, recursive=True)
        files = []
        for obj in objects:
            files.append({
                "name": obj.object_name,
                "size": obj.size,
                "lastModified": obj.last_modified.isoformat() if obj.last_modified else None,
                "s3aPath": "s3a://" + MINIO_BUCKET + "/" + obj.object_name,
            })
        return jsonify(files)
    except Exception as e:
        return jsonify({"error": str(e)}), 200


@app.route('/api/files/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "no file in request"}), 400
    f = request.files['file']
    if not f.filename:
        return jsonify({"error": "Empty Filename"}), 400
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ('.py', '.jar'):
        return jsonify({"error": "Invalid Extension"}), 400
    object_name = "jobs/" + f.filename
    data = f.read()
    content_type = "text/x-python" if ext == '.py' else "application/octet-stream"
    try:
        ensure_bucket()
        mc = get_minio()
        mc.put_object(MINIO_BUCKET, object_name, io.BytesIO(data),
                      length=len(data), content_type=content_type)
        return jsonify({
            "uploaded": f.filename,
            "s3aPath": "s3a://" + MINIO_BUCKET + "/" + object_name,
            "size": len(data),
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/files/<path:object_name>', methods=["DELETE"])
def delete_file(object_name):
    try:
        mc = get_minio()
        mc.remove_object(MINIO_BUCKET, object_name)
        return jsonify({"deleted": object_name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/minio/status')
def minio_status():
    try:
        ensure_bucket()
        mc = get_minio()
        buckets = [b.name for b in mc.list_buckets()]
        return jsonify({"status": "ok", "buckets": buckets})
    except Exception as e:
        return jsonify({"error": str(e)}), 200


@app.route('/api/config')
def get_config():
    return jsonify({
        "defaultNamespace": SPARK_NAMESPACE,
        "historyServerUrl": SPARK_HISTORY_URL,
        "historyExternalUrl": SPARK_HISTORY_EXTERNAL_URL,
        "namespaces": DASHBOARD_NAMESPACES
    })

@app.route('/proxy/history/')
@app.route('/proxy/history/<path:subpath>')
def proxy_history(subpath=''):
    target = f"{SPARK_HISTORY_URL}/{subpath}"
    if request.query_string:
        target += '?' + request.query_string.decode()
    try:
        resp = req_lib.get(target, timeout=5, stream=True)
        content_type = resp.headers.get('Content-Type', 'text/html')
        content = resp.content
        if 'text/html' in content_type:
            content = content \
                .replace(b'href="/', b'href="/proxy/history/') \
                .replace(b'src="/',  b'src="/proxy/history/')  \
                .replace(b'action="/', b'action="/proxy/history/')
        return Response(content, status=resp.status_code,
                        content_type=content_type)
    except Exception as e:
        return f"<p>History server unavailable: {e}</p>", 503

@app.route('/proxy/spark-ui/<pod_name>/<path:path>')
@app.route('/proxy/spark-ui/<pod_name>/')
@app.route('/proxy/spark-ui/<pod_name>')
def proxy_spark_ui(pod_name, path=''):
    namespace = request.args.get('namespace', SPARK_NAMESPACE)

    target_url = f"http://{pod_name}.{namespace}.svc.cluster.local:4040/{path}"

    if request.query_string:
        target_url += '?' + request.query_string.decode('utf-8')

    try:
        resp = req_lib.request(
            method=request.method,
            url=target_url,
            headers={k: v for k, v in request.headers if k.lower() != 'host'},
            data=request.get_data(),
            allow_redirects=False,
            timeout=30
        )

        headers = [(k, v) for k, v in resp.headers.items()
                   if k.lower() not in ('transfer-encoding', 'connection')]

        if 'Location' in resp.headers:
            location = resp.headers['Location']
            if location.startswith('http'):
                location = location.replace(
                    f"http://{pod_name}.{namespace}.svc.cluster.local:4040",
                    f"/proxy/spark-ui/{pod_name}"
                )
            headers = [(k, v if k != 'Location' else location) for k, v in headers]

        return Response(
            resp.content,
            status=resp.status_code,
            headers=headers
        )

    except Exception as e:
        return jsonify({
            "error": f"Cannot connect to Spark UI for pod {pod_name}",
            "details": str(e),
            "pod": pod_name,
            "namespace": namespace
        }), 502

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)