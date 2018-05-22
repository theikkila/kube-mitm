import json, sys, os
from subprocess import run
import subprocess
import time

if len(sys.argv) < 3 or sys.argv[1] in ('--help', '-h', 'help'):
    print("Usage: mitm.py <ns> <service>")
    sys.exit(0)

namespace = sys.argv[1]
service = sys.argv[2]
old_svc = run(["kubectl", "-n", namespace, "get", "svc", service, "-o", "json"], stdout=subprocess.PIPE)

k = json.loads(old_svc.stdout)
md = k['metadata']
del md['annotations']
del md['creationTimestamp']
del md['resourceVersion']
del md['selfLink']
del md['uid']

# Set name for the proxy svc
orig_service_name = md['name'] + '-origin'
md['name'] = orig_service_name

spec = k['spec']
del spec['clusterIP']


# Select only first port
port = spec['ports'][0]

# Run pod and redirect to the port
del k['status']
print("Creating origin service to point where the service used to point...")
srv = run(["kubectl", "create", "-f", "-"], input=json.dumps(k).encode('utf8'))


mitmproxy_podname = "mitmproxy-"+service
mitmproxy_pod = {
    "apiVersion": "v1",
    "kind": "Pod",
    "metadata": {
        "labels": {
            "papp": service,
            "proxy": "true"
        },
        "name": mitmproxy_podname,
        "namespace": namespace
    },
    "spec": {
        "containers": [
            {
                "env": [
                    {
                        "name": "PORT",
                        "value": str(port['port'])
                    },
                    {
                        "name": "SERVICE",
                        "value": "http://{}:{}".format(orig_service_name, str(port['port']))
                    }
                ],
                "image": "theikkila/mitmp",
                "imagePullPolicy": "Always",
                "name": "mitmproxy",
                "ports": [
                    {
                        "containerPort": port['port'],
                        "protocol": "TCP"
                    }
                ]
            }
        ],
        "restartPolicy": "Always"
    }
}

print("Spawning mitmproxy and reverse proxying origin service...")

run(["kubectl", "create", "-f", "-"], input=json.dumps(mitmproxy_pod).encode('utf8'))

print("==========================")

run(["kubectl", "get", "pods", "-n", namespace, "-l", "proxy=true,papp="+service])
print("==========================")
print("Mitmproxy should be soon running, waiting 5s before automatic connect with following command:")
cmd = "kubectl port-forward -n {} {} 45455".format(namespace, mitmproxy_podname)
print(cmd)
time.sleep(5)
proxy = subprocess.Popen(cmd, shell=True)
print("Please note, if pod isn't up you have to manually run the command in other console!")

mitm_labels = {"op":"replace", "path":"/spec/selector", "value": {"proxy":"true", "papp":service}}
orig_labels = {"op":"replace", "path":"/spec/selector", "value": spec['selector']}

cmd = ["kubectl", "patch", "-n", namespace, "svc", service, "--type=json", "--patch={}".format(json.dumps([mitm_labels]))]
run(cmd)

print("\n\n\nPatched service! Now you can debug by going to http://localhost:45455\n\n")
ok = input("When you are ready, return to normal by pressing ENTER")

cmd = ["kubectl", "patch", "-n", namespace, "svc", service, "--type=json", "--patch={}".format(json.dumps([orig_labels]))]

run(cmd)

proxy.kill()
run(["kubectl", "delete", "-n", namespace, "pod", mitmproxy_podname])
run(["kubectl", "delete", "-n", namespace, "service", orig_service_name])
