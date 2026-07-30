# PostgreSQL Cluster Operations

> ⚠️ **ENTORNO COTAS DESMANTELADO (2026-07-28).** El clúster de producción/staging en `10.40.2.158`
> (Ceph RBD, Patroni `192.168.0.x`, `*.aeisoftware.com`) ya no existe, y **no hay entorno productivo
> activo** — la migración a un nuevo proveedor está pendiente. El único entorno vivo es el **testbed
> cruzoil** (`10.9.13.x`), que es solo laboratorio. Esta página se conserva como referencia histórica:
> los procedimientos siguen siendo válidos como plantilla, pero ningún host, IP o namespace aquí
> descrito responde hoy. Ver [Environment Status](Environment-Status.md).

> Guía operativa consolidada para el cluster Patroni HA. Esta página reconcilia y reemplaza información dispersa en otros docs. Véase también la guía más detallada en [`infra/postgres-ha/README.md`](../../infra/postgres-ha/README.md) del repo principal.

## Arquitectura del cluster

**El cluster PG NO corre en K8s.** Son 3 VMs Ubuntu externas con PostgreSQL 16 nativo (paquetes PGDG), orquestadas por Patroni.

| Nodo | IP interna | SSH | Rol típico |
|---|---|---|---|
| pg-node1 | 192.168.0.127 | ubuntu@10.40.2.182 | réplica |
| pg-node2 | 192.168.0.186 | ubuntu@10.40.2.174 | primary |
| pg-node3 | 192.168.0.226 | ubuntu@10.40.2.193 | réplica |

Patroni scope: `odoo-saas-ha` · REST API `:8008` · DCS etcd `192.168.0.{127,186,226}:2379`

pgBackRest stanza: `odoo-saas` (distinto del scope Patroni) · Repo: S3/RadosGW `10.40.1.240:7480` vía stunnel local `127.0.0.1:18480`

En K8s solo hay un `Service postgres` headless + `Endpoints` manual (`k8s/02-postgres-external.yaml`) apuntando a las 3 VMs en port 5000. Los Pods se conectan via `postgres.aeisoftware.svc.cluster.local:5000`.

## Puertos HAProxy — mapa completo

| Puerto | Uso correcto | Estado |
|---|---|---|
| **`:5000`** | **RW primary — TODO el tráfico: Odoo workers, portal, DDL, provisioning** | ✅ ACTIVO |
| **`:5001`** | **RO réplicas — solo lectura: pg_dump CronJob** | ✅ ACTIVO |
| ~~`:5002`~~ | ~~RW pooled vía PgBouncer~~ **ELIMINADO 2026-04-11** | ❌ DEAD |
| `:7000` | HAProxy stats UI | ✅ ACTIVO |
| `:6432` | PgBouncer local — instalado pero `systemctl disable pgbouncer` | ⛔ DISABLED |
| `:5432` | PG nativo — solo localhost; postgres_exporter y Patroni | 🔒 LOCAL ONLY |

> **REGLA:** Cualquier operación de escritura (CREATE, DROP, ALTER, INSERT) va a `:5000`. El puerto `:5001` es solo para reads. El `:5002` está muerto — cualquier doc que lo mencione es stale.

## Identidad de roles — la trampa más frecuente

### Rol `odoo` (lo que usa el portal)

El portal (`k8s/05-portal.yaml:62`) conecta como rol **`odoo`**, que tiene `CREATEROLE + CREATEDB` pero **NO es superusuario**. La variable se llama `POSTGRES_ADMIN_USER` y hay un comentario incorrecto en `portal/routers/instances.py:96` — ambos son engañosos.

Capacidades del rol `odoo`:
- ✅ `CREATE DATABASE`, `CREATE ROLE`
- ✅ `DROP DATABASE` propio, `DROP ROLE`
- ❌ `pg_terminate_backend` sobre sesiones de superusuarios
- ❌ `DROP DATABASE WITH (FORCE)` (requiere superusuario o propietario)

### Rol `postgres` (superusuario)

El password del superusuario vive en **dos sitios**:
1. En las VMs: `/etc/patroni/patroni.yml` → `postgresql.authentication.superuser.password`
2. En K8s: Secret `backup-system/postgres-superuser-secret` key `POSTGRES_PASSWORD` (var `.secrets.env`: `BACKUP_PG_SUPERUSER_PASSWORD`)

No hay secret de superusuario en el namespace `aeisoftware`. El portal nunca tiene acceso al superusuario.

### Mapa de secrets PG

| Secret | Namespace | Key | Contiene |
|---|---|---|---|
| `postgres-secret` | `aeisoftware` | `POSTGRES_PASSWORD` | Password del rol `odoo` |
| `postgres-secret` | `odoo-admin` | `POSTGRES_PASSWORD` | Password del rol `odoo` |
| `odoo-admin-secret` | `odoo-admin` | `DB_PASSWORD` | Password del rol `odoo` |
| `postgres-superuser-secret` | `backup-system` | `POSTGRES_PASSWORD` | Password del superusuario `postgres` |

