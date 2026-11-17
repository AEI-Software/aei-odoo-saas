# Manual Técnico, Funcional y de Defensa — Sitio Web AEI (`aei_website`), Pasarela QR Banco Ganadero (`payment_qr_ganadero` v1.17.4) y Aprovisionamiento SaaS K8s

- **Fecha de actualización:** 13/11/2026
- **Entorno Local (K3s WSL2):** `http://localhost:8090` / `http://10.10.20.118:8069`
- **Entorno Staging (K3s Cruzoil):** `https://www.aeisoftware.com` (`https://aeisoftware.com`)
- **Módulos involucrados y orden de dependencias:**
  `aei_website` (`18.0.1.3.0`) → `odoo_k8s_saas_subscription` → `odoo_k8s_saas` + `payment_qr_ganadero` (`18.0.1.0.0`) + `saas_security_hardening` + `portal/` (FastAPI K8s Provisioner).

---

## ÍNDICE

1. [Resumen Ejecutivo para la Presentación](#1-resumen-ejecutivo-para-la-presentación)
2. [Arquitectura del Flujo End-to-End (Las 4 Fases)](#2-arquitectura-del-flujo-end-to-end-las-4-fases)
3. [Decisiones de Arquitectura y Seguridad (Argumentos de Defensa)](#3-decisiones-de-arquitectura-y-seguridad-argumentos-de-defensa)
4. [Cumplimiento Punto por Punto — Banco Ganadero QR Empresarial v1.17.4](#4-cumplimiento-punto-por-punto--banco-ganadero-qr-empresarial-v1174)
5. [Guion Paso a Paso para la Demostración en Vivo](#5-guion-paso-a-paso-para-la-demostración-en-vivo)
6. [Casos de Prueba QA — Frontend y Experiencia de Usuario (`aei_website`)](#6-casos-de-prueba-qa--frontend-y-experiencia-de-usuario-aei_website)
7. [Casos de Prueba QA — Webhooks y API Banco Ganadero (`curl` / Postman)](#7-casos-de-prueba-qa--webhooks-y-api-banco-ganadero-curl--postman)
8. [Comandos Operativos en K3s y Verificación Técnica en Vivo](#8-comandos-operativos-en-k3s-y-verificación-técnica-en-vivo)
9. [Preguntas Frecuentes del Comité / Defensa Técnica (Q&A)](#9-preguntas-frecuentes-del-comité--defensa-técnica-qa)
10. [Checklist Final de Aceptación](#10-checklist-final-de-aceptación)

---

## 1. Resumen Ejecutivo para la Presentación

El sistema implementa una plataforma **Odoo 18 SaaS Multi-Tenant sobre Kubernetes (K3s)** diseñada para el mercado boliviano, cubriendo el ciclo comercial y técnico completo sin intervención manual:

1. **Captación y Conversión (`aei_website`):** Sitio público 100 % personalizado bajo el sistema de diseño `aei-` (Portada `/`, Planes y Precios `/pricing`, Cuenta `/account` → `/web/signup` y `/web/login`, Contacto `/contactus` y animaciones bidireccionales de scroll).
2. **Onboarding Seguro Nativo (`auth_signup` + `saas_security_hardening`):** Creación de cuenta e inicio de sesión sobre el motor real de autenticación de Odoo 18, con visualización de contraseña (**botón "ojito"** `.aei-password-toggle`), protección CSRF obligatoria y cookies endurecidas (`Secure`, `HttpOnly`, `SameSite=Lax`).
3. **Cobro QR Empresarial Banco Ganadero (`payment_qr_ganadero` v1.17.4):** Implementación íntegra de la especificación técnica del Banco Ganadero (versión `1.17.4`), soportando generación de QR dinámico en Bolivianos (`BOB`) o Dólares (`USD`), verificación de estado en tiempo real, consulta de órdenes diarias y recepción de confirmación de pago vía Webhook autenticado con JWT (`HS256`).
4. **Facturación, Suscripción y Aprovisionamiento K8s (`odoo_k8s_saas_subscription` + `odoo_k8s_saas` + `portal/`):** Al confirmarse el pago QR, Odoo emite y concilia automáticamente la factura (`account.move` en estado `Pagado`), activa la suscripción (`sale.subscription` en estado `En progreso`) e instruye al microservicio FastAPI (`portal`) para crear en Kubernetes un namespace aislado (`odoo-<subdominio>`) con su propia base de datos, PVC, `ResourceQuota`, `NetworkPolicy` e Ingress TLS.

---

## 2. Arquitectura del Flujo End-to-End (Las 4 Fases)

```text
[1. Visitante en / o /pricing]
       │  Elige Plan (Starter / Pro / Advanced) + Ciclo (Mensual / Anual)
       │  Presiona "Probar 15 días gratis ↗" o "Elegir Starter / Pro / Advanced"
       ▼
[2. Wizard Unificado de 3 Pasos (/checkout?plan=...&cycle=...&mode=...)]
       ├── Paso 1 — 01 / TU CUENTA:
       │     Registra Nombre, Correo y Contraseña (con botón "ojito" para verificar clave)
       │     o inicia sesión sobre auth_signup real de Odoo 18 (res.users + res.partner)
       ├── Paso 2 — 02 / TU EMPRESA:
       │     Guarda Tipo de cuenta, Actividad, Nombre de empresa (define subdominio K8s),
       │     NIT/documento, Teléfono, Ciudad y País directamente en res.partner
       └── Paso 3 — 03 / ACTIVACIÓN (Prueba 15 días) o 03 / PAGO POR QR · BANCO GANADERO:
             Crea sale.order + payment.transaction real y muestra el QR Empresarial v1.17.4
             junto al resumen lateral "TU SELECCIÓN" en Bolivianos (Bs) y cupón AEI10
       ▼
[3. Cobro QR Empresarial Banco Ganadero v1.17.4 (payment_qr_ganadero)]
       │  • Saliente: POST .../service/v1/qrcode/access (XApi--Key) → JWT del Banco
       │  • Saliente: POST .../service/v1/qrcode/collections → qrId + qrImage (Base64)
       │  • Entrante: Webhook POST /payment/qr_ganadero/payments (o confirmación en Paso 3)
       ▼
[4. Automatización Post-Pago en Odoo 18 + Kubernetes (K3s)]
       ├── payment.transaction → state = 'done'
       ├── sale.order          → state = 'sale'
       ├── account.move        → state = 'posted' & payment_state = 'paid' (sale.automatic_invoice=True)
       ├── sale.subscription   → stage = 'in_progress'
       └── saas.instance       → action_provision() → FastAPI Portal (POST /instances)
                                   └── Crea en K8s: Namespace + Secret + ResourceQuota
                                       + NetworkPolicy (puertos 5000/5432 y 53) + PVC
                                       + Deployment Odoo 18 + Service + Ingress Traefik
```

---

## 3. Decisiones de Arquitectura y Seguridad (Argumentos de Defensa)

Si durante la presentación consultan **por qué se tomaron estas decisiones técnicas**, estos son los fundamentos de ingeniería:

### 3.1. ¿Por qué usar el motor nativo de cuenta de Odoo 18 (`/web/signup` y `/web/login`) vestido con diseño AEI en lugar del formulario simulado del prototipo?
- **El prototipo de referencia era una maqueta estática:** guardaba nombre y correo en `localStorage` del navegador sin contraseña real, sin sesión de servidor y sin crear registros en base de datos.
- **Seguridad y trazabilidad real en producción:** Al extender `web.login`, `auth_signup.signup`, `auth_signup.fields` y `auth_signup.reset_password` mediante herencia QWeb (`priority="30"` en `addons/aei_website/views/account/login_forms.xml`):
  1. Las contraseñas se almacenan con **hashing criptográfico `PBKDF2-SHA512`** nativo de Odoo (nunca en texto plano).
  2. Todos los formularios incluyen `csrf_token` validado por el servidor.
  3. El módulo `saas_security_hardening` inyecta `HttpOnly`, `Secure` y `SameSite=Lax` en las cookies de sesión.
  4. Al registrarse, Odoo crea automáticamente el `res.partner` (cliente contable) y el `res.users` (usuario de portal), requisito indispensable para emitir la factura, asociar la suscripción `SUBxxxxx` y vincular el tenant de Kubernetes al cliente.

### 3.2. ¿Por qué las vistas y hojas de estilo de `aei_website` no usan clases de Bootstrap ni `innerHTML`?
- **Aislamiento de estilos (Regla `aei-`):** Todas las clases propias en XML y CSS llevan el prefijo `aei-` (verificado automáticamente por `addons/aei_website/tests/test_static_rules.py`). Esto evita colisiones con actualizaciones de Bootstrap/Odoo y garantiza fidelidad pixel-perfect respecto al diseño de marca.
- **Prevención de XSS en el cliente:** El widget público `AeiLanding` (`addons/aei_website/static/src/js/landing.js`) manipula únicamente clases (`classList`), atributos (`setAttribute`, `input.type`, `hidden`) y `textContent`. Está prohibido por test estático el uso de `innerHTML`, `outerHTML`, `insertAdjacentHTML` y `document.write`.
- **Mantenibilidad (Quality Gate en CI):** El script `.github/scripts/structure_gate.py` audita que los archivos `.py` y `.xml` se mantengan por debajo del objetivo de **200 líneas** (máximo estricto 250 líneas), con modelos organizados en subcarpetas por dominio (`models/catalog/`, `models/pages/`, `models/provider/`, `models/transaction/`, `models/api_client/`).

### 3.3. ¿Por qué creamos el Wizard `/checkout` de 3 pasos en lugar de usar `/shop/cart` de Odoo?
- El carrito nativo de Odoo (`/shop/cart`) está diseñado para e-commerce de productos físicos (muestra cantidades `+/-`, costos de envío y barra genérica `YourLogo`).
- En `addons/aei_website/controllers/checkout.py` y `addons/aei_website/models/checkout/`, interceptamos `/shop/cart/update` y `/shop/cart` para redirigir siempre al wizard SaaS `/checkout` (**`TU NUEVO ESPACIO DE TRABAJO — Ya casi es tuyo.`**), que unifica en una sola vista de 2 columnas los 3 pasos (`1. Tu cuenta`, `2. Tu empresa`, `3. Activación / Pago QR`) junto a la tarjeta lateral `TU SELECCIÓN` en Bolivianos (`Bs`).
- Con `sale.automatic_invoice = "True"` (`addons/aei_website/models/pages/website_page.py`), la confirmación del Paso 3 dispara en una sola transacción atómica: confirmación del pedido, creación y conciliación de la factura, activación de la suscripción y aprovisionamiento del contenedor en K8s.

### 3.4. ¿Cómo se aísla cada cliente (Tenant) en Kubernetes?
- Cada cliente recibe su propio **Namespace** en K3s (`odoo-<subdominio>`, por ejemplo `odoo-constructora-ganadero-179-sub00001`).
- **Aislamiento de red (`NetworkPolicy` Zero-Trust):** En `portal/k8s_utils/manifests.py`, la política `tenant-isolation` bloquea todo el tráfico entre clientes. Solo permite:
  - **Ingress:** desde el controlador `traefik` (`kube-system`) y desde el `portal` (`aeisoftware`) hacia los puertos `8069` (HTTP) y `8072` (Longpolling/WebSocket).
  - **Egress:** hacia la base de datos PostgreSQL en los puertos TCP `5000` y `5432` (contemplando el DNAT del Service en K3s) y resolución DNS UDP/TCP en el puerto `53`.
- **Aislamiento de recursos (`ResourceQuota`):** Cada plan (`starter`, `pro`, `advanced`) aplica límites estrictos de CPU, memoria RAM y almacenamiento persistente (`PVC`).

---

## 4. Cumplimiento Punto por Punto — Banco Ganadero QR Empresarial v1.17.4

A continuación se detalla cómo el módulo `addons/payment_qr_ganadero` implementa cada sección de la **Especificación Técnica v1.17.4 (09/06/2026)** entregada por el Banco Ganadero:

| Punto del Manual v1.17.4 | Servicio / Endpoint | Implementación en `addons/payment_qr_ganadero` | Detalles Técnicos Validados |
| :--- | :--- | :--- | :--- |
| **2. Autenticación de Usuario** *(Saliente: Odoo → Banco)* | `POST /ws-servicio-codigo-qr-empresas/service/v1/qrcode/access` | `models/api_client/ganadero_client.py` (`get_access_token`) | Envía cabecera `XApi--Key` (con doble guion, configurable en el proveedor) y cuerpo JSON `{"userName", "password"}`. Valida `result == "COD000"` y almacena el `token` en caché por 50 minutos (`models/provider/payment_provider_token.py`). |
| **3. Generación de Orden de Cobro** *(Saliente: Odoo → Banco)* | `POST /ws-servicio-codigo-qr-empresas/service/v1/qrcode/collections` | `models/api_client/ganadero_client.py` (`create_qr_order`) y `models/transaction/payment_transaction_qr.py` | Envía `Authorization: Bearer <token>` y cuerpo con `accountReference` (máx. 20 chars), `amount` (formateado `###0.00`, validando tope máximo de **69.000,00 Bs**), `currency` (`BOB` o `USD`), `gloss` (máx. 60 chars), `expirationDate` en formato exacto **`ddmmyyyy`** (`%d%m%Y`), `singleUse: 1`, `userName` y `apiKey`. Guarda `qrId` y `qrImage` (Base64). |
| **4. Lista de Órdenes Diarias** *(Saliente: Odoo → Banco)* | `POST /ws-servicio-codigo-qr-empresas/service/v1/qrcode/transactions` | `models/api_client/ganadero_client.py` (`list_daily_transactions`) | Permite consultar por rango `startDate` y `endDate` (`ddmmyyyy`) el arreglo `orders` para conciliación bancaria. |
| **5. Estado de la Orden** *(Saliente: Odoo → Banco)* | `POST /ws-servicio-codigo-qr-empresas/service/v1/qrcode/status` | `models/api_client/ganadero_client.py` (`check_qr_status`) y `controllers/payment_Controller.py` | Consulta por `qrId`, `userName` y `apiKey`. Interpreta `orderState`: `1` (Registrado → `pending`), `2` (Pagado → `_set_done()`), `3` (Anulado → `_set_canceled()`). |
| **6. Autenticación en Empresa** *(Entrante: Banco → Odoo)* | `POST /payment/qr_ganadero/login` | `controllers/webhook_controller.py` (`bank_login`) y `models/provider/payment_provider_jwt.py` | Valida presencia de `userName` y `password` (si faltan → `COD001`). Valida formato estrictamente alfanumérico y coincidencia en tiempo constante (`hmac.compare_digest`) contra el proveedor (si falla → `COD002`). Si es válido, responde `COD000` con un **JWT firmado con HS256** (`exp` = 1 hora). |
| **7. Registro de Pago en Empresa** *(Entrante: Banco → Odoo)* | `POST /payment/qr_ganadero/payments` | `controllers/webhook_controller.py` (`bank_receive_payment`) y `models/transaction/payment_transaction_webhook.py` | Verifica cabecera `Authorization: Bearer <jwt>` (si falta o expiró → `HTTP 401` con `COD002`). Valida `qrId`, `transactionId` y `payDate` (si faltan → `COD001`). Busca la transacción por `ganadero_qr_id`, garantiza **idempotencia** (si ya estaba `done`, devuelve `COD000` sin duplicar pagos) y confirma la orden. |
| **8. Notas Adicionales** | Reglas de formato y seguridad | `models/provider/payment_provider.py` (`_check_incoming_credentials_alphanumeric`) | `@api.constrains` obliga a que `ganadero_incoming_user` y `ganadero_incoming_password` contengan únicamente caracteres alfanuméricos (`^[A-Za-z0-9]+$`), sin espacios ni caracteres especiales (`@`, `.`, `/`, `-`, `_`, `#`). |

---

## 5. Guion Paso a Paso para la Demostración en Vivo

Sigue este orden exacto durante tu presentación de la tarde para mostrar el ciclo completo en menos de 5 minutos:

### Paso 1 — Portada (`/`) y Vista Dedicada de Planes (`/pricing`)
1. Abrir `http://localhost:8090/` (o `https://www.aeisoftware.com/`).
2. Mostrar la estética limpia de AEI Software (sin barras nativas de Odoo), las animaciones bidireccionales al hacer scroll hacia abajo y hacia arriba, y en la sección de planes mostrar el botón **`Comparar todos los módulos ↗`**.
3. Hacer clic en **Planes y precios** (`/pricing`):
   - Destacar cómo en `/pricing` se muestran las 3 tarjetas (**Starter**, **Pro**, **Advanced**), el conmutador **Mensual / Anual (con 20 % de descuento)**, los **4 checks inferiores** (*✓ Instancia privada*, *✓ Facturación SIAT**, *✓ Roles y contador*, *✓ Respaldos y exportación*), las 2 líneas de nota legal y, justo debajo, la **tabla comparativa interactiva de módulos (`#modulos`)** con filtros por área (`Todos`, `Comercial`, `Operaciones`, `Finanzas`, `RRHH`).

### Paso 2 — Pantalla `/checkout` de 3 Pasos (`Ya casi es tuyo.`) y Botón "Ojito" de Contraseña
1. En `/pricing` (o en `/`), hacer clic en **`Probar 15 días gratis ↗`** o en **`Elegir Starter / Pro / Advanced`**.
2. Mostrar cómo redirige inmediatamente a `/checkout?plan=starter&cycle=monthly&mode=trial` (nunca al carrito genérico de Odoo) con el diseño dividido de AEI Software:
   - **Encabezado:** `TU NUEVO ESPACIO DE TRABAJO` — **`Ya casi es tuyo.`** y la barra de progreso de 3 pasos (**`1. Tu cuenta`** → **`2. Tu empresa`** → **`3. Activación / Pago QR`**).
   - **Columna Derecha (`TU SELECCIÓN`):**
     - Muestra el plan seleccionado (`Plan Starter / Pro / Advanced`), enlace `Cambiar`, conmutador en vivo **`Mensual / Anual −20%`**, conmutador **`Prueba gratuita / Comprar ahora`**, desglose en **Bolivianos (`Bs`)** y campo de cupón (`AEI10` para 10 % adicional).
   - **Columna Izquierda (`01 / TU CUENTA — Comienza por ti.`):**
     - Si aún no se inició sesión, muestra las pestañas **Crear cuenta** e **Iniciar sesión** con los campos en orden (`Tu nombre`, `Correo electrónico`, `Contraseña`, `Confirmar contraseña`) y el **botón del ojito** (`.fa-eye` / `.fa-eye-slash`) para verificar la contraseña antes de enviarla.
     - Si ya había sesión activa, muestra la tarjeta con el nombre/correo del usuario y avanza directo al Paso 2.

### Paso 3 — Paso 2 del Checkout (`02 / TU EMPRESA — Conozcamos tu negocio.`)
1. Tras crear la cuenta o iniciar sesión, el wizard avanza automáticamente a **`02 / TU EMPRESA`**.
2. Completar los datos empresariales:
   - `Tipo de cuenta`: `Empresa` o `Persona / profesional independiente`
   - `Actividad`: `Comercial`, `Industrial` o `Servicios`
   - `Nombre de la empresa o nombre completo` (por ejemplo: `Constructora Andina SRL`) — este nombre también define el subdominio del contenedor en Kubernetes.
   - `NIT / documento`, `Teléfono`, `Ciudad` (`Santa Cruz de la Sierra`) y `País` (`Bolivia`).
3. Mostrar cómo estos datos se guardan directamente en el `res.partner` contable real de Odoo 18 y presionar **`Continuar al pago QR ↗`** (o **`Revisar mi prueba gratuita ↗`**).

### Paso 4 — Paso 3 del Checkout (`03 / PAGO POR QR · BANCO GANADERO` o `03 / TU PRUEBA GRATUITA`)
1. Si se eligió **Comprar ahora (`mode=paid`)**:
   - Muestra dentro del mismo panel **`03 / PAGO POR QR · BANCO GANADERO — Escanea. Confirma. Comienza.`**
   - Crea en el backend de Odoo la orden `sale.order` real y la transacción `payment.transaction` con `payment_qr_ganadero` v1.17.4, mostrando el código QR generado, el importe en `Bs`, la referencia de orden y las 3 instrucciones paso a paso.
   - Marcar la casilla de confirmación y hacer clic en **`Simular pago desde mi banco ↗`**.
2. Si se eligió **Prueba gratuita (`mode=trial`)**:
   - Muestra **`03 / TU PRUEBA GRATUITA — 15 días para dar el primer paso.`** con el círculo `15 días gratis ✦`, las fechas de inicio/fin y el botón **`Activar mis 15 días gratis ↗`**.

### Paso 5 — Pantalla de Éxito (`PAGO CONFIRMADO`) y Verificación en Odoo + Kubernetes
1. Al confirmar, la vista muestra la tarjeta de éxito `.aei-success` (**`Bienvenido a una gestión más simple.`** / **`Tu próximo capítulo empieza hoy.`**) con el resumen del Plan, Estado (`Activa` / `En prueba`), fecha de vigencia y el recuadro **`Tu ambiente AEI ya está listo`** con el subdominio asignado (`<empresa>.aeisoftware.com`) y el botón **`Ir a mi portal ↗`** (`/my`).
2. Mostrar en el Backend de Odoo (o en terminal) los 4 objetos creados automáticamente:
   - **Pedido de Venta (`sale.order`):** Confirmado (`sale`).
   - **Factura (`account.move`):** Publicada y en estado **`Pagado` (`paid`)**.
   - **Suscripción (`sale.subscription`):** Activa en etapa **`En progreso` (`in_progress`)**.
   - **Instancia SaaS (`saas.instance`):** Aprovisionada en Kubernetes con su propio namespace `odoo-<subdominio>` y pod corriendo.

---

## 6. Casos de Prueba QA — Frontend y Experiencia de Usuario (`aei_website`)

| ID | Caso de Prueba | Ruta | Resultado Esperado |
| :--- | :--- | :--- | :--- |
| **QA-01** | Portada principal sin cromo nativo de Odoo | `/` | Renderiza header/footer `.aei-site-header` y `.aei-footer`; oculta `#top` de Odoo; muestra botón `Comparar todos los módulos ↗` hacia `/pricing#modulos`. |
| **QA-02** | Página dedicada de Planes y Precios | `/pricing` | Muestra encabezado `PLANES Y PRECIOS`, conmutador Mensual/Anual, 3 tarjetas de planes, 4 checks de beneficios, 2 notas al pie y tabla comparativa `#modulos` (sin el botón redundante `Comparar todos los módulos ↗`). |
| **QA-03** | Redirección de ruta corta `/account` | `/account` | `GET /account` redirige (`HTTP 302`) a `/web/signup`; `GET /account?mode=login` redirige a `/web/login`. |
| **QA-04** | Botón "ojito" mostrar/ocultar contraseña en Login | `/web/login` | El campo `#password` incluye `button[data-aei-password-toggle="password"]` con `.fa-eye`. Al hacer clic cambia `type="password"` a `type="text"`, actualiza el ícono a `.fa-eye-slash` y cambia `aria-label` a `"Ocultar contraseña"`. |
| **QA-05** | Botón "ojito" y orden de campos en Registro | `/web/signup` | Muestra los campos en orden `name` (*Tu nombre*), `login` (*Correo electrónico*), `password` (*Contraseña*) y `confirm_password` (*Confirmar contraseña*), con **2 botones de ojito independientes** para verificar ambas claves. |
| **QA-06** | Formulario de Contacto con validación CSRF | `/contactus` | Envía `POST /contactus/submit` con `csrf_token`, crea registro en `mail.mail` y redirige a `/contactus-thank-you`. Rechaza con `400/403` si se omite el token CSRF. |
| **QA-07** | Animaciones bidireccionales de Scroll | `/`, `/pricing`, `/web/login`, `/contactus`, `/checkout` | Al entrar al viewport agrega `.aei-is-visible`; al salir agrega `.aei-is-exiting` (`.aei-exit-up` / `.aei-exit-down`) y vuelve a animar al reingresar. Respeta `prefers-reduced-motion: reduce`. |
| **QA-08** | Wizard `/checkout` de 3 pasos sin barra nativa de Odoo | `/checkout?plan=pro&cycle=monthly&mode=trial` | Oculta `<header id="top">` (`no_header=True`); muestra los 3 pasos (`1. Tu cuenta` con ojito de contraseña, `2. Tu empresa`, `3. Activación / Pago QR`), resumen `TU SELECCIÓN` en `Bs`, cupón `AEI10` y generación real de QR Banco Ganadero v1.17.4. |

---

## 7. Casos de Prueba QA — Webhooks y API Banco Ganadero (`curl` / Postman)

Estas pruebas permiten demostrar ante el equipo técnico o del banco que los endpoints de los **Puntos 6, 7 y 8** cumplen estrictamente la especificación v1.17.4.

> En los ejemplos siguientes puedes usar `http://localhost:8090` (entorno local) o `https://www.aeisoftware.com` (entorno staging).

### 7.1. Caso Negativo 1 — Parámetros insuficientes (`COD001`)
```bash
curl -i -X POST http://localhost:8090/payment/qr_ganadero/login \
  -H "Content-Type: application/json" \
  -d '{}'
```
- **Respuesta esperada (`HTTP 200`):**
  ```json
  {
    "result": "COD001",
    "message": "Parámetros de entrada insuficientes",
    "token": ""
  }
  ```

### 7.2. Caso Negativo 2 — Caracteres especiales no permitidos por Punto 8 (`COD002`)
```bash
curl -i -X POST http://localhost:8090/payment/qr_ganadero/login \
  -H "Content-Type: application/json" \
  -d '{"userName": "usuario_invalido!", "password": "123"}'
```
- **Respuesta esperada (`HTTP 200`):**
  ```json
  {
    "result": "COD002",
    "message": "Parámetros fuera del formato establecido",
    "token": ""
  }
  ```

### 7.3. Caso Positivo — Autenticación del Banco en Empresa (Punto 6 → `COD000` + JWT)
```bash
curl -i -X POST http://localhost:8090/payment/qr_ganadero/login \
  -H "Content-Type: application/json" \
  -d '{"userName": "<USUARIO_ENTRANTE_ALFANUMERICO>", "password": "<PASSWORD_ENTRANTE_ALFANUMERICO>"}'
```
- **Respuesta esperada (`HTTP 200`):**
  ```json
  {
    "result": "COD000",
    "message": "Resultado satisfactorio",
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
  ```

### 7.4. Caso Positivo — Notificación de Pago de Orden QR e Idempotencia (Punto 7 → `COD000`)
```bash
curl -i -X POST http://localhost:8090/payment/qr_ganadero/payments \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN_JWT_OBTENIDO>" \
  -d '{
    "qrId": "<ID_QR_DE_LA_ORDEN>",
    "transactionId": "000098765432",
    "payDate": "13112026"
  }'
```
- **Respuesta esperada (`HTTP 200`):**
  ```json
  {
    "result": "COD000",
    "message": "Resultado satisfactorio"
  }
  ```
- **Prueba de Idempotencia:** Si se repite exactamente la misma petición `curl` con el mismo `qrId`, devuelve nuevamente `{"result": "COD000", "message": "Resultado satisfactorio"}` sin duplicar pagos ni facturas en Odoo.
- **Prueba de Seguridad JWT:** Si se envía sin cabecera `Authorization: Bearer <jwt>` o con un token alterado, devuelve `HTTP 401` con `{"result": "COD002", "message": "Parámetros fuera del formato establecido"}`.

---

## 8. Comandos Operativos en K3s y Verificación Técnica en Vivo

Si durante la defensa te piden mostrar la consola, correr pruebas o verificar los contenedores en Kubernetes, tienes estos comandos listos:

### 8.1. Verificar el Quality Gate de estructura y límites de líneas
```bash
python3 .github/scripts/structure_gate.py
```
- **Resultado:** `Structure gate: 0 new violation(s)`.

### 8.2. Ver todos los pods corriendo en K3s (Odoo Admin, Portal, PostgreSQL y Tenants de clientes)
```bash
kubectl get pods -A
```

### 8.3. Verificar un cliente aprovisionado automáticamente tras pagar con QR
```bash
kubectl get all,networkpolicy,resourcequota,pvc -n odoo-constructora-ganadero-179-sub00001
```

### 8.4. Ejecutar las pruebas automatizadas de `aei_website` y `payment_qr_ganadero` en K3s
```bash
# Tests de pasarela Banco Ganadero v1.17.4
kubectl exec -n odoo-admin deploy/odoo-admin -- \
  odoo -d admin --test-enable --test-tags /payment_qr_ganadero \
  --http-port=8099 --stop-after-init --workers=0 --max-cron-threads=0

# Tests de sitio web AEI (Landing, /pricing, Cuenta, Ojito de contraseña, Contacto y Reglas Estáticas)
kubectl exec -n odoo-admin deploy/odoo-admin -- \
  odoo -d admin --test-enable --test-tags /aei_website \
  --http-port=8099 --stop-after-init --workers=0 --max-cron-threads=0
```

### 8.5. Comandos para aplicar cambios futuros en K3s local
```bash
# 1. Reiniciar el deployment para que el initContainer copy-addon copie los cambios del repositorio
kubectl rollout restart deployment/odoo-admin -n odoo-admin
kubectl rollout status deployment/odoo-admin -n odoo-admin --timeout=120s

# 2. Actualizar el módulo modificado en la base de datos de Odoo
kubectl exec -n odoo-admin deploy/odoo-admin -- \
  odoo -d admin -u aei_website --stop-after-init --http-port=8098 --workers=0 --max-cron-threads=0

# 3. Exponer el puerto 8090 hacia tu navegador local
kubectl port-forward --address 0.0.0.0 -n odoo-admin svc/odoo-admin-svc 8090:8069
```

---

## 9. Preguntas Frecuentes del Comité / Defensa Técnica (Q&A)

1. **¿Qué pasa si el cliente cierra la ventana del QR justo cuando paga desde su celular?**
   - No se pierde el pago. Existen **dos mecanismos independientes**: (a) el navegador hace *polling* cada 3 segundos mientras la pestaña está abierta, y (b) el Banco Ganadero invoca de servidor a servidor nuestro webhook `POST /payment/qr_ganadero/payments` (Punto 7). Aunque el cliente haya cerrado el navegador, el webhook recibe la confirmación del banco, marca la factura como pagada, activa la suscripción y aprovisiona la instancia de Kubernetes en segundo plano.
2. **¿Qué ocurre si el Banco Ganadero reintenta el webhook dos o tres veces por un corte de red?**
   - El método `_ganadero_confirm_transaction` es **idempotente**. Antes de procesar, verifica si `tx.state == 'done'`. Si ya fue confirmada previamente, retorna inmediatamente `COD000` al banco sin crear asientos contables ni pods duplicados.
3. **¿Cómo se protegen las credenciales del Banco Ganadero y el webhook entrante?**
   - Las credenciales salientes (`XApi--Key`, `userName`, `password`) se almacenan en el proveedor de pago con permisos restringidos a `base.group_system`.
   - El webhook entrante exige autenticación previa en `/payment/qr_ganadero/login` comparando credenciales con `hmac.compare_digest` (resistente a ataques de temporización / *timing attacks*) y emite un **JWT firmado con `HS256`** con tiempo de vida de 1 hora.
4. **¿Por qué se limita el monto de cada QR a 69.000,00 Bs?**
   - Porque la Especificación Técnica v1.17.4 del Banco Ganadero (Punto 3, campo `amount`) establece textualmente que el monto máximo permitido por orden QR es de **69.000,00 Bs**. Nuestro módulo valida ese tope antes de invocar al banco para dar un mensaje claro si una orden lo supera.
5. **¿Un cliente cuyo contenedor fue creado en Kubernetes puede ver la red o los contenedores de otro cliente?**
   - No. Cada cliente vive en su propio namespace `odoo-<subdominio>` con una `NetworkPolicy` (`tenant-isolation`) que bloquea por defecto todo tráfico de entrada y salida, habilitando únicamente la entrada desde el balanceador `Traefik` y la salida hacia el puerto de PostgreSQL y DNS interno.

---

## 10. Checklist Final de Aceptación

- [x] **Portada (`/`) y Planes (`/pricing`):** Fidelidad visual AEI Software, 4 checks de beneficios, 2 notas legales y tabla comparativa `#modulos` con filtros interactivos.
- [x] **Cuenta Nativa Odoo 18 (`/account` → `/web/signup`, `/web/login`, `/web/reset_password`):** Orden de campos (`Tu nombre`, `Correo electrónico`, `Contraseña`, `Confirmar contraseña`), protección CSRF y **botón "ojito"** (`.fa-eye` / `.fa-eye-slash`) funcional.
- [x] **Contacto (`/contactus`):** Validación de datos, protección CSRF, creación de `mail.mail` y redirección a `/contactus-thank-you`.
- [x] **Animaciones Bidireccionales de Scroll:** Entrada (`.aei-is-visible`) y salida (`.aei-is-exiting`) fluidas al subir y bajar en todas las páginas públicas.
- [x] **Pasarela QR Banco Ganadero v1.17.4 (`payment_qr_ganadero`):** Cumplimiento de los Puntos 2, 3, 4, 5, 6, 7 y 8, pantalla QR con estética AEI (`03 / PAGO POR QR · BANCO GANADERO`) y simulación en modo prueba.
- [x] **Flujo End-to-End SaaS + Kubernetes:** Confirmación de pago QR → Factura `Pagada` → Suscripción `En progreso` → Instancia Odoo 18 aprovisionada y corriendo en K3s (`odoo-constructora-ganadero-179-sub00001`).
- [x] **Quality Gate (`structure_gate.py`):** `0 new violation(s)`.
