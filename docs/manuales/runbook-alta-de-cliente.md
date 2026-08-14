# Runbook de Operador — Alta de Cliente (Aei SaaS)

**Producto:** aei-odoo-saas
**Fecha:** 2026-08-14
**Versión:** 1.0
**Audiencia:** operador de AEI Software (no es un documento para el cliente).

---

## Resumen

Dar de alta un cliente de punta a punta tiene cinco fases. Solo la primera está automatizada hoy; el resto son pasos manuales del operador:

| Fase | Qué pasa | Automatizado hoy |
|---|---|---|
| A. Venta / suscripción | Aprovisionamiento del tenant en el cluster | Sí |
| B. Alta del emisor en SBA | Registro fiscal en el facturador SIAT | **No — manual** |
| C. Configuración fiscal del tenant en Odoo | ICPs, diario, productos, compañía | **No — manual** |
| D. Prueba de emisión PILOTO | Validar antes de producción | Manual (procedimiento) |
| E. Entrega al cliente | Checklist final | Manual |

Referencia de fondo: el cierre de este flujo end-to-end es el **hito 14** del roadmap (`docs/wiki/Roadmap-Production-Readiness-100-Tenants.md`), marcado en progreso — el criterio de aceptación ("un tenant nuevo emite una factura PILOTO sin configuración manual del `service_url`") **aún no se cumple de forma automática**: hoy requiere los pasos manuales de las fases B y C.

---

## Fase A — Venta / suscripción (automática)

1. El cliente compra un plan con **imagen custom** desde el sitio (ver `manual-compra-y-primeros-pasos.md` para el flujo visible al cliente).
2. La Orden de Venta se confirma y se paga. Existen dos disparadores posibles del aprovisionamiento:
   - **Trigger de suscripción** (el habitual con el módulo `odoo_k8s_saas_subscription`): al confirmar la orden se crea una `sale.subscription`; cuando su etapa (stage) pasa a **"En Progreso"**, se dispara `action_provision()` — pero **solo si la instancia está en estado `draft` o `error`**.
   - **Trigger de pago** (independiente): la factura pasa a pagada y dispara el mismo aprovisionamiento.
3. Verifique el registro `saas.instance` del cliente:
   - `custom_image` debe reflejar la imagen contratada (fuerza `pull policy: Always`).
   - El estado debe avanzar `draft → provisioning → ready` en un máximo de ~2 minutos tras el aprovisionamiento (hay un cron cada 2 min que consulta `GET /api/v1/instances/{tenant_id}` al portal).
4. Verifique que se enviaron los dos correos automáticos al cliente:
   - **"Instancia en Preparación"** al confirmar la compra.
   - **"Credenciales de Acceso"** (URL del tenant, usuario `admin`, contraseña) cuando la instancia llega a `ready`.
   - Ambos envíos son *best-effort*: un fallo de envío no bloquea el aprovisionamiento. Si el cliente reporta que no recibió el correo, verifique el estado real de `saas.instance` antes de reenviar nada — puede ya estar lista.
5. Se crea también un usuario `soporte@aeisoftware.com` en el tenant con una contraseña generada por el portal. Esa contraseña **nunca se envía por correo al cliente**: queda registrada una única vez como nota interna en el chatter de `saas.instance`. Consúltela ahí si necesita acceso de soporte.

**Gotcha para escalar a desarrollo si el aprovisionamiento no dispara tras el pago:** el trigger de pago depende de que el módulo sobreescriba `_compute_payment_state()` (campo calculado y almacenado en Odoo 18+) — sobreescribir solo `write()` no basta porque la reconciliación de pago normal no pasa por ahí. Si ve una factura pagada y ninguna instancia creada, este es el primer sospechoso.

### Checklist Fase A

- [ ] Orden de venta confirmada y pagada
- [ ] Suscripción en etapa "En Progreso"
- [ ] `saas.instance` existe y llegó a estado `ready`
- [ ] Correo "Credenciales de Acceso" confirmado por el cliente
- [ ] `custom_image` correcta (si el plan la usa)

---

## Fase B — Alta del emisor en SBA (MANUAL hoy)

⚠️ **Este paso es enteramente manual hoy.** No hay automatización entre el aprovisionamiento del tenant y el alta del emisor fiscal — es responsabilidad del operador coordinarlo antes de entregar la instancia. El alta tiene además bugs conocidos (ver más abajo) que no están parcheados en producción.

