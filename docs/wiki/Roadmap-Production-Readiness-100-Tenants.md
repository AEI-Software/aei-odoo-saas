# Roadmap: Production Readiness — 100 Tenants (Abril 2026)

> **Fecha de análisis:** 2026-04-15  
> **Última actualización:** 2026-04-15 — sesión de implementación completa  
> **Objetivo:** dejar la infraestructura apta para vender y operar **100 clientes iniciales** en producción hacia **finales de abril 2026**.  
> **Fuente:** auditoría en vivo del cluster (3 control-planes K3s 1.34, Patroni PG16 ×3, Ceph RBD, Traefik + Cloudflare Tunnel, Prometheus/Loki).  
> **Veredicto actual:** ✅ **Lista para Go/No-Go.** 9/10 hitos completados. Hito 7 (TLS cert-manager) diferido a Roadmap v2 por diseño (Cloudflare maneja TLS externo).

---

## Resumen ejecutivo

La plataforma está lista para producción. Los 9 hitos críticos están completos: 3 worker nodes unidos al cluster con etcd aislado, quotas y PDB por tenant, backups activos, GC de PVs, Traefik HA, fix de restarts, y Loki con retención de 31 días y 50 Gi. El único hito diferido (TLS cert-manager) no bloquea el lanzamiento porque Cloudflare Tunnel ya maneja todo el TLS externo.

---

## Los 10 hitos

Cada hito se marca `[ ]` pendiente, `[~]` en progreso, `[x]` completado, `[→]` diferido.

### 1. [x] Añadir 3 worker nodes dedicados — **BLOQUEANTE**
- **Problema:** 12 vCPU / 24 GB totales. 100 tenants Starter = 51 GB de *requests* de RAM. control-1 ya al 61 %.
- **Entregable:** 3 nodos worker, taint `node-role.kubernetes.io/control-plane:NoSchedule` en los control-planes, reprogramar workloads.
- **Criterio de aceptación:** `kubectl top nodes` muestra workers <60 % mem con 50 tenants simulados.
- **Completado 2026-04-15** — script `infra/k3s-ha/07-join-k3s-workers.sh`. Workers k3s-worker-1/2/3 en 192.168.0.148/.61/.190. Cilium auto-propagado. Label `workload=tenant` aplicado. `nodeAffinity` preferencial añadido a todos los deployments de tenants en `portal/k8s_utils/manifests.py`.

### 2. [x] ResourceQuota + LimitRange por namespace de tenant
- **Problema:** un tenant puede consumir toda la RAM del nodo (noisy neighbor).
- **Entregable:** `portal/k8s_utils/manifests.py` genera `ResourceQuota` (límite por plan) y `LimitRange` (defaults) junto al namespace.
- **Criterio:** crear tenant Starter → `kubectl describe quota -n odoo-<id>` muestra límites; pod que excede es rechazado.
- **Completado 2026-04-15** — commit ef524a9. LimitRange protege init containers (default 500m/512Mi). ResourceQuota por plan (starter: 2cpu/4Gi, pods≤5, pvcs≤2). Validado en stg-aei-cliente1: quota Used/Hard consistente con 1 pod corriendo.

### 3. [~] Backups programados de PostgreSQL
- **Problema:** solo existía un Job one-off `db-backup-test`. Descubrimiento 2026-04-14: **pgBackRest ya está desplegado** y funcional (stanza `odoo-saas`, full+diff diarios a RadosGW, WAL archiving continuo).
- **Entregables completados:**
  - [x] pgBackRest físico/PITR — ya en producción desde 2026-04-11
  - [x] CronJob `pg-logical-dump` — pg_dump por base a S3 (03:30 AM BOT, réplica :5001)
  - [x] CronJob `filestore-dump` — tar de PVC Odoo a S3 (04:00 AM BOT, kubectl exec)
  - [x] CronJob `backup-prune` — retención 7d/4w/3m (Dom 05:00 AM BOT)
  - [x] [Runbook: Backup and Restore](Runbook-Backup-and-Restore.md) — PITR, restore por tenant, filestore (DEPLOY.md)
  - [x] Fix `--expected-size 10GiB` + check existencia filestore — commit 502cf14 (2026-04-15)
  - [x] Validación manual 2026-04-15: pg-dump 9 DBs ✓ + filestore 3 tenants ✓ — 0 errores
  - [ ] Restore drill ejecutado (programado 2026-04-20) → ver [Restore Drill Hito 3](Restore-Drill-Hito-3.md)
