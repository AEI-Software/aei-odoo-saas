# Runbook de Operador — SBA in-cluster

**Producto:** aei-odoo-saas
**Fecha:** 2026-08-14
**Versión:** 1.0
**Audiencia:** operador con acceso `kubectl` al cluster.

> Este runbook no incluye contraseñas, tokens, IPs de VPS ni nombres de archivo de llaves. Los comandos `kubectl` son genéricos: reemplace `<namespace>` por el namespace real de su entorno.

---

## 1. Arquitectura

Namespace **`sba-piloto`**, con dos Deployments:

- **`sba`** — la app del facturador SIAT, puerto **3001** (`PORT=3001`, `NODE_ENV=production`). Probes de `readiness`/`liveness` contra `GET /health` en ese mismo puerto. PVCs propios para XML y PDF generados; logs en `emptyDir`.
- **`db`** — **PostgreSQL 17**, puerto 5432, PVC persistente, `strategy: Recreate` (no rolling update — solo puede haber una réplica).

Imagen: **`ghcr.io/aei-software/sba:<tag inmutable>`** (hoy fijada a un sha corto de commit, no `latest`). Se construye en el repositorio `sba` mediante un workflow de GitHub Actions (`docker-publish.yml`) que dispara en cambios de `app/**` o del Dockerfile de producción, y publica en GHCR. Este workflow **no reemplaza** el build por `docker compose` del VPS — publica la misma imagen también en GHCR para poder usarla in-cluster.

**El paquete de GHCR es PRIVADO** (código propietario): el cluster no puede tirar de la imagen de forma anónima. Requiere un Secret `docker-registry` (nombre típico `ghcr-pull`) referenciado en `imagePullSecrets` del Deployment `sba`, creado con un **Personal Access Token con permiso `read:packages`**.

```bash
# Verificar que el pull secret existe y no ha expirado (falla de ImagePullBackOff es la señal típica)
kubectl -n <namespace> get secret ghcr-pull
kubectl -n <namespace> describe pod -l app=sba | grep -A5 Events
```

⚠️ No hay un procedimiento documentado de renovación automática del token. Si expira, el síntoma es `ImagePullBackOff`/`ErrImagePull` en el pod `sba` tras un reinicio o reschedule — regenere el token con permiso `read:packages` en GitHub y recree el Secret:

```bash
kubectl -n <namespace> delete secret ghcr-pull
kubectl -n <namespace> create secret docker-registry ghcr-pull \
  --docker-server=ghcr.io \
  --docker-username=<usuario-github> \
  --docker-password=<nuevo-token> \
  --docker-email=<email>
```

---

## 2. Por qué no hay Ingress

El endpoint **`/pub/*`** de SBA (el que usan los tenants para facturar) **no tiene autenticación propia** — es la brecha de seguridad más importante del sistema (ver sección 8). Por eso **no se expone con Ingress**: la única protección es la `NetworkPolicy` in-cluster.

**NetworkPolicy `sba-isolation`** (namespace `sba-piloto`):
- **Ingress permitido**: solo desde pods en namespaces con label `managed-by: saas-portal` (los namespaces de tenants) y desde el namespace `staging` (donde vive el Odoo admin interno), puerto `3001/TCP`.
- **Egress permitido**: DNS hacia `kube-dns`; `0.0.0.0/0` en `443/TCP` (para llegar al SIN) y `587/TCP` (SMTP, si algún emisor lo usa); y hacia el pod `db` en `5432/TCP`.

**NetworkPolicy `db-isolation`**: solo permite tráfico hacia la base desde pods `app: sba` dentro del mismo namespace — la base queda aislada incluso de otros pods del propio namespace.

### Gotcha de Cilium — por qué el egreso de los tenants vive en el template del portal

El egreso **desde** un namespace de tenant **hacia** `sba-piloto` no se resuelve con un `ipBlock` genérico. Con **Cilium**, un `ipBlock` (rango de IPs tipo `0.0.0.0/0`) **nunca matchea pods dentro del mismo cluster** — ese tipo de regla solo aplica a tráfico que sale realmente a Internet. El `0.0.0.0/0:443` que cada tenant ya tiene para salir a Internet **no sirve** para llegar al Service de SBA, aunque este escuche en el mismo puerto 443/3001.

Por eso la regla de egreso real vive en el **template de NetworkPolicy que el portal genera para cada tenant** (función Python en el código del portal, no un archivo `.j2` suelto), con una regla propia:

```yaml
# Fragmento representativo de la regla de egreso hacia SBA en el template de tenant
egress:
  - to:
      - namespaceSelector:
          matchLabels:
            app: sba
    ports:
      - protocol: TCP
        port: 3001
```