Fuente: `MANUAL_ADMIN.md` §8 del repositorio `sba`.

### B.1 — Alta de la Empresa (si no existe)

Si el NIT del cliente no tiene todavía una Empresa registrada en SBA:

1. Pantalla **Empresa** (`iam.TabUen`) → Crear.
2. ⚠️ **Bug conocido:** el campo **Código** (`CodUen`) es la clave primaria y **no autoincrementa**; el asterisco de "requerido" no bloquea el envío del formulario del lado del navegador. Si lo deja vacío, el guardado falla con `Argument CodUen is missing`. **Corrección manual:** antes de guardar, calcule el siguiente código libre:
   ```sql
   SELECT MAX("CodUen") FROM dbo."IAM_TabUen";
   ```
   y escriba manualmente `MAX + 1` en el campo Código.
3. ⚠️ **Bug conocido — "Vista sin clave primaria configurada":** afecta a **todas** las Empresas al editar/eliminar/entrar a una ya creada. Corregido en **staging** el 2026-08-03; **no desplegado a producción** (requiere autorización explícita antes de tocar ese host). Si opera contra producción, espere este error y repórtelo — no es un problema del cliente puntual.

### B.2 — Conexión SIAT del emisor

Menú: **Facturación Electrónica → Configuración (Conexiones SIAT) → Crear.**

Complete:

| Campo | Valor / criterio |
|---|---|
| **Empresa** | La `Empresa` (CodUen) dada de alta en B.1. |
| **NIT** | NIT de la empresa cliente. |
| **Usuario / Contraseña SIAT** | Credenciales **SIN delegadas** — no las credenciales del portal del SIN del cliente, sino las delegadas específicamente para facturación electrónica. |
| **Ambiente (CodAmb)** | `1 = Producción`, `2 = Pruebas/PILOTO`. Para un alta nueva, use **PILOTO** primero (ver Fase D) y solo después cree la conexión de Producción. |
| **Modalidad (CodMod)** | `1 = Electrónica`, `2 = Computarizada`. |
| **Código de Sistema (CodSis)** | Código de sistema asignado por el SIN. |
| **Token de Sistema (TokSis)** | ⚠️ El SIN emite un token **distinto para PILOTO que para Producción** — son JWT diferentes, no el mismo token reetiquetado. Pida el token correspondiente al ambiente que está dando de alta. |

⚠️ **Restricción del sistema:** una Empresa (`CodUen`) solo puede tener **una** conexión SIAT en la base de datos (restricción única sobre `CodUen`). No es posible tener PILOTO y Producción activos simultáneamente para el mismo NIT en la misma base — esto es relevante si su ambiente de staging y producción comparten base de datos (normalmente no la comparten, pero verifíquelo).

Luego, dentro de la conexión ya creada:

- **Tipos de documento**: sectores autorizados, formato de representación gráfica, si se envía por correo al cliente final.
- **Configurar Email**: datos de envío de comprobantes por correo.

### B.3 — Sucursal y punto de venta

Use **sucursal 0** y **punto de venta 0** para la casa matriz / punto de venta principal (valores típicos verificados en pruebas reales). Deben coincidir exactamente con lo que el cliente tiene registrado ante el SIN. Si el cliente opera con más de una sucursal o punto de venta, cada uno debe estar dado de alta primero en el SIN con ese mismo código.

### B.4 — Certificado de firma

Si `CodMod = 1` (Electrónica), coloque el certificado de firma del NIT en la ruta `sfl/key/<NIT>/{pk.pem, cer.pem}` del despliegue de SBA que va a usar este emisor (VPS o in-cluster — ver `runbook-sba-in-cluster.md` para el detalle de cómo se monta en el cluster). Sin certificado, la firma de documentos falla.

⚠️ **Por confirmar:** no se encontró documentación que confirme si el certificado también es obligatorio para `CodMod = 2` (Computarizada). Verifíquelo antes de omitir este paso en un alta con esa modalidad.

### B.5 — CUIS/CUFD (los gestiona SBA solo)

**No requiere alta manual.** SBA obtiene y renueva automáticamente el CUFD cada día por punto de venta; el CUIS es de vigencia más larga y también se gestiona solo. Use la opción manual **"Obtener Códigos"** (filtrando Empresa → Sucursal → Punto de Venta) **solo** como contingencia, si un punto quedó sin código vigente tras un corte prolongado del servicio.