> **Staging gotcha:** `postgres-secret` en ns `staging` NO lo crea `apply-manifests.sh`. Hacerlo manualmente. Ver `k8s/07-staging.yaml:26-27`.

## Operaciones de diagnóstico (ejecutar siempre primero)

```bash
# Estado del cluster — quién es primary, lag de réplicas
ssh ubuntu@10.40.2.174 'sudo patronictl -c /etc/patroni/patroni.yml list'

# ¿Quién es primary? (200 = sí, 503 = no)
for ip in 192.168.0.127 192.168.0.186 192.168.0.226; do
  echo -n "$ip: "; curl -s -o /dev/null -w "%{http_code}" http://$ip:8008/primary; echo
done

# Conexiones activas (con detalle de superusuario)
ssh ubuntu@10.40.2.174 "sudo -u postgres psql -c \"
  SELECT pid, usename, r.rolsuper, datname, application_name, state
  FROM pg_stat_activity a
  JOIN pg_roles r ON r.rolname = a.usename
  WHERE datname NOT IN ('postgres','template0','template1')
  ORDER BY datname;\""

# Tamaños de DBs
ssh ubuntu@10.40.2.174 "sudo -u postgres psql -c \"
  SELECT datname, pg_size_pretty(pg_database_size(datname))
  FROM pg_database ORDER BY pg_database_size(datname) DESC;\""
```

## Flujo canónico de eliminar un tenant

El portal intenta hacer el DROP automáticamente al eliminar una instancia. **Cuando falla** (warning en logs), usar este procedimiento manual:

### Paso 1 — Verificar sesiones activas

```bash
ssh ubuntu@10.40.2.174 "sudo -u postgres psql -c \"
  SELECT pid, usename, application_name, state
  FROM pg_stat_activity WHERE datname = 'odoo_<tenant_id>';\""
```

### Paso 2a — Si hay sesiones de `postgres_exporter` (superusuario)

```bash
# Parar exporter en las 3 VMs (Prometheus tolera 2 min de gap)
for IP in 10.40.2.182 10.40.2.174 10.40.2.193; do
  ssh ubuntu@$IP "sudo systemctl stop postgres_exporter"
done
```

### Paso 2b — Si hay sesión del pg_dump CronJob

El CronJob `pg-logical-dump` en `backup-system` corre a las **03:30 BOT** y conecta como superusuario a `:5001`. Esperar a que termine:

```bash
kubectl -n backup-system get jobs --sort-by=.status.startTime | tail -5
```

### Paso 3 — DROP como superusuario

```bash
# Opción A: desde las VMs (requiere SSH al nodo primary)
ssh ubuntu@10.40.2.174 "sudo -u postgres psql -p 5432 -c \"
  SELECT pg_terminate_backend(pid) FROM pg_stat_activity
  WHERE datname = 'odoo_<tenant_id>' AND pid <> pg_backend_pid();\"
  DROP DATABASE IF EXISTS odoo_<tenant_id>;
  DROP ROLE IF EXISTS \\\"odoo-<tenant_id>\\\";\""

# Opción B: desde K8s con el secret de backup-system
kubectl -n backup-system run pg-drop --rm -it --restart=Never \
  --image=postgres:16-alpine \
  --env="PGPASSWORD=$(kubectl -n backup-system get secret postgres-superuser-secret \
    -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d)" \
  -- psql -h postgres.aeisoftware.svc.cluster.local -p 5000 -U postgres \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'odoo_<tenant>' AND pid <> pg_backend_pid();" \
  -c "DROP DATABASE IF EXISTS odoo_<tenant>;" \
  -c "DROP ROLE IF EXISTS \"odoo-<tenant>\";"
```

### Paso 4 — Reanudar exporter (si se paró)

```bash
for IP in 10.40.2.182 10.40.2.174 10.40.2.193; do
  ssh ubuntu@$IP "sudo systemctl start postgres_exporter"
done
```

### Verificar DBs huérfanas

```bash
# Via GC endpoint del portal (dry run)
API_KEY=$(kubectl -n aeisoftware get secret portal-secret -o jsonpath='{.data.API_KEY}' | base64 -d)
kubectl -n aeisoftware run gc-check --rm -it --restart=Never --image=curlimages/curl:8.7.1 \
  -- curl -s -H "X-API-Key: $API_KEY" \
  "http://portal.aeisoftware.svc.cluster.local:8000/api/v1/gc/dbs?dry_run=true"
```

## Errores comunes y solución

