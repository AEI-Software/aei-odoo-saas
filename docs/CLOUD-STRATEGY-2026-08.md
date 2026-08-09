# Estrategia de Infraestructura Cloud — 2026-08

> **Fecha:** 2026-08-09 · **Rama:** `feat/cloud-portability` · **Autor:** análisis asistido (Claude), revisión adversarial de fuentes en 3 pasadas.
>
> **Premisa arquitectónica (decisión del owner — restricción, no pregunta):** se venden contenedores Odoo independientes por tenant; el namespace del tenant puede contener contenedores add-on (hoy el asistente IA, mañana más productos monetizables); el tenant tiene un TECHO que no puede superar, pero los recursos NO se reservan por adelantado (el incidente de reserva total de Longhorn del 2026-08-08 agotó el storage del testbed — `docs/wiki/Environment-Status.md`); el techo de storage debe sumar TODOS los contenedores del namespace; Postgres por tenant dentro del namespace es aceptable; Patroni HA queda descartado en todas las variantes (no autoconvergía y añadía puntos de falla). Se requieren dos entornos INDEPENDIENTES: Staging y Producción.
>
> Datos de referencia del repo (autoritativos para toda la aritmética): `portal/k8s_utils/manifests.py` (`PLAN_RESOURCES`, `AGENT_PLAN_RESOURCES`, PVC Odoo 10Gi, PVC agente 1Gi) y `docs/wiki/Cloud-Provider-Cost-Analysis.md` (análisis 2026-07).

## Resumen ejecutivo

| # | Pregunta | Recomendación |
|---|---|---|
| 1 | Hosting | **Vultr sigue primero, GCP segundo** — pero sobre **VMs planas + K3s + Longhorn** (no VKE con CSI del proveedor), porque el CSI del proveedor factura el tamaño *provisionado* del PVC (el techo), no el uso thin. Cotizar COTAS en paralelo por latencia en Bolivia. |
| 2 | Storage | **Mantener Longhorn, re-tuneado**: réplica 2, overprovisioning 100–200%, reserva mínima 25% (10% si disco dedicado), `storageReserved` explícito por disco, jobs de snapshot-delete y trim. Techo por tenant = `ResourceQuota requests.storage` que suma todos los PVC del namespace. |
| 3 | Postgres | **CloudNativePG, un cluster de 1 instancia por tenant, sin standby** (Patroni fuera en ambas variantes). Costo: ~+8.5 vCPU / +9 GiB de requests vs. un PG único compartido para 50 tenants — se paga a cambio de aislamiento de fallas y PITR por tenant. |
| 4 | COTAS 3 VMs | **Factible.** Spec mínima a cotizar: **3× 16 vCPU / 64 GB RAM / 500 GB NVMe** (cubre el caso peor: mix 70/25/5 + PG por tenant + N-1). Con 50 Starter puros y PG compartido bastaría 3× 8 vCPU/32 GB, pero no deja crecer. HA real: quórum etcd sí; storage sobrevive a 1 nodo con réplica 2; la BD no es HA en ninguna variante. **No se halló pricing público de COTAS — se requiere cotización formal.** |
| 5 | Staging/Prod | **Mantener el testbed cruzoil como Staging** (clúster físicamente separado, costo marginal $0) y desplegar Producción limpia en el proveedor elegido. Namespaces/vCluster en las mismas 3 VMs quedan descartados por blast radius. |

---

## 1. Recomendación de hosting (actualiza el análisis 2026-07)

El análisis de julio (`docs/wiki/Cloud-Provider-Cost-Analysis.md`) concluyó **Vultr primero (~$70–90/mes de arranque), GCP segundo (~$85–160)**, con AWS ~2× por su control plane de $73/mes fijo — cifra consistente con fuentes externas: EKS cobra $0.10/h por clúster ≈ $72/mes [10], AKS no cobra control plane en su tier base [10], y GKE regala el primer clúster zonal (no verificado) [10]. Una carga pequeña ronda $100/mes en EKS, $80 en AKS y $85 en GKE (no verificado) [10].

**Qué cambia con la nueva premisa:**

