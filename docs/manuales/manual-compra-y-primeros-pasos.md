# Manual de Usuario — Compra y Primeros Pasos

**Producto:** Aei SaaS Starter 19.0
**Fecha:** 2026-08-14
**Versión:** 1.0

## Introducción

Este manual explica cómo contratar el servicio **Aei SaaS Starter 19.0** desde el sitio web de
AEI Software, qué ocurre automáticamente después de la compra, y cómo dar los primeros pasos una
vez que su sistema Odoo está listo. Aei SaaS Starter 19.0 es un Odoo 19 alojado en la nube,
preparado de fábrica para el mercado boliviano: empresa en Bolivia, moneda en bolivianos y
facturación con IVA del 13% ya configurados desde el primer ingreso.

No necesita conocimientos técnicos para completar la compra ni para empezar a usar el sistema.

## Requisitos Previos

- Una computadora con navegador web actualizado (Chrome, Firefox o Edge) y conexión a internet.
- Una cuenta de correo electrónico válida y a la que tenga acceso inmediato — ahí llegarán las
  notificaciones de su compra.
- Los datos de facturación de su empresa a mano: nombre completo del contacto, correo, teléfono,
  razón social/nombre de la empresa y **NIT**.
- Para pagar con QR: la aplicación de su banco instalada en el celular, con saldo disponible.
  Esta guía documenta el pago con **QR Mercantil** (Banco Mercantil Santa Cruz); ⚠️ por confirmar
  si el sitio ofrece además otros métodos de pago (transferencia, tarjeta, etc.).

## Uso Paso a Paso

### 1. Elegir su plan

1. Ingrese al sitio web de AEI Software y navegue a la sección de planes / tienda.
2. Ubique el producto **Aei SaaS Starter 19.0**. Este plan incluye 3 usuarios; si necesita más
   usuarios activos, puede agregarlos más adelante desde su portal de cliente (se facturan de
   forma automática cada mes — ver el manual del Portal del Cliente).

   [CAPTURA: página de planes con Aei SaaS Starter 19.0 destacado]

3. Haga clic en **Agregar al carrito**.

⚠️ Por confirmar: el precio mensual exacto del plan Starter en bolivianos no se encontró en la
documentación revisada; verifíquelo en la página del producto antes de confirmar la compra.

### 2. Iniciar el checkout

1. Vaya al carrito de compras y haga clic en **Proceder al pago / Checkout**.
2. El sitio le pedirá **crear una cuenta o iniciar sesión** — este paso es obligatorio y no se
   puede omitir. Esta cuenta es la que usará después para entrar a su **Portal del Cliente**
   (Mi cuenta → Suscripciones).

   [CAPTURA: pantalla de creación de cuenta / inicio de sesión en el checkout]

### 3. Completar los datos de facturación

El formulario de checkout le pedirá únicamente estos campos, todos **obligatorios**:

| Campo | Descripción |
|---|---|
| Nombre completo | Nombre del contacto que gestionará la cuenta |
| Correo electrónico | A este correo llegarán las notificaciones de su instancia |
| Teléfono | Número de contacto |
| Empresa | Razón social o nombre comercial |
| NIT | Número de Identificación Tributaria de la empresa |
| País | Bolivia viene preseleccionado |

No se le pedirá dirección, ciudad ni código postal — esos campos no aplican para este servicio.

[CAPTURA: formulario de checkout con los 6 campos obligatorios]

### 4. Pagar con QR Mercantil

1. En el paso de pago, seleccione **QR Mercantil**.
2. El sistema genera un código QR en pantalla.
3. Abra la aplicación de su banco, escanee el código QR y confirme el pago desde su celular.
4. La página se actualiza automáticamente en cuanto el banco confirma el pago — no necesita
   recargar ni volver a hacer clic en nada.

   [CAPTURA: pantalla con el código QR de pago]

### 5. Qué pasa después de pagar

Apenas se confirma el pago, el sistema empieza a preparar su instancia automáticamente. No
necesita hacer nada más de su lado. Recibirá **dos correos**, en este orden:

**Correo 1 — "Estamos preparando tu sistema Odoo — [nombre de la instancia]"**
Confirma que la compra se procesó y que su sistema está en camino. El estado indicado es
"En preparación". Este correo le avisa que en unos minutos llegará un segundo correo con sus
credenciales.

**Correo 2 — "¡Tu sistema Odoo está listo! — Credenciales de acceso"**
Llega cuando su instancia ya está lista para usarse (normalmente pocos minutos después del
primer correo). Incluye:

- La **URL de su sistema**: `https://<subdominio>.aeisoftware.com`
- **Usuario**: `admin`
- **Contraseña** generada automáticamente

[CAPTURA: ejemplo del correo de credenciales de acceso]

> **Importante:** este segundo correo se elimina de los servidores de AEI Software después de
> enviarse. Guarde la contraseña en un lugar seguro apenas la reciba.

### 6. Primer ingreso

1. Abra el enlace `https://<subdominio>.aeisoftware.com` que recibió por correo.
2. Ingrese con el usuario `admin` y la contraseña del correo de credenciales.

   [CAPTURA: pantalla de login de Odoo con el subdominio de la instancia]

3. **Cambie la contraseña de inmediato**: vaya a **Ajustes → Usuarios y Compañías → Usuarios**,
   abra el usuario `admin` y actualice la contraseña por una de su elección.

### 7. Qué viene preconfigurado de fábrica

Su instancia **no nace vacía**. Aei SaaS Starter 19.0 se crea a partir de una base de datos ya
preparada por AEI Software para Bolivia, así que desde el primer ingreso ya cuenta con:

- Empresa configurada con **país Bolivia**.
- **Moneda boliviano (BOB)** como moneda de la compañía.
- **Plan de cuentas boliviano** ya cargado.
- **IVA 13%** configurado en los impuestos.
- **Idioma español** (es_BO) como idioma por defecto.
- Las aplicaciones de localización boliviana (facturación fiscal, reportes contables e
  inventario, nómina, etc.) ya instaladas.

Esto es así porque su instancia se clona de una base de datos maestra ya verificada por AEI
Software con estos datos — usted no necesita configurar país, moneda ni plan de cuentas
manualmente.

### 8. Primeros pasos recomendados

1. **Complete los datos reales de su empresa.** Vaya a **Ajustes → Usuarios y Compañías →
   Compañías**, abra su compañía y actualice:
   - Nombre real de la empresa
   - NIT
   - Dirección
   - Teléfono

   [CAPTURA: formulario de datos de la compañía en Ajustes → Compañías]

2. **Cree usuarios internos para su equipo.** Vaya a **Ajustes → Usuarios y Compañías →
   Usuarios → Nuevo**, complete el nombre y correo de cada persona, y asigne los permisos que
   correspondan a su rol (Ventas, Contabilidad, Inventario, etc.).

3. **Verifique que cambió la contraseña del usuario `admin`** (paso 6.3), si aún no lo hizo.

## Preguntas Frecuentes

**P: Pagué pero no recibí ningún correo.**
R: Revise su carpeta de spam/correo no deseado. Si después de 15-20 minutos no llegó ningún
correo, contacte a soporte indicando el correo con el que compró y la fecha/hora del pago.

**P: Recibí el primer correo ("En preparación") pero no el segundo con las credenciales.**
R: El proceso de preparación toma normalmente pocos minutos. Si pasó más de una hora sin recibir
el segundo correo, contacte a soporte — puede haber un problema con el aprovisionamiento.

**P: ¿Puedo entrar a mi sistema antes de recibir el correo de credenciales?**
R: No. El primer correo solo confirma la compra; necesita la contraseña que llega en el segundo
correo para poder ingresar.

**P: ¿Por qué mi empresa ya aparece configurada para Bolivia si yo no la configuré?**
R: Porque su instancia se crea a partir de una base de datos maestra ya preparada por AEI
Software con la localización boliviana lista (ver sección 7). No es necesario configurarla usted.

**P: Perdí la contraseña del correo de credenciales, ¿qué hago?**
R: Use la opción "¿Olvidó su contraseña?" en la pantalla de login de su instancia, o contacte a
soporte para que le ayuden a recuperar el acceso.