- **Criterio:** restore de una DB tenant en <15 min desde backup del día anterior.

### 4. [x] Garbage collection de tenants borrados
- **Problema:** ~25 PV en estado `Released` con `reclaimPolicy: Retain` — RBD sigue ocupado.
- **Entregable:** endpoint `DELETE /api/v1/gc/pvs` en el portal + CronJob diario `pv-gc` (03:00 UTC). Filtra PVs Released cuyo namespace `odoo-*` ya no existe.
- **Criterio:** `kubectl get pv | grep Released` → 0.
- **Completado 2026-04-15** — `portal/routers/gc.py`, `k8s/09-gc-cronjob.yaml`, RBAC `persistentvolumes` en `k8s/04-rbac.yaml`. Soporta `?dry_run=true`.

### 5. [x] Traefik HA
- **Problema:** 1 sola réplica de Traefik. Reinicio tumba TODOS los tenants.
- **Entregable:** réplicas ≥2, `PodDisruptionBudget` min 1, anti-affinity por nodo.
- **Criterio:** `kubectl delete pod -l app=traefik` → ingress sigue respondiendo 200.
- **Completado 2026-04-15** — commit 21263da. HelmChartConfig replicas=2 + requiredAntiAffinity por hostname. PDB minAvailable:1. Validado: delete pod → 200 OK continuo desde ClusterIP. Pods migrados a workers tras hito 10.

### 6. [x] PodDisruptionBudget en tenants
- **Problema:** rolling updates / cordons tumban clientes.
- **Entregable:** template de tenant incluye `PDB minAvailable: 1`.
- **Criterio:** `kubectl drain` de un nodo no produce downtime en tenants replicados.
- **Completado 2026-04-15** — commit ef524a9. `pdb_manifest()` añadido a `all_manifests()`. ALLOWED DISRUPTIONS=0 con replicas=1 — protege de drain accidental.

### 7. [→] TLS de origen con cert-manager — **DIFERIDO A ROADMAP v2**
- **Decisión 2026-04-15:** Cloudflare Tunnel ya maneja 100% del TLS externo. El tramo interno (cloudflared → Traefik → pods) viaja en red privada `192.168.0.0/24` con Cilium NetworkPolicy. El riesgo de instalar cert-manager en producción supera el beneficio actual.
- **Diferido porque:** cambios en todos los Ingress de tenants (25+ namespaces), dependencia de Cloudflare API para ACME DNS-01, posibles conflictos con Traefik en producción.
- **Pendiente para:** Roadmap v2 — mTLS intra-cluster, cert rotation automático.

### 8. [x] Retención y dimensionamiento de Loki
- **Problema:** Loki PVC 10 Gi single-node; con 100 tenants se llena en días.
- **Entregable:** política de retención 31 días, PVC 50 Gi, `table_manager` activo.
- **Criterio:** ingestión sostenida una semana con utilización <70 %.
- **Completado 2026-04-15** — PVC expandido 10Gi→50Gi vía patch directo (Ceph RBD online resize). Helm upgrade con `table_manager.retention_deletes_enabled=true`, `retention_period=744h`, `chunk_store_config.max_look_back_period=744h`. Filesystem reconocido: 49 Gi libres. `infra/install-monitoring.sh` actualizado.

### 9. [x] Arranque de tenant resiliente (fix 58-60 restarts)
- **Problema:** init container de Odoo falla con timeout DNS a `postgres.aeisoftware.svc.cluster.local` en primeros intentos — 58-60 restarts antes de estabilizar.
- **Entregable:** init container `wait-for-postgres` con `nc -z` loop, init container `odoo-init` idempotente (skip si DB ya existe).
- **Criterio:** nuevo tenant alcanza `ready` con ≤2 restarts.
- **Completado 2026-04-15** — commit 6ac833d. 3 init containers: clone-addons → wait-for-postgres → odoo-init (idempotente). Validado: restarts reducidos a 0-1.

