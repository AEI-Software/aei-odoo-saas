# Manual de Usuario — Portal del Cliente

**Producto:** Aei SaaS Starter 19.0
**Fecha:** 2026-08-14
**Versión:** 1.0

## Introducción

El **Portal del Cliente** es el lugar donde usted gestiona su suscripción a Aei SaaS Starter
19.0: ver el estado de su instancia, cambiar de plan, descargar backups, revisar usuarios
adicionales y su facturación, y cancelar el servicio si lo necesita. Se accede desde el mismo
sitio web de AEI Software con la cuenta que usó al momento de la compra.

## Requisitos Previos

- Haber completado la compra de Aei SaaS Starter 19.0 (ver "Manual de Compra y Primeros Pasos").
- Tener la cuenta de cliente que creó durante el checkout (correo y contraseña del **sitio de
  AEI Software**, distinta de la contraseña de su instancia Odoo).
- Haber iniciado sesión en el sitio.

## Uso Paso a Paso

### 1. Acceder al portal

1. Inicie sesión en el sitio web de AEI Software con su cuenta de cliente.
2. Vaya a **Mi cuenta → Suscripciones**.
3. Verá el listado de sus suscripciones activas.

   [CAPTURA: listado de suscripciones en Mi cuenta → Suscripciones]

4. Haga clic sobre su suscripción para ver el detalle.

### 2. Ver su instancia y abrirla

En el detalle de la suscripción encontrará una tarjeta con la información de su instancia:

- **URL de la instancia** (clic para abrirla directamente cuando está lista).
- **Estado**: `Ready` (lista) / `Provisioning` (en preparación) / `Suspended` (suspendida) /
  `Error`.
- Plan contratado.
- Botón **Open Instance** (Abrir Instancia).

   [CAPTURA: tarjeta de instancia en el detalle de la suscripción]

Si su plan incluye usuarios y hay usuarios extra activos, también verá una sección de **Uso de
Usuarios** con la cantidad actual, la incluida en el plan, y el cargo estimado por los extra.

### 3. Cambiar de plan (upgrade)

1. En el detalle de su suscripción, haga clic en **Cambiar de plan**.
2. El portal le muestra una página de **comparación de planes** disponibles frente a su plan
   actual.

   [CAPTURA: página de comparación de planes antes de confirmar el cambio]

3. Seleccione el nuevo plan y confirme.
4. El cambio se aplica sobre su instancia automáticamente: se actualizan los recursos asignados
   (memoria y capacidad de procesamiento) según el nuevo plan, y la instancia se reinicia
   brevemente para aplicarlos.

> El cambio de plan ajusta los recursos técnicos de su instancia (CPU/RAM) y la cantidad de
> usuarios incluidos; no requiere que usted haga nada más de su lado.

### 4. Descargar un backup

1. En el detalle de su suscripción, haga clic en **Download Backup** (Descargar Backup).
2. El portal genera y descarga un archivo **ZIP** con una copia completa de su base de datos y
   sus archivos adjuntos.

   [CAPTURA: botón de descarga de backup en el detalle de la suscripción]

> **Límite:** solo puede descargar **un backup cada 24 horas** por instancia. Si intenta
> descargar otro antes de que pase ese tiempo, el portal le indicará cuánto falta para el
> próximo backup disponible.

Se recomienda descargar un backup periódicamente y, especialmente, **antes de cancelar su
suscripción** (ver sección 6).

### 5. Usuarios adicionales y su facturación

Su plan Aei SaaS Starter 19.0 incluye una cantidad de usuarios activos sin costo adicional. Si
su equipo crece más allá de lo incluido:

- El sistema detecta automáticamente la cantidad de usuarios activos en su instancia.
- Los usuarios que excedan lo incluido en el plan se agregan **automáticamente** como una línea
  adicional ("Extra User") en su próxima factura mensual — no necesita solicitarlo ni
  configurarlo manualmente.
- Si la cantidad de usuarios extra baja (por ejemplo, desactivó usuarios), el cargo se ajusta o
  se elimina automáticamente en el siguiente ciclo.

Puede consultar el detalle de usuarios incluidos, usuarios actuales y el cargo estimado en la
sección "Uso de Usuarios" del detalle de su suscripción (ver sección 2).

### 6. Qué pasa si no paga a tiempo

Si una factura de su suscripción vence sin pagarse, el sistema sigue esta secuencia automática:

| Día de atraso | Qué ocurre |
|---|---|
| Día 1 | Correo recordatorio: aviso de pago vencido |
| Día 3 | Correo de aviso final antes de la suspensión |
| Día 5 en adelante | **Suspensión de la instancia** (su sistema deja de estar accesible) + correo de aviso |

En cuanto usted se pone al día con el pago, la instancia se **reactiva automáticamente**, sin
necesidad de contactar a soporte ni de ninguna acción manual adicional de su parte.

### 7. Cancelar la suscripción

1. En el detalle de su suscripción, haga clic en **Cancelar**.

   [CAPTURA: botón de cancelación en el detalle de la suscripción]

2. Al confirmar, su instancia se **suspende de inmediato** (queda inaccesible).
3. Se inicia un **período de gracia de 7 días**. Durante esos 7 días su instancia y sus datos
   siguen existiendo, aunque suspendida.
4. Al cumplirse los 7 días, la instancia y **todos sus datos se eliminan de forma permanente**.

> **Importante:** descargue un backup de su instancia (sección 4) **antes de cancelar**, o a más
> tardar dentro de los 7 días de gracia. Pasado ese plazo, la información no se puede recuperar.

### 8. Canal de soporte

- **Tickets de soporte**: desde el detalle de su suscripción, o directamente en
  **Mi cuenta → Tickets** (`/my/tickets`), puede crear un ticket describiendo su consulta o
  problema. Si su plan incluye una bolsa de horas de soporte mensual, verá en esta misma página
  cuántas horas tiene incluidas, cuántas consumió y cuántas le quedan disponibles ese mes.

  [CAPTURA: sección de tickets de soporte / horas de soporte del mes]

- **Mensajes en la suscripción**: en el detalle de su suscripción también hay una sección de
  comunicación (chatter) donde puede dejar mensajes visibles para el equipo de AEI Software.

⚠️ Por confirmar: no se encontró en la documentación revisada un correo o teléfono de contacto
directo de soporte distinto de los canales del portal (tickets y chatter) — de existir, agréguelo
aquí.

## Preguntas Frecuentes

**P: ¿Perderé mi contraseña de acceso al portal si cambio de plan?**
R: No. El cambio de plan afecta los recursos de su instancia Odoo, no su cuenta del portal ni sus
credenciales de acceso.

**P: Descargué un backup hace unas horas y necesito otro urgente, ¿puedo?**
R: No, el límite es de un backup cada 24 horas por instancia. Espere a que se cumpla el plazo
indicado por el portal.

**P: Mi instancia se suspendió, ¿perdí mis datos?**
R: No. La suspensión (por atraso de pago o por cancelación) no borra sus datos de inmediato.
Los datos se eliminan recién al cumplirse el período de gracia correspondiente (ver secciones
6 y 7).

**P: Cancelé por error, ¿puedo recuperar mi suscripción?**
R: Si todavía está dentro del período de gracia de 7 días, contacte a soporte cuanto antes. Una
vez eliminados los datos tras el período de gracia, no es posible recuperarlos.

**P: Agregué usuarios este mes, ¿cuándo me cobran por ellos?**
R: El cargo por usuarios extra se calcula automáticamente y se incluye en su siguiente factura
mensual, sin que usted tenga que hacer nada.
