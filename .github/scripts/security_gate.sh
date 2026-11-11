#!/usr/bin/env bash
# Supply-Chain & Repository Security Gate for AEI Software (Odoo 18 SaaS)
set -euo pipefail

ERRORS=0

echo "==> [1/4] Checking for malicious VSCode auto-run tasks..."
if [ -f ".vscode/tasks.json" ]; then
    if grep -qi '"runOn"[[:space:]]*:[[:space:]]*"folderOpen"' .vscode/tasks.json; then
        echo "ERROR: Malicious auto-run task (runOn: folderOpen) detected in .vscode/tasks.json"
        ERRORS=$((ERRORS + 1))
    fi
fi

echo "==> [2/4] Checking for obfuscated JS or EtherHiding patterns in custom addons..."
if grep -rnE 'eval\(atob\(|Function\(atob\(|fromCharCode\([0-9, ]{40,}\)|eth_call|eth_sendRawTransaction' addons/ portal/ 2>/dev/null; then
    echo "ERROR: Suspicious obfuscated code or blockchain C2 pattern detected."
    ERRORS=$((ERRORS + 1))
fi

echo "==> [3/4] Checking for tracked private key files or kubeconfigs..."
FORBIDDEN_FILES=$(find . -maxdepth 3 \( -name "*.pem" -o -name "*.key" -o -name ".kubeconfig" -o -name ".secrets.env" \) -not -path "./.git/*" || true)
if [ -n "$FORBIDDEN_FILES" ]; then
    echo "ERROR: Sensitive key or secret file present in workspace:"
    echo "$FORBIDDEN_FILES"
    ERRORS=$((ERRORS + 1))
fi

echo "==> [4/4] Checking custom Odoo POST forms for CSRF token presence..."
while IFS= read -r -d '' xml_file; do
    if grep -qi '<form[^>]*method=["'\'']post["'\'']' "$xml_file"; then
        if ! grep -q 'csrf_token' "$xml_file"; then
            echo "ERROR: POST form without csrf_token in $xml_file"
            ERRORS=$((ERRORS + 1))
        fi
    fi
done < <(find addons/ -name "*.xml" -print0)

if [ "$ERRORS" -gt 0 ]; then
    echo "Security gate FAILED with $ERRORS error(s)."
    exit 1
fi

echo "Security gate PASSED."