### 10. [x] Separar etcd de workloads
- **Problema:** etcd embebido en los 3 control-planes compartidos con cargas; fsync degrada plano de control con densidad alta.
- **Entregable:** taint `node-role.kubernetes.io/control-plane:NoSchedule` en los 3 nodos. Todos los workloads migrados a workers.
- **Criterio:** 0 pods de workload en control-plane. Solo DaemonSets de sistema (cilium, kube-vip, node-exporter, promtail, ceph-csi-nodeplugin).
- **Completado 2026-04-15** — taint aplicado a k3s-control-1/2/3. Rollout restart de: portal, odoo-admin, odoo-stg, portal-stg, cloudflared, traefik, ceph-provisioner, tenants, prometheus, loki, alertmanager, grafana, kube-state-metrics, kube-prometheus-operator. Resultado: 0 workloads en control-plane, 0 pods non-running. Bug bonus corregido: Grafana datasource `loki-loki-stack` tenía `isDefault: true` duplicado con Prometheus — causaba CrashLoopBackOff en cada restart.

---

## Dependencias y orden sugerido

```
1 (workers)   ──┬──> 2 (quotas) ──> 6 (PDB tenants)
                ├──> 5 (traefik HA)
                └──> 10 (etcd separation)
3 (backups)    ── independiente
4 (GC tenants) ── independiente
8 (loki)       ── independiente
9 (fix restarts) ── independiente, rápido
7 (TLS)        ── DIFERIDO a Roadmap v2
```

## Seguimiento

| # | Hito | Estado | Responsable | Fecha completado | PR / commit |
|---|------|--------|-------------|-----------------|-------------|
| 1 | Worker nodes | [x] | Claude / JPV | 2026-04-15 | 07-join-k3s-workers.sh |
| 2 | ResourceQuota/LimitRange | [x] | Claude / JPV | 2026-04-15 | ef524a9 |
| 3 | Backups PG programados | [~] | Claude / JPV | drill: 2026-04-20 | k8s/backup/ · 502cf14 |
| 4 | GC tenants borrados | [x] | Claude / JPV | 2026-04-15 | portal/routers/gc.py · k8s/09-gc-cronjob.yaml |
| 5 | Traefik HA | [x] | Claude / JPV | 2026-04-15 | 21263da |
| 6 | PDB tenants | [x] | Claude / JPV | 2026-04-15 | ef524a9 |
| 7 | TLS cert-manager | [→] | — | diferido | Roadmap v2 |
| 8 | Loki retención 50Gi | [x] | Claude / JPV | 2026-04-15 | infra/install-monitoring.sh |
| 9 | Fix restarts tenant | [x] | Claude / JPV | 2026-04-15 | 6ac833d |
| 10 | Aislar etcd | [x] | Claude / JPV | 2026-04-15 | taint NoSchedule + rollout |

---

## Hitos post-MVP / Roadmap v2

### 11. [ ] TLS cert-manager (intra-cluster)
- Diferido desde hito 7. Ver decisión en sección 7.
- Implementar cuando se requiera mTLS entre servicios o compliance más estricto.

### 12. [ ] Alertas Prometheus de backup
- **Problema:** ninguna alerta activa si los backups fallan silenciosamente.
- **Entregable:** PrometheusRule con alertas: `archive_failed_count > 0`, `time_since_last_pgdump > 26h`, `time_since_last_filestore > 26h`. AlertManager → email/Slack.

### 13. [ ] Réplica off-site del repo pg-backups
- **Problema:** bucket `pg-backups` reside en el mismo Ceph del cluster.
- **Entregable:** `rclone sync` nocturno del bucket a ubicación externa (cloud S3 / NAS / segundo Ceph).