**Consecuencia operativa importante:** los tenants aprovisionados **antes** de que se agregara esta regla al template del portal no la tienen en su `NetworkPolicy` actual, y un reinicio/`PATCH` normal del tenant no la regenera (el mecanismo de "restart" del portal solo re-renderiza el ConfigMap, no reaplica el manifiesto completo del Deployment/NetworkPolicy). Si un tenant viejo no puede alcanzar a SBA, **verifique primero si su `NetworkPolicy` tiene esta regla** y aplíquela manualmente si falta:

```bash
kubectl -n <namespace-tenant> get networkpolicy -o yaml | grep -A10 "app: sba"
# Si falta, aplique manualmente el manifiesto de NetworkPolicy actualizado del tenant
kubectl -n <namespace-tenant> apply -f <networkpolicy-actualizada>.yaml
```

Este mismo patrón de "un `ipBlock` no cubre destinos dentro del cluster con Cilium" también aplica al API server de Kubernetes en otras policies del portal — no es un caso aislado de SBA.

---

## 3. Base de datos

**La base de SBA en el cluster no nace vacía ni se bootstrapea desde el repo.** El repositorio `sba` no trae seed ni migraciones utilizables para un despliegue nuevo — la base nace de un **`pg_dump -F c`** de la base de un ambiente origen (staging), restaurado manualmente después de desplegar el manifiesto de Postgres:

```bash
kubectl -n <namespace> apply -f 02-postgres.yaml
# ... esperar a que el pod db esté Ready ...
kubectl -n <namespace> exec -i deploy/db -- pg_restore --no-owner -d <basededatos> < dump.pgdump
```

**PILOTO vs producción no es una variable de despliegue, vive dentro de los datos**:

- `dbo."SFL_TabCon"` — columna **`CodAmb`** por emisor (`1 = Producción`, `2 = Piloto/Pruebas`). Un dump de staging trae normalmente todos sus emisores en `CodAmb = 2`.
- `dbo."SFL_TabPar"`, `GruPar = '1.2'` — endpoints de Piloto (`GruPar = '1.1'` sería Producción).

Al restaurar un dump de un ambiente a otro (por ejemplo, para preparar un cliente nuevo en un `sba-piloto` que nació de staging), la verificación del `CodAmb` real por SQL directa (ver `runbook-alta-de-cliente.md`, Fase B) es obligatoria — no confíe en la etiqueta del ambiente de origen del dump.

---

## 4. Certificados de firma

Los certificados de firma digital por NIT se montan como Secret de solo lectura en **`/app/sfl/key/<NIT>/`**:

```bash
kubectl -n <namespace> get secret sba-sfl-key -o jsonpath='{.data}' | jq 'keys'
```

Como las claves de un Secret de Kubernetes no admiten `/`, el nombre de cada clave usa un formato plano (por ejemplo `nit-<NIT>-pk`, `nit-<NIT>-cer`) y el Deployment reconstruye la ruta real con `items` en el volumen:

```yaml
volumes:
  - name: sfl-key
    secret:
      secretName: sba-sfl-key
      items:
        - key: nit-<NIT>-pk
          path: <NIT>/pk.pem
        - key: nit-<NIT>-cer
          path: <NIT>/cer.pem
```

Para agregar el certificado de un NIT nuevo: agregue las claves correspondientes al Secret `sba-sfl-key` y agregue el par `items` correspondiente al Deployment (o al manifiesto que lo genera), luego reinicie el pod `sba`:

```bash
kubectl -n <namespace> rollout restart deployment/sba
```

Si un emisor no tiene su certificado montado, la firma de documentos falla con un error de archivo no encontrado — no es un error del SIN.

---

## 5. Conectar un tenant

ICP a configurar en el tenant (Odoo → Ajustes, o vía XML-RPC):

```
l10n_bo_core.service_url = http://sba.<namespace-sba>.svc.cluster.local:3001
```

Esto se hace hoy **manualmente por tenant** (ver `runbook-alta-de-cliente.md`, Fase C) — el first-boot del portal todavía no lo automatiza; el ICP queda vacío por defecto tras aprovisionar.

⚠️ **Tenants creados antes de que el template de NetworkPolicy del portal incluyera la regla de egreso hacia `app: sba`** (sección 2) necesitan un parche manual de su propia `NetworkPolicy` para poder alcanzar el Service de SBA — sin esa regla, la conexión se cae aunque el ICP esté bien configurado, y el síntoma se ve como timeout de red, no como error de configuración de Odoo.

---

## 6. Verificación

**Salud del servicio:**

```bash
kubectl -n <namespace> exec -it deploy/sba -- curl -fsS http://localhost:3001/health && echo OK
```

Los probes de `readiness`/`livenessProbe` del propio Deployment ya consultan este mismo endpoint — un pod `Ready` implica que `/health` respondió correctamente.