| Error | Causa raíz | Solución |
|---|---|---|
| `Could not drop Postgres user <x>` en logs del portal | `postgres_exporter` o pg_dump CronJob tiene sesión superusuario en la DB → `pg_terminate_backend` denegado | Ver flujo "Eliminar tenant" arriba. Parar exporter → DROP como superusuario. |
| `database is being accessed by other users` | Sesión superusuario activa impide DROP | Mismo flujo. Verificar quién está conectado. |
| `server closed the connection unexpectedly` en WorkerCron | HAProxy cierra conexiones idle después de 30 min (antes del fix de PGKEEPALIVES) | Ya corregido en commit `0bc7109` — PGKEEPALIVES=1 + IDLE=60s en los manifiestos. |
| `pg_terminate_backend` permission denied | El rol `odoo` intenta terminar una sesión del rol `postgres` (superusuario) | Conectarse como superusuario para la terminación. Ver §Identidad de roles. |
| Archive failing — WAL archiver | Stunnel no corriendo en el nodo primary | `ssh ubuntu@10.40.2.174 'sudo systemctl restart stunnel-s3proxy'` · Verificar: `sudo -u postgres psql -c "SELECT last_failed_wal FROM pg_stat_archiver;"` |
| No-leader — Patroni pierde quórum | etcd no tiene quórum (≥2 nodos) | `etcdctl endpoint health --endpoints=...` · `sudo systemctl restart etcd` en los nodos que fallaron |
| Réplica divergida / corrupta | Crash de nodo, network split | `sudo patronictl -c /etc/patroni/patroni.yml reinit odoo-saas-ha <pg-nodeX>` |
| Replication lag alto | IO de disco en primary o réplica lenta | `patronictl list` para ver lag · revisar `pg_stat_replication` · considerar `synchronous_commit=off` en DCS |

## Patronictl — comandos de gestión del cluster

```bash
# Ver estado completo
sudo patronictl -c /etc/patroni/patroni.yml list

# Switchover controlado (interactivo)
sudo patronictl -c /etc/patroni/patroni.yml switchover

# Reiniciar nodo vía Patroni (NUNCA systemctl restart postgresql directamente)
sudo patronictl -c /etc/patroni/patroni.yml restart odoo-saas-ha pg-node1

# Re-inicializar réplica caída/divergida
sudo patronictl -c /etc/patroni/patroni.yml reinit odoo-saas-ha pg-node3

# Editar configuración del cluster en DCS (max_connections, wal_level, etc.)
sudo patronictl -c /etc/patroni/patroni.yml edit-config

# Ver config DCS actual
sudo patronictl -c /etc/patroni/patroni.yml show-config
```

## pgBackRest

```bash
# Estado de backups
sudo -u postgres pgbackrest --stanza=odoo-saas info

# Verificar salud (conectividad + archiver)
sudo -u postgres pgbackrest --stanza=odoo-saas check

# Backup manual full
sudo -u postgres pgbackrest --stanza=odoo-saas --type=full backup

# PITR — restauración point-in-time (DESTRUCTIVO — requiere parar Patroni en todos los nodos)
# Ver procedimiento completo en [Runbook: Backup and Restore](Runbook-Backup-and-Restore.md)
```

## Notas sobre PgBouncer (HISTÓRICO)

PgBouncer fue **eliminado del path de tráfico** el 2026-04-11. Razones:
- `LISTEN/NOTIFY` incompatible con `pool_mode=transaction`
- DDL requería una conexión bypass
- SCRAM-SHA-256 de PG 16 vs `auth_type=md5` de PgBouncer (resuelto pero frágil)

Sigue instalado (`systemctl disable pgbouncer`) en las 3 VMs como fallback si el número de tenants supera ~250 (cada tenant necesita ~3 conexiones, 800 max_connections → ~255 tenants sin pooler). Si algún doc menciona PgBouncer como activo, es información stale.

## Referencias cruzadas y estado de vigencia

| Doc | Vigente | Caveats |
|---|---|---|
| [Production Cloud Environment](Production-Cloud-Environment.md) | ✅ Sí | Arquitectura actual, por qué se eliminó PgBouncer |
| [Operational Runbook](Operational-Runbook.md) | ✅ Sí | Health checks, pgBackRest, stunnel, monitoring |
| [Runbook: Backup and Restore](Runbook-Backup-and-Restore.md) | ✅ Sí | PITR completo, restore por tenant |
| `infra/postgres-ha/README.md` (repo) | ⚠️ Parcial | PgBouncer documentado como activo — ignorar esas secciones |
| [Secrets Management](Secrets-Management.md) | ⚠️ Parcial | Rotación de password documenta `postgres-0` StatefulSet que no existe en prod |
| [Low-Level Design (LLD)](Low-Level-Design-(LLD).md) | ⚠️ Solo dev | Puerto `5432` es solo en entorno local K3s |
| [High-Level Design (HLD)](High-Level-Design-(HLD).md) | ⚠️ Solo diseño | Describe MVP sin Patroni |
| `DEPLOY.md` (repo) | ✅ Corregido | Port 5001→5000 corregido 2026-04-16 |
| `backups/backup-restore.md` (repo) | ✅ Corregido | Port 5002→5000 corregido 2026-04-16 |
