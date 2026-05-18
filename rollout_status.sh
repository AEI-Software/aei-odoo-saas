#!/bin/bash
ssh -i /tmp/k3s_rsa -o StrictHostKeyChecking=no ubuntu@10.40.2.158 "KUBECONFIG=/etc/rancher/k3s/k3s.yaml kubectl rollout status deployment/odoo-stg -n staging"
