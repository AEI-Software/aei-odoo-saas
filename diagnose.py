import subprocess

def run():
    commands = [
        ("NAMESPACES", 'KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get ns'),
        ("TENANT_PODS", 'KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get pods -A'),
        ("PORTAL_LOGS", 'KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl logs -n staging deploy/portal-stg --tail=150'),
        ("POD_EVENTS", 'KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get events -A --sort-by=".metadata.creationTimestamp" | tail -n 50')
    ]
    
    with open('/home/kali/aei-odoo-saas/diag.log', 'w') as f:
        for title, cmd in commands:
            f.write(f"=== {title} ===\n")
            ssh_cmd = [
                "ssh", "-i", "/tmp/k3s_rsa", 
                "-o", "StrictHostKeyChecking=no", 
                "-o", "BatchMode=yes",
                "ubuntu@10.40.2.158", cmd
            ]
            try:
                res = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
                f.write(res.stdout)
                if res.stderr:
                    f.write("\n--- STDERR ---\n")
                    f.write(res.stderr)
            except Exception as e:
                f.write(f"Error running command: {str(e)}\n")
            f.write("\n\n")

if __name__ == '__main__':
    run()
