# Environment Status — qué entornos existen hoy

> **Última actualización:** 2026-08-08
> Esta página es la fuente de verdad sobre qué infraestructura está viva. Cualquier otra
> página del wiki que describa hosts, IPs o namespaces debe leerse contra esta tabla.

## Estado actual

| Entorno | Estado | Dónde | Notas |
|:---|:---|:---|:---|
| **COTAS — producción + staging** | ❌ **DESMANTELADO (2026-07-28)** | `10.40.2.158` (OpenStack/Platform9, Ceph RBD) | Ya no existe. Ni el clúster K3s, ni los 3 nodos Patroni `192.168.0.x`, ni los namespaces `odoo-admin`/`staging`/`aeisoftware`. |
| **Testbed cruzoil** | ✅ Vivo — **solo laboratorio** | Host bare-metal `10.9.13.2`, VMs `10.9.13.20-24` | Entorno de validación de portabilidad multi-nube. **No aloja nada productivo.** |
| **Dev local (WSL)** | ✅ Disponible | `dev-setup.sh` | Sin cambios. Ver [Local Deployment WSL](Local-Deployment-WSL.md). |

**No hay entorno productivo activo.** La migración a un nuevo proveedor está pendiente:
no se ha elegido destino todavía. Ver [Cloud Provider Cost Analysis](Cloud-Provider-Cost-Analysis.md)
para la comparativa Vultr/AWS/Azure/GCP que alimenta esa decisión.

## Qué implica para la documentación

Las páginas que describen la infraestructura de COTAS se conservan **como referencia
histórica y como plantilla del procedimiento**, con un banner de desmantelamiento arriba.
Los pasos siguen siendo correctos conceptualmente; lo que ya no existe son los hosts.

Páginas marcadas como históricas:

- [Production Cloud Environment](Production-Cloud-Environment.md) — Ceph RBD, `securityContext` para Ceph, puerto 5000
- [Operational Runbook](Operational-Runbook.md) — DAY1/DAY2, pgBackRest, stack de monitoring
- [PostgreSQL Cluster Operations](PostgreSQL-Cluster-Operations.md) — topología Patroni 3 nodos
- [Runbook: Backup and Restore](Runbook-Backup-and-Restore.md) — pgBackRest → RadosGW, PITR
- [Branch Strategy and Promotion](Branch-Strategy-and-Promotion.md) — modelo `main`=staging / `18.0`=producción
- [High Level Design (HLD)](High-Level-Design-(HLD).md) y [Low Level Design (LLD)](Low-Level-Design-(LLD).md) — topología y recursos tal como corrían en COTAS
- [DAY0 Install From Scratch](DAY0-Install-From-Scratch.md) — instalación desde cero (sigue siendo la guía base, pero sus IPs son de COTAS)

Los roadmaps y auditorías (`Roadmap-*`, `Auditoria-Produccion.md`, `Security-Remediation-2026-07.md`)
son registros con fecha; se dejan tal cual.

## Testbed cruzoil — el único entorno vivo

Laboratorio de portabilidad multi-nube (branch `feat/cloud-portability`, levantado 2026-07-17).
Runbook completo en [Cloud Portability](Cloud-Portability.md).

| Elemento | Valor |
|:---|:---|
| Host KVM | `10.9.13.2` (bare-metal Ubuntu 22.04, 20 cores / 125 GB) |
| K3s servers | `k3s-test-1..3` = `10.9.13.21-23` (K3s v1.36 HA + Cilium + Longhorn) |
| VIP API server | `10.9.13.20` (kube-vip) |
| PostgreSQL | `pg-test-1` = `10.9.13.24` (Patroni single + PgBouncer + HAProxy) |
| Object storage | MinIO en `https://10.9.13.24:9000` |
| Inventario | `infra/environments/testbed.env` |
| Acceso kubectl | `KUBECONFIG=infra/k3s-ha/.kubeconfig.testbed` — **directo desde la workstation**, sin salto SSH (a diferencia de COTAS) |
| Dominios | `staging.` / `www.` / `portal.` / `<tenant>.aeisoftware.com` vía tunnel propio in-cluster — ver § "Tunnel Cloudflare del testbed" |

> ⚠️ **Invariantes del host cruzoil:** NO tocar `comodin-win7`, `pangolin_it911`, `pcd.qcow2`,
> la red `br0` ni los ~28 contenedores docker del host (Odoo 17 de clientes, cloudflared,
> traefik). El gateway de la red es `10.9.13.253`, no `.1`.

## Staging nuevo en la nube COTAS — `cotas-staging` (2026-08-09)