### B.6 — Sincronizar catálogos

Menú: **Parámetros SIAT → Sincronizar Catálogos.** Obligatorio después de cada alta de empresa nueva (y cada vez que el SIN publique catálogos nuevos).

### ⚠️ Advertencia — dropdown de ambiente invertido en el admin UI

El formulario real de alta que usted usa en B.2 (Conexiones SIAT) tiene `1 = Producción, 2 = Pruebas` y **coincide** con el valor real que usa el sistema en tiempo de ejecución. Sin embargo, existe **otra pantalla interna del admin UI** (relacionada al Panel de Pruebas SIAT) donde el mismo par de valores 1/2 aparece **invertido** respecto a ese runtime. Es un defecto de código conocido, no una diferencia intencional entre pantallas.

**Regla de oro: nunca confíe en lo que muestra un dropdown para saber en qué ambiente está un emisor.** Antes de emitir cualquier documento, verifique el `CodAmb` real directamente en la base de datos:

```sql
SELECT "CodUen", "NroNit", "CodAmb", "CodMod" FROM dbo."SFL_TabCon";
```

Interpretación correcta y verificada: **`CodAmb = 1` → Producción real (fiscal)**. **`CodAmb = 2` → Piloto/Pruebas (sandbox, sin efecto fiscal)**.

### Checklist Fase B

- [ ] Empresa (CodUen) creada sin error de código faltante
- [ ] Conexión SIAT creada con NIT, credenciales delegadas, `CodAmb` y `TokSis` correctos para el ambiente deseado
- [ ] Sucursal / Punto de Venta dados de alta con el código que el SIN tiene registrado
- [ ] Certificado de firma cargado (si `CodMod = 1`)
- [ ] Catálogos SIAT sincronizados
- [ ] `CodAmb` verificado por consulta SQL directa, no por el dropdown

---

## Fase C — Configuración fiscal del tenant en Odoo

Esta fase configura el lado Odoo para que hable con el emisor dado de alta en la Fase B. El detalle orientado al cliente está en **`manual-facturacion-siat.md`**; aquí se listan los pasos que le corresponden a usted como operador, antes de entregar la instancia.

1. **Ajustes → "Facturación Electrónica"**: complete los 6 campos respaldados por `ir.config_parameter`:
   - `l10n_bo_core.service_url` — la URL del servicio SBA que va a usar este tenant. **La pone el operador.** Apunte al SBA correspondiente al ambiente (staging/PILOTO in-cluster o VPS de producción — ver `runbook-sba-in-cluster.md`).
   - `l10n_bo_core.invoice_mode_code` (Código de modalidad — debe coincidir con `CodMod` de la Fase B).
   - `l10n_bo_core.siat_internal_document_type`, `l10n_bo_core.siat_billing_type`, `l10n_bo_core.siat_tax_document`.

   ⚠️ **Esto NO se automatiza hoy en el first-boot del tenant.** El ICP `l10n_bo_core.service_url` queda **vacío** tras el aprovisionamiento de la Fase A — el tenant no puede emitir hasta que usted lo configure manualmente (UI o XML-RPC).

2. **Datos de la compañía** (Ajustes → Empresas): NIT, razón social, ciudad/municipio, dirección, teléfono — los cuatro son obligatorios para poder emitir.
3. **Diario de ventas** (Contabilidad → Configuración → Diarios → pestaña Facturación Electrónica): sucursal y punto de venta (los mismos códigos dados de alta en B.3), actividad económica **hoja** (la más específica, no el código padre), ciudad, zona, teléfono, dirección.
4. **Productos** (categorías de producto): código de producto SIN y actividad económica (con herencia recursiva a la categoría padre); unidades de medida con su código SIAT (`57 = UNIDAD` es el más común).
5. **Cliente(s) de prueba**: cree al menos un contacto con NIT/CI **ficticio** para la prueba de la Fase D — nunca use un NIT de un tercero real en ambiente PILOTO ni de pruebas.

### Checklist Fase C

