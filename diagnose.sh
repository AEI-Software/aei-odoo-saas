#!/bin/bash
echo "=== NAMESPACES ===" > /home/kali/aei-odoo-saas/diag.log
ssh -i /tmp/k3s_rsa -o StrictHostKeyChecking=no ubuntu@10.40.2.158 "KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get ns" >> /home/kali/aei-odoo-saas/diag.log 2>&1

echo "=== TENANT PODS ===" >> /home/kali/aei-odoo-saas/diag.log
ssh -i /tmp/k3s_rsa -o StrictHostKeyChecking=no ubuntu@10.40.2.158 "KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl get pods -A" >> /home/kali/aei-odoo-saas/diag.log 2>&1

echo "=== PORTAL LOGS ===" >> /home/kali/aei-odoo-saas/diag.log
ssh -i /tmp/k3s_rsa -o StrictHostKeyChecking=no ubuntu@10.40.2.158 "KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl logs -n staging deploy/portal-stg --tail=150" >> /home/kali/aei-odoo-saas/diag.log 2>&1