Primer entorno de la **nueva arquitectura** (`docs/CLOUD-STRATEGY-2026-08.md`): Longhorn
thin-provisioned re-tuneado, **sin VM de Postgres** (los tenants llevarán CNPG por namespace),
techos por namespace. Desplegado en el **proyecto IT911** de la nube COTAS
(`cloudscz.cotas.com.bo`, PCD 2026.4 CE — acceso vía VPN, ver `~/it911/cloud.cotas.com/ACCESS.md`).

| Elemento | Valor |
|:---|:---|
| VMs | `aei-stg-1..3` = m1.xlarge (8 vCPU / 16 GB / 160 GB root) + volumen cinder 150 GB dedicado a Longhorn (`/var/lib/longhorn`) |
| Red | `IT911` 192.168.0.0/24 (geneve MTU 1440) → router → `net4002`; fixed .135/.208/.196 |
| Floating IPs | `10.40.2.248` / `.245` / `.220`; **VIP kube-vip `192.168.0.150` ← FIP `10.40.2.210`** (puerto neutron `aei-stg-vip` + allowed_address_pairs) |
| Kubeconfig | `infra/k3s-ha/.kubeconfig.cotas-staging` (gitignored) — apunta a `https://10.40.2.210:6443` |
| Inventario | `infra/environments/cotas-staging.env` |
| K3s | v1.36.3, 3 servers HA + Cilium + Traefik + Longhorn (validado con PVC de prueba) |
| Longhorn | réplica **2**, overprovisioning **200%**, minimal-available **10%**, `storageReserved` **5 GB**/disco, RecurringJobs `snapshot-delete` (diario, retain 2) + `filesystem-trim` (semanal) |
| Postgres | **CNPG por tenant** (operador CloudNativePG 1.30.0 instalado en ns `cnpg-system`): cada tenant lleva un Cluster `pg` single-instance en su namespace, creado por el portal con `PG_TOPOLOGY=cnpg` — validado en vivo 2026-08-09 (initdb con credenciales del portal, quota `requests.storage` 16Gi enforced, PVC en exceso rechazado). ⚠ Los pods CNPG necesitan `CiliumNetworkPolicy` → `kube-apiserver` (generada por el portal, `pg_cilium_apiserver_policy_manifest`) |
| Tunnel/dominios | **el comodín `*.aeisoftware.com` corre AQUÍ desde 2026-08-09** — mismo tunnel `afc7a49a` movido desde cruzoil (connectors de cruzoil en `replicas=0`, rollback fácil). `staging.` / `www.` / `portal.aeisoftware.com` verificados 200 |
| Stack SaaS | **DESPLEGADO y MIGRADO (2026-08-09)**: `odoo-stg` + `portal-stg` (ns `staging`, branch `feat/cloud-portability`, portal `PG_TOPOLOGY=cnpg`) + portal prod (ns `aeisoftware`) + CNPG de plataforma (`pg` en `aeisoftware`, BD `staging` migrada desde cruzoil — dump 65MB + filestore 59MB — y **limpiada: 0 tenants**, 12 saas.instance borradas; 9 suscripciones quedaron como histórico). Service `postgres` 5000→5432 → primario CNPG (`k8s/04b-postgres-cnpg.yaml`) |

Convivencia: el **testbed cruzoil sigue vivo** (arquitectura anterior, tunnel comodín, admin
SaaS en ns `staging`). `cotas-staging` es el candidato a reemplazarlo como Staging permanente
cuando tenga el stack completo (CNPG, portal, tunnel propio).

> ⚠️ **Capacidad de storage Longhorn muy justa (desde 2026-08-08):** un tenant real se quedó en
> `error` por falta de espacio para un replica (ver `docs/wiki/AEI-Assistant.md` § Auto-enable /
> memoria de proyecto `testbed_cruzoil` para el diagnóstico completo — el fix real fue bajar
> `storageReserved` estático por disco en `nodes.longhorn.io`, no `numberOfReplicas` ni el setting
> global de porcentaje). Tras el fix, nodos 1 y 2 quedaron con solo ~6.2 GB libres cada uno, nodo 3
> con ~27.6 GB. **Revisar headroom real antes de provisionar un tenant nuevo** — no asumir que
> alcanza.

## Tunnel Cloudflare del testbed

Desde el **2026-07-29** el testbed tiene su propio tunnel cloudflared, que recupera la
integración comodín que existía en COTAS: una sola ruta hacia Traefik, y provisionar un
tenant nuevo **no requiere ninguna llamada a la API de Cloudflare**.

