# Manuales del producto — Aei SaaS Starter 19.0

Documentación de la solución completa (plataforma SaaS + Odoo 19 con localización boliviana +
AEI Assistant + facturador SBA). En español. Generada el 2026-08-14 a partir del inventario de
documentación de los 5 repos; las capturas de pantalla están pendientes (marcadores `[CAPTURA: …]`).

## Para el cliente (PyME)

| Manual | Contenido |
|---|---|
| [Compra y primeros pasos](manual-compra-y-primeros-pasos.md) | Contratar el plan, pago QR, emails de credenciales, primer login, qué viene preconfigurado, datos de empresa y usuarios |
| [Facturación electrónica SIAT](manual-facturacion-siat.md) | Configuración fiscal (Ajustes, diario, productos, clientes), emitir/anular/revertir, tabla de errores |
| [Nómina boliviana](manual-nomina.md) | Empleados, contratos, boletas, lotes, anticipos/préstamos, aguinaldo, finiquito, planilla MTSS |
| [Reportes](manual-reportes.md) | 10 reportes financieros dinámicos, Kardex físico/costos, Libro Diario, tipo de comprobante, tipo de cambio BCB, plantillas AEI |
| [AEI Assistant](manual-aei-assistant.md) | El chat de IA: qué puede y qué no, crédito de prueba, configurar tu propia API key |
| [Portal del cliente](manual-portal-cliente.md) | Mi cuenta → Suscripciones: upgrade de plan, backups, usuarios extra, mora y suspensión, cancelación |

## Para el operador de la plataforma

| Runbook | Contenido |
|---|---|
| [Alta de cliente end-to-end](runbook-alta-de-cliente.md) | Venta → tenant → alta del emisor en SBA (manual hoy) → configuración fiscal → prueba PILOTO → entrega |
| [SBA in-cluster](runbook-sba-in-cluster.md) | Despliegue, red/NetworkPolicy, BD y certificados, conexión de tenants, incidentes |
| [Actualizar tenants](../../../aei-custom-odoo-images/docs/UPDATING-TENANTS.md) *(repo aei-custom-odoo-images)* | Imagen horneada vs clone, `odoo -u`, flujo recomendado |

Manuales por módulo que viven junto al código (fuente única — no editar las copias staged de la
imagen): `aei-l10n-bo/addons/l10n_bo_stock_reports/MANUAL.md`, `…/l10n_bo_ledger_kardex/MANUAL.md`,
`…/l10n_bo_voucher_type/MANUAL.md`, `…/l10n_bo_payroll_bolivia_base/REGLAS.md`. Para el web-app de
SBA (operador del facturador): `sba/docs/MANUAL_USUARIO.md` y `MANUAL_ADMIN.md`.

**Pendientes de confirmación comercial** (marcados "⚠️ por confirmar" dentro de cada manual):
precio del plan en Bs., métodos de pago además del QR Mercantil, canal de soporte dedicado,
cuál de los dos caminos de "anticipo" de nómina es el oficial, y si el cert de firma aplica a
CodMod=2. Capturas de pantalla: pendientes en todos.
