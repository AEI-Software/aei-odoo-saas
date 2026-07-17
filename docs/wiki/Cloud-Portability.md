# Cloud Portability — desplegar aei-odoo-saas en cualquier nube

> Estado: implementado en branch `feat/cloud-portability` (2026-07-17). Validado en el
> testbed cruzoil (ver runbook abajo) antes de merge a `main`.

## Objetivo

Eliminar el acoplamiento a la nube OpenStack/Platform9 de COTAS para poder alojar la
solución en cualquier proveedor con VMs Ubuntu + object storage S3 (AWS, Vultr, GCP,
DigitalOcean, Hetzner...) o en un servidor bare-metal con KVM.

## Acoplamientos eliminados

| # | Acoplamiento | Solución |
|---|--------------|----------|
| 1 | StorageClass `ceph-rbd` hardcodeada en manifiestos | Placeholder `${STORAGE_CLASS}` renderizado por `apply-manifests.sh` (envsubst con whitelist) |
| 2 | IPs de nodos incrustadas en scripts `infra/` | Inventario por entorno en `infra/environments/<env>.env` |
| 3 | Endpoints manuales de Postgres con IPs fijas (`k8s/02-postgres-external.yaml`) | Endpoints generados desde `PG_ENDPOINT_IPS` del inventario |
| 4 | Backups S3 → RadosGW con default hardcodeado + stunnel | `BACKUP_S3_ENDPOINT` obligatorio por entorno; stunnel condicionado a `S3_USE_STUNNEL` |
| 5 | Dominio `aeisoftware.com` en manifiestos y script CF | `${BASE_DOMAIN}` renderizado; `WILDCARD_HOSTNAME`/`TRAEFIK_SERVICE` por env en `setup_cloudflare_wildcard_tunnel.py` |
| 6 | Ceph obligatorio en prepare-node y deploy | `STORAGE_BACKEND=ceph\|longhorn`; Longhorn vía `infra/k3s-ha/06b-install-longhorn.sh` |
| 7 | Topología PG fija de 3 nodos | `PG_TOPOLOGY=single\|ha` — scripts iteran `PG_NODE_LIST` de longitud variable |

## El patrón: inventario por entorno

Todo lo específico del entorno (no-secreto) vive en un solo archivo:

```
infra/environments/
├── cotas.env      # producción/staging actual en COTAS (default — comportamiento histórico)
└── testbed.env    # testbed KVM en cruzoil
```

Uso:

```bash
./infra/k3s-ha/deploy-k3s-cluster.sh  infra/environments/testbed.env
./infra/k3s-ha/07-join-k3s-workers.sh infra/environments/testbed.env
./infra/postgres-ha/deploy-all.sh     infra/environments/testbed.env
./infra/apply-manifests.sh --env      infra/environments/testbed.env
```

Sin argumento, todos usan `cotas.env` — cero cambio de comportamiento para COTAS.
Los secretos siguen donde estaban: `.secrets.env` (raíz), `infra/k3s-ha/.env`,
`infra/postgres-ha/.env` + `.secrets.generated`.

Para un proveedor nuevo: copiar `testbed.env` → `<proveedor>.env`, poner IPs de las VMs,
elegir `STORAGE_BACKEND`/`STORAGE_CLASS` y el endpoint S3. Nada más.

### Render de manifiestos (whitelist envsubst)

`apply-manifests.sh` renderiza SOLO `${STORAGE_CLASS}` y `${BASE_DOMAIN}` en los
`k8s/0*.yaml`. Cualquier otra `${VAR}` (scripts embebidos en ConfigMaps de
`k8s/backup/` y `k8s/07-staging.yaml`) pasa intacta al clúster. Si se añade una
variable nueva a la whitelist, verificar colisiones antes:

```bash
grep -o '\${[A-Z_]*}' k8s/*.yaml k8s/backup/*.yaml | sort -u
```

## Matriz por proveedor

| Proveedor | VMs equivalentes (3×k3s + 3×pg prod) | Storage bloque | Object storage (backups) | Notas |
|-----------|--------------------------------------|----------------|--------------------------|-------|
| **COTAS (actual)** | blades OpenStack 4vCPU/8-16G | Ceph RBD (`ceph-rbd`) | Ceph RadosGW (HTTP + stunnel) | `cotas.env` |
| **Bare-metal / KVM** | VMs libvirt (testbed) | Longhorn (`longhorn`) | MinIO self-hosted (TLS self-signed) | `testbed.env`; patrón replicable en Hetzner/OVH dedicados |
| **Vultr** | 6× vc2-4c-8gb (~$48/mes c/u) | Longhorn, o Vultr Block Storage CSI | Vultr Object Storage (S3) | VKE (K8s gestionado) elimina `infra/k3s-ha/` |
| **AWS** | 6× t3.xlarge | Longhorn, o EBS CSI (`gp3`) | S3 | EKS gestionado opcional; RDS podría reemplazar `infra/postgres-ha/` |
| **GCP** | 6× e2-standard-4 | Longhorn, o PD CSI (`standard-rwo`) | GCS (modo interop S3) | GKE opcional |
| **DigitalOcean** | 6× s-4vcpu-8gb | Longhorn, o DO Block CSI | Spaces (S3) | DOKS opcional |