1. **Thin provisioning invalida el CSI del proveedor como default.** El block storage de proveedor factura por GB *provisionado*. Con el techo actual por tenant (PVC Odoo 10Gi + PVC agente 1Gi = 11Gi), 50 tenants = **550 Gi provisionados**; en Vultr a $1/10GB (análisis 2026-07) son **~$55/mes solo de discos**, y **~$80/mes** (800 Gi) si se añade PG por tenant (+5Gi c/u) — pagando espacio que los tenants no usan. Con **Longhorn sobre el disco NVMe incluido en las VMs**, el overprovisioning es una perilla nuestra [5] y el costo marginal del techo es $0. Conclusión: **VMs planas + K3s + Longhorn** (exactamente el stack ya validado en el testbed) en lugar de VKE/GKE con CSI gestionado.
2. **Latencia LatAm para Bolivia.** Ninguno de los cuatro tiene región en Bolivia; lo más cercano es Brasil/Chile en los hyperscalers y São Paulo en Vultr. Un datacenter en el país (COTAS u otro proveedor local) siempre ganará en RTT — es el único argumento técnico fuerte a favor de COTAS pese a la mala experiencia previa. COTAS ofrece formalmente IaaS/PaaS/SaaS y datacenters en Bolivia (no verificado) [14], pero **no publica pricing ni SLA** (no verificado) [14] — ver §4.
3. **Créditos para startups.** GCP/AWS/Azure tienen programas de créditos para startups que pueden cubrir 6–12 meses de la factura; si se obtiene uno, GCP pasa a primera opción durante la vigencia del crédito (autoscaling superior + interoperabilidad S3 de GCS ya validada en el plan de julio). No se citan montos porque no fueron verificados en esta pasada.
4. **Oracle Cloud free tier: descartado como base.** El allowance Always Free de Ampere A1 se recortó a 1,500 OCPU-h y 9,000 GB-h/mes (= 2 OCPU / 12 GB siempre encendidos) desde el 15-06-2026 [1], sin anuncio público (no verificado) [1], con riesgo de terminación de instancias por encima del límite (no verificado) [1]. Nadie construye producción sobre un free tier que se recorta en silencio.

**Recomendación:** Vultr, 3 VMs dedicadas (spec de §4) + K3s HA + Longhorn + tunnel Cloudflare in-cluster (todo ya probado en cruzoil), con `vultr.env` como inventario. GCP como plan B inmediato si aparece crédito de startup. Cotización COTAS en paralelo solo por latencia — sin compromiso hasta ver precio y SLA escritos.

## 2. Estrategia de storage thin-provisioned

### Veredicto: Longhorn se queda, re-tuneado (no se reemplaza)

Los reemplazos posibles pierden contra la premisa: CSI de proveedor = facturación thick del techo (§1); Ceph = el stack que acabamos de abandonar con COTAS, sobredimensionado para 3 nodos. El incidente del 2026-08-08 no fue un defecto de Longhorn sino de configuración: el fix real fue bajar el `storageReserved` estático por disco en `nodes.longhorn.io` (`docs/wiki/Environment-Status.md`), no la réplica ni el porcentaje global.

**Settings exactos para el nuevo entorno:**

| Setting | Valor | Fundamento |
|---|---|---|
| `default replica count` | **2** | Recomendación de producción de Longhorn para disponibilidad de datos [2]. El default de la StorageClass es 3 (no verificado) [6] — bajarlo explícitamente. |
| `Storage Overprovisioning Percentage` | **200%** (default; rango sostenible 100–200%) | [5]; con disco compartido con el SO, usar 100% [2]. |
| `Minimal Available Storage Percentage` | **25%** si el disco es compartido con el root [2]; **10%** si se monta un disco dedicado a Longhorn (no verificado) [2]. Al menos 25% previene `DiskPressure` (no verificado) [5]. |
| `storageReserved` (por disco, en `nodes.longhorn.io`) | Valor explícito y bajo en discos dedicados | La lección del incidente: este campo estático, no el porcentaje global, era lo que agotaba el espacio. |
| Recurring job `snapshot-delete` | Activo, retención corta | Backups/rebuilds/expansiones crean snapshots ocultos que consumen espacio (no verificado) [5]; borrar archivos en el FS no libera bloques del block device (no verificado) [5]. |
| Recurring job `filesystem-trim` | Activo, escalonado (pocos volúmenes a la vez) | Disponible desde v1.4.0; el job es costoso en recursos (no verificado) [5]. |
| `Allow Volume Creation With Degraded Availability` | `true` (default desde v1.1.0, no verificado) [6] | Permite provisionar aunque un nodo esté justo; monitorear volúmenes degraded. |