| Elemento | Valor |
|:---|:---|
| Tunnel ID | `afc7a49a-166d-4505-92de-b9aad8fb1e32` (account `2755b41b811dc9afc7396ed5d1e27644`) |
| Dónde corre | **In-cluster**: `k8s/07-cloudflare-tunnel.yaml`, namespace `cloudflare`, 2 réplicas |
| Ruta comodín | `*.aeisoftware.com` → `http://traefik.kube-system:80` (config remote-managed) |
| Token | `CLOUDFLARE_TUNNEL_TOKEN` en `.secrets.env.testbed` (gitignored) |
| Verificado | 2026-07-29 — ver tabla de hostnames más abajo |

### Hostnames servidos (verificado 2026-07-29)

El testbed reusa **los mismos dominios que tenía el clúster productivo de COTAS**. Todos
estaban en 404 desde el desmantelamiento, así que reusarlos no desplazó nada.

| URL | Backend | Estado |
|:---|:---|:---|
| `https://www.aeisoftware.com` | `odoo-stg-svc` (namespace `staging`) | ✅ HTTP 200 — *Login \| AEI Software* |
| `https://staging.aeisoftware.com` | `odoo-stg-svc` | ✅ HTTP 200 |
| `https://portal.aeisoftware.com/healthz` | `portal` (namespace `aeisoftware`) | ✅ HTTP 200 `{"status":"ok"}` |
| `https://portal-stg.aeisoftware.com/healthz` | `portal-stg` | ✅ HTTP 200 |
| `https://demo1.aeisoftware.com` | `odoo` (namespace `odoo-demo1`) | ✅ HTTP 200 |
| `https://admin.aeisoftware.com` | — | 404 a propósito: `06-odoo-admin.yaml` está excluido |

`www.` lo sirve el Odoo de **staging** porque el stack `odoo-admin` (que servía `admin.` y
`www.` en COTAS) no se despliega en el testbed. Un tenant nuevo queda publicado en
`<tenant_id>.aeisoftware.com` sin ninguna llamada a la API de Cloudflare: lo genera el portal
(`portal/k8s_utils/manifests.py:580`) y el comodín del tunnel ya lo cubre.

> Nota: las peticiones con user-agent de herramienta (curl por defecto) reciben
> `HTTP 403` + `cf-mitigated: challenge` — son las reglas WAF de zona que sobrevivieron a COTAS
> (`infra/apply-cf-security-rules.sh`). Con user-agent de navegador pasan. No es un fallo del
> tunnel; tenerlo en cuenta al diagnosticar con curl.

El tunnel corre **dentro del clúster a propósito**: su servicio destino es
`traefik.kube-system`, un nombre DNS que solo resuelve vía CoreDNS. Como contenedor docker
en el host cruzoil devolvería 502. Además así no se toca el docker del host ni sus ~28
contenedores de terceros.

> ⚠️ Es un tunnel **distinto** al del host cruzoil (contenedor `6ad434184e13`, que sirve las
> cargas de terceros). No correr `setup_cloudflare_wildcard_tunnel.py` contra ese: su paso 2
> reemplaza todas las rutas del tunnel que reciba en `CF_TUNNEL_ID`.

### Por qué se descartó `*.test.aeisoftware.com`

El Universal SSL de Cloudflare cubre **un solo nivel** de subdominio. El certificado servido es:

```
subject = CN=aeisoftware.com
SAN     = DNS:*.aeisoftware.com, DNS:aeisoftware.com
```

Consecuencia medida el 2026-07-29: `demo1.test.aeisoftware.com` **resuelve por DNS** y la ruta
del tunnel hasta hace match (cloudflared compara por sufijo), pero el handshake TLS muere en el
edge con `alert 40 handshake_failure` — no existe certificado que cubra dos niveles. Servir el
esquema `test.` exigiría **Advanced Certificate Manager** (~10 USD/mes), que no aporta nada a un
laboratorio.

**Decisión (2026-07-29): se abandona `test.aeisoftware.com`** y el testbed usa los dominios de
un nivel del ex-productivo. `BASE_DOMAIN="aeisoftware.com"` en
`infra/environments/testbed.env`; los hosts de los Ingress salen de `envsubst ${BASE_DOMAIN}`
en `apply-manifests.sh`, así que re-aplicar es idempotente y ya no hay alias `-tb` que se
pierdan. El tenant `demo1`, provisionado antes del cambio, conserva sus hosts viejos y se le
añadió `demo1.aeisoftware.com`; los tenants nuevos ya nacen con el esquema correcto.

## Entorno por defecto de los scripts

Desde el 2026-07-28 los orquestadores usan **`infra/environments/testbed.env`** cuando se invocan
sin argumento (antes era `cotas.env`, que apuntaba a infraestructura ya desmantelada):