- [ ] `l10n_bo_core.service_url` apunta al SBA correcto para el ambiente actual
- [ ] Resto de ICPs de Facturación Electrónica completos y coherentes con `CodMod`/`CodAmb` de SBA
- [ ] Datos de la compañía completos (NIT, ciudad, dirección, teléfono)
- [ ] Diario de ventas con sucursal/PV/actividad configurados
- [ ] Al menos un producto con código SIN y actividad configurados
- [ ] Partner de prueba ficticio creado

---

## Fase D — Prueba de emisión PILOTO

**Nunca pase un cliente a producción sin antes validar el ciclo completo en PILOTO.**

1. Confirme que `l10n_bo_core.service_url` del tenant apunta al SBA de **staging/PILOTO**, no al de producción.
2. Confirme por SQL directa (ver Fase B) que el emisor tiene `CodAmb = 2` en esa instancia de SBA.
3. Emita una factura de prueba desde Odoo, con el partner ficticio de la Fase C: botón **"Generar factura SIAT"**. Verifique que obtiene **CUF** y que el estado pasa a **VÁLIDO**.
4. **Anule** esa factura de prueba y luego **revierta la anulación**, para validar el ciclo completo de vida del documento.
5. Use el botón **"Verificar NIT"** sobre el partner de prueba para confirmar que la consulta al SIN responde correctamente.
6. Solo después de validar los cuatro puntos anteriores sin errores, proceda a producción:
   - Cree una **nueva conexión SIAT** en SBA para el mismo emisor, con `CodAmb = 1` y el `TokSis` de producción (distinto al de PILOTO).
   - Actualice `l10n_bo_core.service_url` (y el diario, si corresponde) para que apunte al SBA de producción.
   - Repita una emisión de prueba **mínima** contra producción antes de entregar al cliente, si el proceso de la empresa lo permite; de lo contrario, la primera emisión real del cliente será la validación.

⚠️ **Nunca emita documentos reales contra NITs de clientes reales en ambiente PILOTO ni de prueba.** Use siempre partners ficticios para estas validaciones — los NITs que existen en los ambientes de staging pertenecen a clientes reales.

### Checklist Fase D

- [ ] Emisión de prueba PILOTO exitosa, con CUF obtenido
- [ ] Anulación y reversión de anulación validadas
- [ ] Verificación de NIT funcional
- [ ] Conexión de Producción creada con su propio `TokSis`
- [ ] `service_url` actualizada a producción antes de la entrega

---

## Fase E — Checklist de entrega al cliente

⚠️ **No existe hoy un documento oficial de "checklist de entrega".** La siguiente lista es una propuesta armada para este runbook combinando las fases anteriores — valídela con el equipo antes de adoptarla como definitiva.

- [ ] `saas.instance` en estado `ready`, URL de la instancia accesible
- [ ] Correo de credenciales confirmado recibido por el cliente
- [ ] Emisor dado de alta en SBA (Fase B) y catálogos sincronizados
- [ ] Certificado de firma cargado, si aplica
- [ ] Configuración fiscal completa en Odoo (Fase C)
- [ ] Prueba de emisión PILOTO exitosa (Fase D)
- [ ] Ambiente cambiado a producción y validado, si el cliente ya factura en real
- [ ] Manuales entregados al cliente: `manual-compra-y-primeros-pasos.md`, `manual-facturacion-siat.md`, `manual-portal-cliente.md`, y `manual-nomina.md` si contrató el módulo de nómina
- [ ] Portal del cliente accesible y probado

---

## Referencias

- `sba/docs/MANUAL_ADMIN.md` — alta de emisor, troubleshooting.
- `sba/docs/MANUAL_USUARIO.md` — Conexiones SIAT, CUIS/CUFD.
- `sba/docs/API_GUIDE.md` — referencia de endpoints `/pub`.
- `aei-odoo-saas/docs/wiki/Roadmap-Production-Readiness-100-Tenants.md` — hito 14 (SBA in-cluster, estado de la automatización).
- `aei-odoo-saas/docs/wiki/Portal-API-Reference.md` — API de aprovisionamiento (Fase A).
- `aei-odoo-saas/docs/wiki/QA-Testing-Battery.md` — batería de pruebas del aprovisionamiento.
- `aei-odoo-saas/docs/manuales/manual-facturacion-siat.md` — versión orientada al cliente de la Fase C.
- `aei-odoo-saas/docs/manuales/runbook-sba-in-cluster.md` — operación del SBA in-cluster referenciado en la Fase C/D.