### Evidencia en vivo del testbed (2026-08-09, lectura directa)

Chequeo read-only sobre el cruzoil actual, que confirma tanto el problema como la palanca:

- `storage-over-provisioning-percentage` = **100** (el valor conservador; la tabla de arriba propone 200) y `storage-minimal-available-percentage` = 10.
- Por nodo: ~83 GB de disco, solo **~19 GB realmente usados** (~64 GB libres en el filesystem), pero **72–73 GB "scheduled"** (comprometidos) en los nodos 1 y 2 — el clúster está "lleno" en papel con tres cuartos del disco vacío. Es exactamente el desperdicio que motiva esta estrategia: la capacidad que gobierna es la *programable* (`(máx − reserva) × overprov%`), no la usada.

### Techo por namespace: `ResourceQuota` sumando todos los contenedores

Kubernetes ya da la primitiva exacta que pide la premisa: `requests.storage` en una `ResourceQuota` limita **la suma de los tamaños solicitados de todos los PVC del namespace** — Odoo (10Gi) + agente (1Gi) + PG opcional (5Gi propuesto):

```yaml
apiVersion: v1
kind: ResourceQuota
metadata: { name: tenant-ceiling, namespace: odoo-<tenant> }
spec:
  hard:
    requests.storage: 16Gi        # suma: PVC odoo + PVC agente + PVC pg
    persistentvolumeclaims: "3"
    limits.cpu: "4"               # techo compute del namespace completo
    limits.memory: 6Gi
```

Esto satisface ambas mitades de la premisa: el techo existe (nadie puede crear PVCs que sumen más), y nada se reserva por adelantado (Longhorn provisiona thin; los limits de CPU/RAM no reservan — el scheduler solo mira requests [4]).

**Caveats honestos:**

- `requests.storage` limita el tamaño **solicitado**, no el uso vivo. Un tenant con PVC de 10Gi puede tener 1Gi escrito o 10Gi — la quota no distingue. El techo real de escritura lo impone el tamaño del filesystem del volumen, no la quota.
- El **tamaño real** de un volumen Longhorn puede superar su spec por los snapshots históricos (no verificado) [5] — es decir, el consumo agregado en disco puede exceder la suma de los techos. Mitigación: los recurring jobs de la tabla.
- La quota no gobierna el espacio de **réplicas**: cada Gi usado cuesta 2 Gi raw con réplica 2 [2]. La aritmética de capacidad de §4 lo incorpora.
- El portal debe crear la `ResourceQuota` en `create_tenant` y **ampliarla en upgrade de plan** — hoy no existe ese manifest en `portal/k8s_utils/manifests.py`; es trabajo nuevo.

## 3. Veredicto: Postgres por tenant

Patroni HA está **fuera en ambas variantes** — decisión ya tomada (no autoconvergía, sumaba HAProxy/PgBouncer/etcd como puntos de falla). La comparación es *CNPG por tenant (1 instancia)* vs *1 PG compartido single-instance*.

**Sizing propuesto por tenant** (derivado de la guía CNPG, no de `PLAN_RESOURCES`): `shared_buffers` default 128MB (no verificado) [4]; la regla CNPG es shared_buffers = 25% de la memoria — 256MB ⇒ 1GB de contenedor [4] — así que 128MB ⇒ **512Mi de contenedor**. CNPG recomienda QoS Guaranteed (requests = limits) para PG [4] (no verificado el detalle, verificada la regla de equivalencia), es decir **250m/512Mi req=lim** + PVC 5Gi.

| | Por tenant (CNPG ×50) | Compartido (1 instancia) |
|---|---|---|
| CPU requests | 50 × 250m = **12.5 vCPU** | ~4 vCPU (estimación de diseño para 50 BDs) |
| RAM requests | 50 × 512Mi = **25 GiB** (reservada, por Guaranteed) | ~16 GiB |
| Storage (techo) | 50 × 5Gi = **250 Gi** | ~100–200 Gi (un volumen) |
| Delta | **+8.5 vCPU, +9 GiB, +~100 Gi** de requests | — |
| Falla de un nodo | Solo caen los PG de tenants en ese nodo; reinician en otro nodo desde la réplica Longhorn (minutos) | Si cae el nodo del PG, caen **los 50 tenants** a la vez — dominio de falla compartido (no verificado) [3] |
| Backup / restore | Plugin barman-cloud: sidecar en el pod del primario [7 — verificado que los sidecars ejecutan backup y WAL], full + **PITR por tenant** contra object store [7 (no verificado el PITR per se, verificado en [3] el modelo por-workload: PITR independiente sin reproducir WAL ajeno (no verificado))]. Un ObjectStore dedicado por cluster (no verificado) [7]. Restore = bootstrap de un cluster nuevo, no in-place (no verificado) [7]. | pgBackRest/barman global; restaurar UN tenant a un punto en el tiempo exige restore completo aparte + dump de esa BD — operativamente feo. |

