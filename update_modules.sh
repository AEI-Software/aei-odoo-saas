#!/bin/bash
ssh -i /tmp/k3s_rsa -o StrictHostKeyChecking=no ubuntu@10.40.2.158 "KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl exec -n staging deploy/odoo-stg -c odoo -- odoo --config=/etc/odoo/odoo.conf -d staging -u odoo_k8s_saas_subscription,odoo_k8s_saas --http-port=8088 --stop-after-init"
