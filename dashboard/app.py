from config import SPARK_NAMESPACE, SPARK_HISTORY_URL, DASHBOARD_NAMESPACES, SPARK_HISTORY_EXTERNAL_URL
import requests as req_lib
from flask import Response
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from kubernetes import client, config

app = Flask(__name__, template_folder='templates',
            static_folder='static')
CORS(app)

# Load Kubernetes Config
try:
    config.load_incluster_config()
except config.ConfigException:
    config.load_kube_config()

# NAMESPACE = os.environ.get("SPARK_NAMESPACE", "spark")

core_v1 = client.CoreV1Api()
batch_v1 = client.BatchV1Api()
custom_api = client.CustomObjectsApi()

SPARK_GROUP = "sparkoperator.k8s.io"
SPARK_VERSION = "v1beta2"
SPARK_PLURAL = "sparkapplications"



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
        # spark job pods have spark-role label
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
            "image": body.get("image", "apache/spark:3.5.1"),
            "imagePullPolicy": body.get("imagePullPolicy", "Never"),
            "mainApplicationFile": body["jarPath"],
            "sparkVersion": body.get("sparkVersion","3.5.1"),
            "restartPolicy": {"type": "Never"},
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)