La arquitectura recomendada de CNPG es una base de datos por recurso Cluster [3] — encaja exactamente con "un PG en el namespace del tenant". CNPG advierte que cada cluster trae overhead base fijo que se multiplica (no verificado) [3] — la tabla lo cuantifica — y que en general "aún vas a querer un standby" [15→[3]]: **desviación consciente** — sin standby, el RTO de un tenant es el re-schedule del pod (minutos) + en el peor caso PITR desde S3; aceptable para el segmento, coherente con haber tirado Patroni.

**Veredicto: PG por tenant con CloudNativePG, 1 instancia, sin standby.** El sobrecosto (~+9.6 GiB de RAM reservada en el clúster) compra el aislamiento de fallas, el PITR por tenant y el modelo de negocio "todo lo del tenant vive y se factura en su namespace". Si el presupuesto de la VM aprieta en el arranque, la variante compartida es la palanca de ahorro — pero es deuda: migrar 50 BDs vivas a clusters por tenant después es un proyecto en sí.

## 4. Factibilidad COTAS: 3 VMs grandes en HA para 50 tenants

**Sobre pricing:** no se encontró pricing público de cloud COTAS — su perfil corporativo lista SaaS/PaaS/IaaS y datacenters pero sin precios, tamaños de VM ni SLA (no verificado) [14]. **Se requiere cotización formal**; la referencia interna previa era ~$700/mes por el modelo IaaS 2026-07 (`docs/BUSINESS-REVIEW-2026-07.md`). La spec a cotizar está al final de esta sección.

Valores por tenant (fuente: `portal/k8s_utils/manifests.py`; agente activado en el 100% como cota superior — el techo debe soportarlo aunque la adopción real sea menor):

| Plan | Odoo req | Odoo lim | Agente req | Agente lim |
|---|---|---|---|---|
| Starter | 100m / 512Mi | 500m / 1Gi | 128m / 256Mi | 1 / 1Gi |
| Pro | 250m / 1Gi | 1 / 2Gi | 256m / 512Mi | 1 / 2Gi |
| Enterprise | 500m / 2Gi | 2 / 4Gi | 256m / 512Mi | 1 / 2Gi |

### Caso A — 50 Starter puros

- **Requests:** CPU = 50×(0.100+0.128) = **11.4 vCPU** · RAM = 50×(512+256)Mi = 50×768Mi = **37.5 GiB**
- **Limits:** CPU = 50×(0.5+1) = **75 vCPU** · RAM = 50×(1+1)Gi = **100 GiB**
- **+ PG por tenant:** requests +12.5 vCPU / +25 GiB ⇒ **23.9 vCPU / 62.5 GiB**; limits ⇒ **87.5 vCPU / 125 GiB**
- **+ PG compartido:** requests +4 / +16 ⇒ **15.4 vCPU / 53.5 GiB**

### Caso B — mix 70/25/5 (35 Starter / 12 Pro / 3 Enterprise)

- **Odoo requests:** CPU = 35×0.1 + 12×0.25 + 3×0.5 = 3.5+3+1.5 = **8 vCPU** · RAM = 35×0.5 + 12×1 + 3×2 = 17.5+12+6 = **35.5 GiB**
- **Agente requests:** CPU = 35×0.128 + 15×0.256 = 4.48+3.84 = **8.32 vCPU** · RAM = 35×0.25 + 15×0.5 = 8.75+7.5 = **16.25 GiB**
- **Total requests:** **16.3 vCPU / 51.75 GiB** · **Total limits:** CPU = (17.5+12+6)+(50×1) = **85.5 vCPU** · RAM = (35+24+12)+(35+30)Gi = **136 GiB**
- **+ PG por tenant:** requests ⇒ **28.8 vCPU / 76.75 GiB**; limits ⇒ **98 vCPU / 161 GiB**
- **+ PG compartido:** requests ⇒ **20.3 vCPU / 67.75 GiB**