| Script | Línea |
|:---|:---|
| `infra/k3s-ha/deploy-k3s-cluster.sh` | `:35` |
| `infra/k3s-ha/07-join-k3s-workers.sh` | `:27` |
| `infra/postgres-ha/deploy-all.sh` | `:39` |
| `infra/apply-manifests.sh` | `:27` (`--env`) |

Los secretos se resuelven por entorno automáticamente: `.secrets.env.testbed`,
`infra/k3s-ha/.env.testbed`, `infra/postgres-ha/.env.testbed` /
`.secrets.generated.testbed`. Aun así, pasar el entorno explícito sigue siendo la forma más
segura de operar:

```bash
./infra/k3s-ha/deploy-k3s-cluster.sh infra/environments/testbed.env
./infra/postgres-ha/deploy-all.sh    infra/environments/testbed.env
./infra/apply-manifests.sh --env     infra/environments/testbed.env
```

`cotas.env` se conserva en el repo como **plantilla del entorno productivo anterior** (topología de
3+3 nodos, Ceph, PG HA de 3 nodos) — útil como punto de partida al dimensionar el nuevo proveedor,
pero su infraestructura ya no existe.

## AI Agent (aei_assistant) — build en curso, 2026-08-07/08

Nueva funcionalidad: agente de IA opcional por tenant en Discuss. Ver
[AEI Assistant](AEI-Assistant.md) para arquitectura, guardrails, BYOK y billing. Mientras se
construye (Phase 1 y 2 completas, verificadas en vivo), **`staging` y `portal-stg` apuntan
temporalmente a `feat/cloud-portability`** en vez de `main`:

| Recurso | Normal | Ahora mismo |
|:---|:---|:---|
| `odoo-stg-conf` (ConfigMap, key `addon-git-branch`) | `main` | `feat/cloud-portability` |
| `portal-stg` imagen | `portal:main` | `portal:feat-cloud-portability` |
| `portal-stg` env `AGENT_IMAGE` | (sin setear → `agent:stable`, no existe) | `agent:feat-cloud-portability` |

**Esto confirmó en vivo el pendiente #1 de abajo**: un tenant nuevo provisionado por `portal-stg`
mientras corría `:main` recibió una NetworkPolicy con el CIDR viejo de COTAS
(`192.168.0.0/24`) en vez del real del testbed (`10.9.13.0/24`) — Postgres inalcanzable,
`Connection timed out`. Mitigado apuntando al build de `feat/cloud-portability`, no hay que
volver a tocarlo mientras este branch siga siendo el que corre ahí.

**Revertir cuando el branch se mergee a `main`** (o antes, si hace falta volver a probar algo en
`main` tal cual está hoy):
```bash
kubectl patch configmap odoo-stg-conf -n staging --type merge -p '{"data":{"addon-git-branch":"main"}}'
kubectl set image deployment/portal-stg -n staging portal=ghcr.io/aei-software/aei-odoo-saas/portal:main
kubectl set env deployment/portal-stg -n staging AGENT_IMAGE-   # unset, vuelve al default del código
kubectl rollout restart deployment/odoo-stg deployment/portal-stg -n staging
```

## Pendientes abiertos del branch `feat/cloud-portability`

1. **Rebuild de la imagen del portal** — `PG_NETWORK_CIDR` ya es configurable
   (`portal/k8s_utils/manifests.py:26`), pero la imagen `:stable`/`:main` desplegada hardcodea
   `192.168.0.0/24`; la NetworkPolicy del tenant demo1 se parcheó a mano. **Confirmado en vivo de
   nuevo el 2026-08-08** contra `portal-stg` (ver § "AI Agent" arriba) — sigue sin mergearse a
   `main`, así que el próximo deploy desde `main` (sin el workaround manual) lo vuelve a pisar.
2. ~~**Ruta Cloudflare** `*.test.aeisoftware.com → https://10.9.13.20` — se crea a mano.~~
   **Resuelto el 2026-07-29** con un tunnel propio in-cluster: `*.aeisoftware.com →
   http://traefik.kube-system:80` (ver § "Tunnel Cloudflare del testbed"). Sigue vigente el
   aviso: **NO** correr `setup_cloudflare_wildcard_tunnel.py` contra el tunnel del host
   cruzoil — su paso 2 reemplaza todas las rutas.
3. ~~**Esquema de nombres / TLS**~~ — **decidido el 2026-07-29**: se usan los dominios de un
   nivel del ex-productivo (`staging.` / `www.` / `portal.` / `<tenant>.aeisoftware.com`) y se
   descarta `*.test.aeisoftware.com`. Ver § "Por qué se descartó `*.test.aeisoftware.com`".