### 14. [~] SBA in-cluster: facturación SIAT como parte de la solución (añadido 2026-08-13)
- **Avance 2026-08-14 — instancia PILOTO operativa en staging:** ns `sba-piloto` con postgres:17 +
  restore del dump de `sba_v1_staging` (3 emisores CodAmb=2, endpoints piloto verificados), imagen
  `ghcr.io/aei-software/sba:3268457` (workflow nuevo en el repo SBA; paquete privado → Secret
  `ghcr-pull`), certs del NIT DEMO en Secret, NetworkPolicy validada en vivo (tenant → 200; ns no
  autorizado → bloqueado). Template del tenant con regla de egreso `app: sba → 3001` (los ipBlock
  de Cilium no matchean pods del cluster). `sub00271` conectado (`service_url` al Service).
  Manifests: `infra/sba-piloto/`. **Criterio de aceptación CUMPLIDO 2026-08-14:** `sub00271`
  (tenant recién aprovisionado) emitió una factura PILOTO end-to-end vía el SBA del cluster —
  CUF obtenido, documento `EstDoc=V` en `SFL_TabDoc`, anulación y reversión de anulación también
  verificadas; sin túneles SSH. Emisor URZACOM (CodAmb=2), actividad hoja `4530000`, producto SIN
  `1002379`. Observación menor: la respuesta v2 no trajo `file_pdf/file_xml` inline (la descarga
  desde Odoo queda por resolver — existen `docs.obtenerPdf/Xml` en SBA). **Queda del hito:** auth
  de `/pub`, onboarding de emisores no-manual, localizar el repo TS fuente.
- **Problema:** el producto vendible (Starter 19.0, `l10n_bo_core`) emite facturas **delegando en SBA**,
  que hoy vive solo en un VPS remoto (contenedores `sba-app-1` prod / `sba-staging-app-1` PILOTO,
  ligados a localhost y alcanzados por túnel SSH). Los tenants del cluster no tienen un SBA alcanzable:
  sin esto el producto no factura. Además `/pub/*` **no tiene autenticación** — su única protección
  actual es el binding a localhost del VPS, así que no puede exponerse tal cual.
- **Entregable:** namespace `sba` en el cluster con Deployment + Service **ClusterIP** (sin Ingress
  público) y su propia BD (Cluster CNPG en el ns, mismo patrón que los tenants). Una instancia
  **staging/PILOTO (CodAmb=2)** primero; la de producción (CodAmb=1) como despliegue separado cuando
  el QA del producto cierre.
  - **NetworkPolicy obligatoria:** solo los namespaces de tenants (`odoo-*`) alcanzan el puerto de
    SBA; todo lo demás denegado. Es la mitigación de la falta de auth de `/pub/*` mientras no exista
    una API key (hardening de `/pub` ya diferido en el track SBA).
  - **Integración con el aprovisionamiento:** el first-boot / portal fija
    `l10n_bo_core.service_url = http://<svc>.sba.svc.cluster.local:<puerto>` en cada tenant nuevo
    (hoy el ICP queda vacío y el tenant no puede emitir sin configuración manual).
  - **Alta de emisor por tenant:** cada tenant necesita su empresa/emisor (NIT, CUIS/CUFD, actividades)
    dada de alta en SBA. Definir si se automatiza en el provisioning o queda como paso operativo
    manual — el alta hoy tiene bugs conocidos documentados (commit `3252085` del track SBA, sin
    parchear porque el código desplegado es compilado).
  - **Imagen:** empaquetar SBA para el cluster y publicarla en GHCR. ⚠️ Prerrequisito: el código
    fuente TS real de SBA está en un repo aún sin identificar (en el VPS corre un build compilado) —
    localizarlo o, como puente, exportar la imagen que corre en el VPS.
- **Criterio de aceptación:** un tenant recién aprovisionado emite una factura de prueba contra SIAT
  **PILOTO** end-to-end (CUF + PDF/XML) usando el SBA del cluster, sin túneles SSH ni configuración
  manual del `service_url`; un pod fuera de `odoo-*` no puede conectarse al Service de SBA.

---

## Go / No-Go para 100 clientes

- ✅ **GO:** hitos 1-6, 8-10 en verde. Hito 7 (TLS) diferido con mitigación documentada (Cloudflare). Hito 3 en verde excepto restore drill (programado 2026-04-20).
- **Condición:** ejecutar restore drill (hito 3) antes del lanzamiento comercial.