El overcommit de limits (85–98 vCPU sobre ~48 físicos) es correcto por diseño: el scheduler asigna por requests, no por limits [4] — los limits son el techo contractual del tenant, no una reserva.

### Storage: techo vs. uso thin vs. disco raw

- **Techo (quota):** 50×11Gi = **550 Gi** (sin PG) · 50×16Gi = **800 Gi** (con PG). Nota: el PVC hoy es fijo (10Gi, no escala por plan) — el caso B no cambia el total.
- **Uso thin realista:** un tenant Odoo recién provisionado escribe del orden de 1–2 GiB (filestore + BD inicial; estimación operativa del testbed, no verificada) ⇒ ~**100 Gi vivos** al arranque, creciendo con adopción.
- **Raw necesario con réplica 2 [2]:** lo que gobierna el disco no es el uso vivo (100×2 = 200 Gi raw) sino la **capacidad programable**: Longhorn agenda `(disponible − reserva 25% [2]) × overprov 200% [5]` por nodo, y cada volumen consume asignación ×2 réplicas. Para el peor techo (800 Gi ⇒ 1,600 Gi de asignación entre 3 nodos ⇒ ~533 Gi/nodo): disco/nodo ≥ 533 ÷ (0.75×2) ≈ **356 GB** ⇒ **500 GB NVMe/nodo** deja margen para snapshots ocultos (no verificado) [5] y rebuilds. (Solo Odoo+agente: 1,100÷3÷1.5 ≈ 245 GB ⇒ 300 GB/nodo bastarían.) SSD/NVMe recomendado; HDD solo "funcional" (no verificado) [2].

### Spec mínima por VM (regla: los requests + overhead deben caber en N−1 nodos)

Overhead de plataforma por nodo (K3s/Cilium/Longhorn/portal/cloudflared/traefik): reservar **2 vCPU / 4 GiB** (Longhorn pide mínimo 4 vCPU/4 GiB por nodo, no verificado [2]).

| Variante | Requests totales + overhead (2 nodos) | Por nodo superviviente | **Spec mínima 3 VMs** |
|---|---|---|---|
| A + PG compartido | 15.4+4 = 19.4 vCPU / 53.5+8 = 61.5 GiB | 9.7 vCPU / 30.8 GiB | **3× 8 vCPU / 32 GB** (justo) |
| B + PG compartido | 20.3+4 = 24.3 / 75.75 | 12.2 / 37.9 | **3× 12 vCPU / 48 GB** |
| A + PG por tenant | 23.9+4 = 27.9 / 70.5 | 14 / 35.3 | **3× 16 vCPU / 48 GB** |
| **B + PG por tenant (peor caso)** | 28.8+4 = 32.8 / 84.75 | 16.4 / 42.4 | **3× 16 vCPU / 64 GB** |

**Spec a cotizar a COTAS (y a Vultr como benchmark): 3× VM de 16 vCPU / 64 GB RAM / 500 GB NVMe local, red privada entre las 3, sin IP pública requerida (ingress por Cloudflare Tunnel), + object storage S3-compatible (o una 4ª VM chica para MinIO) para backups.**

### ¿"3 nodos" es HA real?

- **Control plane:** sí — 3 servers K3s dan quórum etcd y toleran la pérdida de 1 nodo.
- **Storage:** con réplica 2 [2] y anti-afinidad de nodo (default estricta, no verificado [6]), cada volumen tiene copias en 2 nodos distintos ⇒ sobrevive a 1 nodo caído en modo degraded; el rebuild posterior consume espacio extra (snapshots de rebuild, no verificado [5]) — otra razón para el margen de disco.
- **Qué muere cuando cae 1 nodo:**
  - *PG por tenant:* los pods (Odoo, agente, PG) de los tenants de ese nodo se re-agendan en los otros 2 y arrancan desde su réplica Longhorn superviviente. Interrupción de minutos **solo para ~⅓ de los tenants**; el resto ni se entera.
  - *PG compartido:* si el nodo caído es el del PG, **los 50 tenants pierden BD simultáneamente** hasta el re-schedule (no verificado) [3] — el blast radius es total aunque Odoo siga corriendo.
  - En **ninguna** variante hay failover de BD en caliente: Patroni se fue y no vuelve. El RTO de BD es re-schedule de pod, no election.

