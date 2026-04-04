import os
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from kubernetes import client, config

app = Flask(__name__, template_folder='templates')
CORS(app)

# Load Kubernetes Config
try:
    config.load_incluster_config()
except config.ConfigException:
    config.load_kube_config()

NAMESPACE = os.environ.get("SPARK_NAMESPACE", "spark")

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
    ns = request.args.get("namespace", NAMESPACE)
    pods = core_v1.list_namespaced_pod(namespace=ns)
    result= []
    for pod in pods.items:
        result.append({
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "status": pod.status.phase,
            "node": pod.spec.node_name,
            "created": pod.metadata.creation_timestamp.isoformat()
                       if pod.metadata.creation_timestamp else None,
            "labels": pod.metadata.labels or {}
        })
    return jsonify(result)

@app.route('/api/pods/<name>/logs')
def get_pod_logs(name):
    ns = request.args.get("namespace", NAMESPACE)
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
    ns = request.args.get("namespace", NAMESPACE)
    core_v1.delete_namespaced_pod(name=name, namespace=ns)
    return jsonify({"deleted": name})

@app.route('/api/namespace')
def list_namespace():
    ns_list = core_v1.list_namespace()
    return jsonify([ns.metadata.name for ns in ns_list.items])

@app.route('/api/spark-apps')
def list_spark_apps():
    ns = request.args.get("namespace", NAMESPACE)
    try:
        resp = custom_api.list_cluster_custom_object(
            group=SPARK_GROUP,
            version=SPARK_VERSION,
            namespace=ns,
            plural=SPARK_PLURAL
        )
        result = []
        for item in resp.items("items", []):
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
    ns = body.get("namespace", NAMESPACE)
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
            "imagePullPolicy": "IfNotPresent",
            "mainApplicationFile": body["jarPath"],
            "sparkVersion": body.get("sparkVersion","3.5.1"),
            "restartPolicy": {"type": "Never"},
            "driver": {
                "cores": int(body.get("driverCores",1)),
                "memory": body.get("driverMemory","512m"),
                "serviceAccount": "spark"
            },
            "executor": {
                "cores": int(body["executorCores",1]),
                "instances": int(body["executorInstances",1]),
                "memory": body.get("executorMemory","512m")
            }
        }
    }

    if body.get("mainClass"):
        spark_app["spec"]["mainClass"] = body["mainClass"]

    return jsonify({"submitted": body["name"]}), 201

@app.route('/api/spark-apps/<name>', methods=["DELETE"])
def delete_spark_app(name):
    ns = request.args.get("namespace", NAMESPACE)
    custom_api.delete_namespaced_custom_object(
        group=SPARK_GROUP,
        version=SPARK_VERSION,
        namespace=ns,
        plural=SPARK_PLURAL,
        name=name
    )
    return jsonify({"deleted": name})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)