**Emisión de prueba:** siga el procedimiento de la Fase D de `runbook-alta-de-cliente.md` (emisión PILOTO end-to-end con partner ficticio, verificar CUF, anular y revertir anulación). No hay un script de humo separado documentado para este despliegue — la emisión de prueba real es la verificación de referencia.

---

## 7. Incidentes comunes

| Síntoma | Causa | Acción |
|---|---|---|
| **App en bucle de reinicio** | `DATABASE_URL` inválida o base inaccesible | Revisar `kubectl -n <namespace> logs deploy/sba`; confirmar que `db` está `Ready` |
| **`Error al autenticar` en todas las consultas, `Invalid URL`** | `DATABASE_URL` con caracteres especiales de la contraseña sin URL-encoding (`/`, `+` generados por `openssl rand -base64`) | Usar contraseñas generadas con `openssl rand -hex 32` (sin caracteres especiales), o codificar el valor dentro de `DATABASE_URL` con URL-encoding — nunca pegar la contraseña cruda si contiene `/` o `+` |
| **Todo lo que dependa de rutas de archivo falla con `ENOENT`** (XSD, XML, PDF, JSON, certificados, logs) | Parámetro `ROOTHOME` en `dbo."SFL_TabPar"` (`CodUen=-1`, `GruPar='1.3'`, `CodPar='ROOTHOME'`) apunta a una ruta que no es la del contenedor | Debe ser exactamente `/app/` (el `WORKDIR` de la imagen). Se corrige por SQL directo — no hay opción en la UI. No requiere reinicio del pod, la app lee el parámetro sin caché |
| **CUFD vencido / "sin código vigente"** | El punto de venta quedó sin CUFD tras un corte prolongado | El CUFD se auto-renueva diariamente en operación normal; si un punto quedó sin código vigente, use "Obtener Códigos" manualmente en el admin UI (Empresa → Sucursal → Punto de Venta) |
| **`ImagePullBackOff`** | Secret de pull de GHCR ausente o token expirado | Ver sección 1 — recrear el Secret con un token `read:packages` vigente |
| **Timeout de red desde un tenant, sin error de configuración en Odoo** | `NetworkPolicy` del tenant no tiene la regla de egreso hacia `app: sba` (tenant creado antes del fix del template) | Ver sección 2 — aplicar manualmente la `NetworkPolicy` actualizada al tenant |
| **404 en operaciones de Producción tras migrar un emisor** | Endpoints mal cargados en `SFL_TabPar` `GruPar='1.1'` (Producción) | Verificar los endpoints de Producción contra el catálogo oficial del SIN; problema histórico ya corregido en el origen del dump más reciente, pero puede reaparecer en dumps antiguos |

---

## 8. Pendientes de seguridad

- 🔴 **`/pub/*` sin autenticación por cliente.** Cualquiera que alcance el puerto de SBA y conozca un NIT configurado podría, en teoría, emitir o anular documentos de ese emisor — no hay validación de credencial ni firma por tenant en esas acciones. La `NetworkPolicy` de la sección 2 es hoy la **única** mitigación (restringe quién puede alcanzar el puerto); no reemplaza una autenticación real por API key o firma por NIT, que sigue pendiente de diseño en el roadmap de la solución. **No se debe exponer `/pub` fuera del cluster** (ni siquiera por un túnel/proxy interno) hasta cerrar esa autenticación.
- 🟡 **Validación XSD sin protección de red.** La validación de los XML contra su esquema se ejecuta con una herramienta externa (`xmllint`) sin la opción que le impide resolver referencias de red ni acotar el consumo de entidades — no hay inyección de comandos (la invocación no pasa por un shell), pero deja abierto un vector potencial de tipo XXE/SSRF si alguna vez se valida un XML de origen no confiable. No está deshabilitada por completo, pero le falta ese endurecimiento.

---

## Referencias

- `aei-odoo-saas/infra/sba-piloto/README.md` y los YAML de ese directorio (namespace, Postgres, SBA, NetworkPolicy).
- `sba/docs/MANUAL_ADMIN.md` — troubleshooting general del admin UI.
- `sba/docs/DEPLOYMENT.md` — problemas conocidos de despliegue (`ROOTHOME`, `DATABASE_URL`, endpoints de producción).
- `sba/docs/SECURITY_AUDIT.md` — hallazgos V2 (auth de `/pub`) y V10 (XSD) citados en la sección 8.
- `aei-odoo-saas/docs/wiki/Roadmap-Production-Readiness-100-Tenants.md` — hito 14, contexto y criterio de aceptación de este despliegue.
- `aei-odoo-saas/docs/manuales/runbook-alta-de-cliente.md` — procedimiento de alta de emisor y prueba de emisión PILOTO que usa este SBA.
