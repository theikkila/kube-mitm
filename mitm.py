import json, sys, os
from subprocess import run
import subprocess
import time

if len(sys.argv) < 3 or sys.argv[1] in ('--help', '-h', 'help'):
    print("Usage: mitm.py <ns> <service> <http|https>")
    sys.exit(0)

namespace = sys.argv[1]
service = sys.argv[2]
svc_protocol = sys.argv[3]
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


# Select all ports
ports = [str(p['port']) for p in spec['ports']]


# Run pod and redirect to the port
del k['status']
print("Creating origin service to point where the service used to point...")
srv = run(["kubectl", "create", "-f", "-"], input=json.dumps(k).encode('utf8'))

def get_mitmproxy_pod_status(namespace, service):
    print("==========================")
    run(["kubectl", "get", "pods", "-n", namespace, "-l", "proxy=true,papp="+service])
    print("==========================")


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
                        "name": "PORTS",
                        "value": str(" ".join(ports))
                    },
                    {
                        "name": "SERVICE",
                        "value": "{}://{}".format(svc_protocol, orig_service_name)
                    }
                ],
                "image": "theikkila/mitmp",
                "imagePullPolicy": "Always",
                "name": "mitmproxy",
                "ports": [{"containerPort": int(p), "protocol": "TCP"} for p in ports]
            }
        ],
        "restartPolicy": "Always"
    }
}

print("Spawning mitmproxy and reverse proxying origin service...")

run(["kubectl", "create", "-f", "-"], input=json.dumps(mitmproxy_pod).encode('utf8'))
print("Mitmproxy should be soon running, waiting 10s before automatic connect with following command:")
get_mitmproxy_pod_status(namespace, service)
time.sleep(5)
get_mitmproxy_pod_status(namespace, service)
time.sleep(5)
get_mitmproxy_pod_status(namespace, service)
mitm_ports = list(str(p) for p in range(45455, 45455+len(ports)))
port_mapping = {}
for m_port, l_port in zip(mitm_ports, ports):
    port_mapping[l_port] = m_port

cmd = "kubectl port-forward -n {} {} {}".format(namespace, mitmproxy_podname, " ".join(mitm_ports))
# print(cmd)
proxy = subprocess.Popen(cmd, shell=True)
print("Please note, if pod isn't up you have to manually run the command in other console!")

mitm_labels = {"op":"replace", "path":"/spec/selector", "value": {"proxy":"true", "papp":service}}
orig_labels = {"op":"replace", "path":"/spec/selector", "value": spec['selector']}

ok = input("Patch the original service by pressing ENTER")
cmd = ["kubectl", "patch", "-n", namespace, "svc", service, "--type=json", "--patch={}".format(json.dumps([mitm_labels]))]
print(cmd)
run(cmd)

print("\n\n\n")
for l_port, m_port in port_mapping.items(): 
    print("Patched service! Now you can debug by going to http://localhost:{} for port {}".format(m_port, l_port))
print("\n\n\n")

ok = input("When you are ready, return to normal by pressing ENTER")

cmd = ["kubectl", "patch", "-n", namespace, "svc", service, "--type=json", "--patch={}".format(json.dumps([orig_labels]))]
print(cmd)
run(cmd)

proxy.kill()
run(["kubectl", "delete", "-n", namespace, "pod", mitmproxy_podname])
run(["kubectl", "delete", "-n", namespace, "service", orig_service_name])