Regla general con K8s gestionado: saltarse `infra/k3s-ha/` por completo, poner en el
`.env` del entorno `STORAGE_CLASS` = clase default del proveedor, y correr solo
`postgres-ha` (o usar DB gestionada) + `apply-manifests.sh`.

Ingress: Cloudflare Tunnel hace el ingress independiente del proveedor — no se necesita
IP pública ni LoadBalancer; `cloudflared` (in-cluster o en un host cercano) alcanza el
VIP de Traefik.

## Runbook del testbed (cruzoil 10.9.13.2)

Topología: 3 VMs K3s (Longhorn) + 1 VM Postgres (Patroni single + MinIO), bridge `br0`.

| VM | IP | Recursos |
|----|-----|----------|
| kube-vip | 10.9.13.20 | (VIP flotante) |
| k3s-test-1..3 | 10.9.13.21-23 | 4 vCPU / 12G / 80G |
| pg-test-1 | 10.9.13.24 | 4 vCPU / 8G / 60G |

Invariantes del host cruzoil: NO tocar `comodin-win7`, `pangolin_it911` (producción,
con autostart), `pcd.qcow2`, la red `br0` ni los contenedores docker (producción
multi-tenant Odoo 17 + cloudflared).

```bash
SSH_CRUZOIL="ssh -i /home/kali/it911/pentest_it911/hardening/keys/it911_admin_ed25519 ubuntu@10.9.13.2"

# 1. Crear VMs (idempotente; verifica IPs libres antes)
#    OJO: el gateway de la red 10.9.13.0/24 es 10.9.13.253 (no .1)
scp -i <key> -r infra/testbed ubuntu@10.9.13.2:/tmp/
$SSH_CRUZOIL "sudo GATEWAY=10.9.13.253 SSH_PUBKEY_FILE=/tmp/it911_admin_ed25519.pub bash /tmp/testbed/create-testbed-vms.sh"

# 2. MinIO en pg-test-1
scp -i <key> infra/testbed/setup-minio.sh ubuntu@10.9.13.24:/tmp/
ssh -i <key> ubuntu@10.9.13.24 "sudo bash /tmp/setup-minio.sh"
# credenciales quedan en /root/minio-credentials.txt de pg-test-1 → copiarlas a infra/postgres-ha/.env

# 3. PostgreSQL single-node
./infra/postgres-ha/deploy-all.sh infra/environments/testbed.env

# 4. Clúster K3s + Longhorn
./infra/k3s-ha/deploy-k3s-cluster.sh infra/environments/testbed.env
export KUBECONFIG=infra/k3s-ha/.kubeconfig.testbed

# 5. Manifiestos (stack staging; excluye odoo-admin y cloudflared in-cluster)
./infra/apply-manifests.sh --env infra/environments/testbed.env

# 6. Ingress: ruta *.test.aeisoftware.com en el tunnel cloudflared EXISTENTE del host
#    ⚠️ NO ejecutar setup_cloudflare_wildcard_tunnel.py contra ese tunnel: su paso 2
#    REEMPLAZA todas las rutas y rompería los Odoo de producción del host.
#    Añadir el public hostname manualmente en Zero Trust:
#      *.test.aeisoftware.com → http://10.9.13.20
```

Validación E2E:

```bash
# tenant de prueba vía portal API
curl -X POST -H "X-API-Key: $API_KEY" https://portal-stg.test.aeisoftware.com/api/v1/instances \
  -H 'Content-Type: application/json' -d '{"tenant_id":"demo1","plan":"starter"}'
kubectl get pvc -n odoo-demo1          # Bound en longhorn
curl -I https://demo1.test.aeisoftware.com
# luego stop/start/upgrade/delete por la misma API

# backup a MinIO
kubectl -n backup-system create job --from=cronjob/<backup-cronjob> test-backup-manual
# verificar objeto: mc ls (o aws s3 ls --endpoint-url https://10.9.13.24:9000)
```

Regresión COTAS antes de merge:

```bash
./infra/apply-manifests.sh --dry-run          # usa cotas.env — debe renderizar ceph-rbd,
                                              # aeisoftware.com y Endpoints 192.168.0.x
```