**Veredicto: factible.** 3 VMs de 16/64/500 sostienen los 50 tenants en el peor caso con N−1. El riesgo no es técnico sino comercial: sin pricing público [14], si la cotización COTAS supera lo que costarían ~3 VMs equivalentes en Vultr, la latencia local es lo único que compraría esa prima.

## 5. Separación Staging / Producción

Opciones evaluadas:

1. **Namespaces (o vCluster) en las mismas 3 VMs.** Descartado. Un namespace es solo una partición lógica que comparte control plane y data plane (no verificado) [8]; la actividad de staging puede agotar los límites del API server compartido y tumbar producción [9]; sin ResourceQuotas estrictas los namespaces no limitan consumo en el nodo [9]; y un atacante con acceso a staging puede intentar cruzar el boundary vía ServiceAccounts mal configuradas (no verificado) [9]. Un vCluster aísla el control plane pero solo clústeres separados dan aislamiento físico completo [8]. Y el ahorro es ilusorio: los servicios duplicados cuestan casi lo mismo esté donde esté la frontera [8].
2. **4ª VM pequeña como staging** (K3s single-node en el mismo proveedor). Aislamiento total, misma versión de K8s garantizada, pero es la única opción con costo nuevo recurrente (~$20–48/mes según proveedor, tabla 2026-07).
3. **Mantener el testbed cruzoil como Staging.** Clúster físicamente independiente (el patrón recomendado de blast radius: prod/staging/dev en clústeres separados, no verificado [11]), ya construido, validado y con tunnel propio — **costo marginal $0**.

**Recomendación: opción 3** — cruzoil queda como Staging permanente; Producción se despliega limpia en el proveedor de §1. Razones: máximo aislamiento de blast radius al precio mínimo (un `kubectl` equivocado en staging no puede tocar prod ni compartir su API server [9]); los dos entornos ya son **archivos de inventario distintos** (`testbed.env` / `<proveedor>.env`), que es exactamente el modelo del refactor de portabilidad. Condiciones para que la validación en staging siga valiendo: (a) **misma versión de K3s** en ambos clústeres — validar en versiones distintas es inútil (no verificado) [9]; (b) mismo stack de storage (Longhorn con los settings de §2, aunque con menos disco); (c) DNS: la ruta comodín `*.aeisoftware.com` apunta al tunnel de un solo clúster — al lanzar producción, el comodín migra al tunnel del clúster prod y `staging.aeisoftware.com` se enruta con un hostname explícito al tunnel de cruzoil (los hostnames explícitos preceden al comodín en Cloudflare). Límites asumidos y aceptados para un staging: el host cruzoil aloja cargas de clientes con invariantes intocables y el headroom de disco es justo (~6.2/6.2/27.6 GB libres tras el incidente — `docs/wiki/Environment-Status.md`); suficiente para staging, inaceptable para prod — que es precisamente por qué prod va a otro lado.

## Fuentes

1. https://www.infoq.com/news/2026/07/oracle-cloud-free-tier-limits/
2. https://longhorn.io/docs/1.7.1/best-practices/
3. https://github.com/cloudnative-pg/cloudnative-pg/discussions/2357
4. https://cloudnative-pg.io/documentation/1.20/resource_management/
5. https://longhorn.io/kb/space-consumption-guideline/
6. https://longhorn.io/kb/troubleshooting-volume-pvc-xxx-not-scheduled/
7. https://cloudnative-pg.io/plugin-barman-cloud/docs/concepts/
8. https://www.signadot.com/blog/namespace-based-environments-for-testing-pros-and-cons/
9. https://www.qovery.com/blog/how-to-isolate-your-production-from-staging-with-kubernetes
10. https://sedai.io/blog/kubernetes-cost-eks-vs-aks-vs-gke
11. https://oneuptime.com/blog/post/2026-02-02-k3s-multi-cluster/view
12. https://terminalbytes.com/oracle-cloud-free-tier-changes-2026/
13. https://oec.sh/blog/odoo-multi-tenant-architecture
14. https://www.bnamericas.com/en/company-profile/cooperativa-de-telecomunicaciones-santa-cruz-rl

Fuentes internas del repo: `portal/k8s_utils/manifests.py` · `docs/wiki/Cloud-Provider-Cost-Analysis.md` · `docs/wiki/Environment-Status.md` · `docs/BUSINESS-REVIEW-2026-07.md`.