# Auditoría Completa del Proyecto y Backlog de Historias de Usuario (`HU-01` a `HU-15`)

- **Proyecto:** AEI Software — Plataforma Odoo 18 SaaS Multi-Tenant + Pasarela QR Banco Ganadero v1.17.4
- **Fecha de actualización:** 16/11/2026
- **Leyenda de estado para tu Backlog:**
  - `[x]` = **Completado, implementado y verificado en código**
  - `[ ]` = **Pendiente (por respuesta del Banco Ganadero o cierre final de Fase 2)**

---

## PARTE 1 — REVISIÓN TÉCNICA SEPARADA POR CAPAS Y MÓDULOS

### 1.1. Desarrollo Frontend (`addons/aei_website` — Separación de Vistas, Estilos, JS y Lógica)

El módulo `addons/aei_website` (`v18.0.1.3.0`) está estructurado separando estrictamente la presentación (QWeb/CSS/JS) de la lógica de negocio (modelos Python en subcarpetas):

| Capa / Submódulo | Archivos Principales | Qué hace exactamente | Estado |
| :--- | :--- | :--- | :---: |
| **Catálogo y Planes (`models/plans/` y `models/catalog/`)** | [product_template.py](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/models/plans/product_template.py), [plan_pricing.py](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/models/plans/plan_pricing.py), [website_catalog.py](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/models/catalog/website_catalog.py), [modules.json](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/data/catalog/modules.json) | Lee precios en `Bs`, usuarios, GB y horas de soporte desde `sale.subscription.template`; calcula en servidor el descuento anual (-20 %) y el ahorro en Bolivianos; sirve la matriz de módulos y reportes por plan. | `[x]` |
| **Portada Principal (`/`) (`views/home/`)** | [homepage.xml](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/views/homepage.xml), [hero.xml](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/views/home/hero.xml), [clients.xml](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/views/home/clients.xml), [processes.xml](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/views/home/processes.xml), [profiles.xml](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/views/home/profiles.xml), [plans.xml](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/views/home/plans.xml), [faq.xml](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/views/home/faq.xml), [cta.xml](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/views/home/cta.xml) | Reemplaza el cromo nativo de Odoo (`no_header`/`no_footer`), muestra el Hero interactivo, clientes, procesos, selector de perfiles empresariales, tarjetas de planes, modales de detalle y 8 preguntas frecuentes. | `[x]` |
| **Página Dedicada de Planes y Precios (`/pricing`) (`views/pricing/`)** | [pricing_page.xml](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/views/pricing/pricing_page.xml), [pricing_comparison.xml](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/views/pricing/pricing_comparison.xml) | Vista dedicada `/pricing` con las 3 tarjetas de planes, los 4 checks inferiores, notas legales, tabla comparativa interactiva de módulos (`#modulos`) con filtros por categoría (`Todos`, `Comercial`, `Operaciones`, `Finanzas`, `RRHH`) y sección de reportes (`#reportes`). | `[x]` |
| **Autenticación y Botón "Ojito" (`/account`, `/web/login`, `/web/signup`, `/web/reset_password`) (`views/account/`)** | [login_layout.xml](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/views/account/login_layout.xml), [login_forms.xml](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/views/account/login_forms.xml), [public_pages.py](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/controllers/public_pages.py) | Viste el motor real `auth_signup` de Odoo 18 con estética AEI, ordena los campos (`Tu nombre`, `Correo electrónico`, `Contraseña`, `Confirmar contraseña`) e incorpora el botón de visualización de contraseña ("ojito" `.fa-eye` / `.fa-eye-slash`). | `[x]` |
| **Contacto Institucional (`/contactus` y `/contactus-thank-you`) (`models/contact/`, `views/contact/`)** | [website_contact.py](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/models/contact/website_contact.py), [contactus.xml](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/views/contact/contactus.xml) | Valida y sanea los campos del formulario de contacto con protección CSRF, genera el correo saliente en `mail.mail` y redirige a la pantalla de agradecimiento. | `[x]` |
| **Wizard de Contratación en 3 Pasos (`/checkout`) (`controllers/checkout.py`, `models/checkout/`, `views/checkout/`)** | [checkout.py](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/controllers/checkout.py), [website_checkout.py](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/models/checkout/website_checkout.py), [website_checkout_order.py](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/models/checkout/website_checkout_order.py), [checkout_page.xml](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/views/checkout/checkout_page.xml), [checkout_steps.xml](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/views/checkout/checkout_steps.xml), [checkout_payment.xml](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/views/checkout/checkout_payment.xml) | Intercepta `/shop/cart` para llevar al cliente al flujo guiado de 3 pasos (**1. Tu cuenta**, **2. Tu empresa**, **3. Activación de prueba 15 días o Pago QR Banco Ganadero**) con resumen lateral en `Bs`, cupón `AEI10` y pantalla final de éxito con credenciales de acceso. | `[x]` |
| **Interactividad Cliente y Animaciones Bidireccionales (`static/src/js/landing.js`, `static/src/css/`)** | [landing.js](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/static/src/js/landing.js), `foundation/` y `refinements/` | Controla en cliente: conmutador Mensual/Anual, pestañas de Hero/Perfiles, filtros de tabla comparativa, modales `<dialog>`, botón "ojito" de contraseña y animaciones de entrada/salida al hacer scroll hacia abajo y hacia arriba (sin usar Bootstrap ni `innerHTML`). | `[x]` |
| **Estética AEI en el Portal de Clientes (`/my`)** | `views/portal/` *(por crear)* | Actualmente `/my` funciona con el diseño estándar de Odoo 18 (`YourLogo`). Falta aplicar el encabezado/pie AEI en `/my`. | `[ ]` |

---

### 1.2. Integración con Banco Ganadero QR Empresarial v1.17.4 (`addons/payment_qr_ganadero`)

| Punto de la Especificación v1.17.4 | Archivos en `addons/payment_qr_ganadero` | Lo que ya está programado | Qué falta | Estado |
| :--- | :--- | :--- | :--- | :---: |
| **Punto 2 — Autenticación Saliente (`/qrcode/access`)** | [token_auth.py](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/payment_qr_ganadero/models/provider/token_auth.py), [provider_fields.py](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/payment_qr_ganadero/models/provider/provider_fields.py) | Envía cabecera `XApi--Key` y cuerpo JSON `{"userName", "password"}`, valida `COD000` y guarda el token JWT en caché por 50 minutos. | Cargar credenciales reales del banco cuando respondan la solicitud del 04/11/2026. | `[x]` |
| **Punto 3 — Generación de Orden QR (`/qrcode/collections`)** | [qr_requests.py](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/payment_qr_ganadero/models/provider/qr_requests.py), [payment_transaction.py](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/payment_qr_ganadero/models/transaction/payment_transaction.py) | Valida moneda (`BOB`/`USD`) y tope de **69.000,00 Bs**, formatea `expirationDate` como `ddmmyyyy`, envía `accountReference`, `amount`, `gloss`, `singleUse` y almacena `qrId` + `qrImage` (o genera SVG demo si `state == 'test'`). | Certificar con el sandbox/producción del banco cuando entreguen `accountReference` y `apiKey`. | `[x]` |
| **Punto 4 — Lista de Órdenes Diarias (`/qrcode/transactions`)** | [qr_requests.py](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/payment_qr_ganadero/models/provider/qr_requests.py) | Consulta por `startDate` y `endDate` (`ddmmyyyy`) el arreglo `orders` para conciliación. | Probar contra servidor real del banco. | `[x]` |
| **Punto 5 — Consulta de Estado (`/qrcode/status`) y Cron** | [qr_requests.py](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/payment_qr_ganadero/models/provider/qr_requests.py), [transaction_cron.py](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/payment_qr_ganadero/models/transaction/transaction_cron.py), [status_polling.py](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/payment_qr_ganadero/controllers/status_polling.py) | Consulta `orderState` (`1` Registrado, `2` Pagado, `3` Anulado) tanto por endpoint `/payment/qr_ganadero/status` como por tarea programada (`ir.cron` cada minuto). | Conectado: el Paso 3 de `/checkout` consulta el estado cada 3 s y abre `step=done` al confirmarse el pago (20/11/2026). | `[x]` |
| **Punto 6 — Login Entrante del Banco (`/payment/qr_ganadero/login`)** | [bank_webhook.py](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/payment_qr_ganadero/controllers/bank_webhook.py), [inbound_jwt.py](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/payment_qr_ganadero/models/provider/inbound_jwt.py) | Valida `userName` y `password` en tiempo constante (`hmac.compare_digest`), exige formato alfanumérico y emite un JWT firmado con `HS256` (validez 1 h). Devuelve `COD000`, `COD001` o `COD002`. | Entregar al banco el usuario/clave alfanuméricos una vez que confirmen las rutas de la Solicitud Técnica. | `[x]` |
| **Punto 7 — Webhook Entrante de Pago (`/payment/qr_ganadero/payments`)** | [bank_webhook.py](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/payment_qr_ganadero/controllers/bank_webhook.py), [payment_transaction.py](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/payment_qr_ganadero/models/transaction/payment_transaction.py) | Verifica `Authorization: Bearer <jwt>`, valida `qrId`, `transactionId` y `payDate`, garantiza idempotencia (no duplica pagos si el banco reintenta) y dispara facturación + suscripción + K8s. | Recibir notificación real desde el servidor del Banco Ganadero. | `[x]` |
| **Punto 8 — Reglas de Formato y Seguridad** | [provider_fields.py](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/payment_qr_ganadero/models/provider/provider_fields.py), [website_checkout_order.py](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/addons/aei_website/models/checkout/website_checkout_order.py) | Restricción `@api.constrains` alfanumérica sobre credenciales entrantes y bloqueo de simulación manual cuando el proveedor está en `enabled`. | Confirmar con el banco la Consulta 1 (prefijo `/payment/qr_ganadero/`). | `[x]` |

---

### 1.3. Automatización Post-Pago y Aprovisionamiento Kubernetes (`odoo_k8s_saas_subscription`, `odoo_k8s_saas`, `portal/`)

| Componente | Archivos | Qué hace | Estado |
| :--- | :--- | :--- | :---: |
| **Facturación y Suscripción Automática** | `odoo_k8s_saas_subscription/models/sale_subscription.py`, `odoo_k8s_saas/models/saas_sale.py` | Con `sale.automatic_invoice=True`, al confirmarse la transacción QR emite la factura en estado `Pagado`, pasa la suscripción a `En progreso` y crea el registro `saas.instance`. | `[x]` |
| **Orquestador FastAPI y Manifiestos K8s** | [instances.py](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/portal/routers/instances.py), [manifests.py](file:///home/ronald/proyectos/odoo-lab/aeiSoftware/aei-odoo-saas/portal/k8s_utils/manifests.py) | Crea rol y base de datos en PostgreSQL y despliega en K3s el namespace `odoo-<tenant>`, `Secret` (con `APP_ADMIN_PASSWORD` de 16 caracteres), `ResourceQuota`, `NetworkPolicy` (puertos `5000`/`5432` y `53`), `PVC`, `Deployment` e `Ingress` (`.aeisoftware.com` y `.localhost`). | `[x]` |
| **Servidor SMTP en Producción** | Configuraciones de Odoo (`ir.mail_server`) | Las plantillas `mail_template_instance_provisioned` y `email_template_saas_credentials` están listas y se disparan automáticamente, pero falta configurar las credenciales SMTP reales en el servidor para que el correo llegue a la bandeja externa del cliente. | `[ ]` |

---

## PARTE 2 — BACKLOG COMPLETO DE HISTORIAS DE USUARIO (`HU-01` A `HU-15`)

| Código | Historia de Usuario | Horas Estimadas | Estado |
| :--- | :--- | :---: | :---: |
| **HU-01** | Presentación comercial e identidad visual en la página de inicio (`/`) | **16 h** | `[x]` |
| **HU-02** | Comparación transparente de planes de suscripción y capacidades incluidas | **8 h** | `[x]` |
| **HU-03** | Selector de pago Mensual vs. Anual con cálculo automático de descuento (-20%) | **6 h** | `[x]` |
| **HU-04** | Consulta detallada de módulos, procesos operativos y matriz comparativa (`/pricing`) | **14 h** | `[x]` |
| **HU-05** | Selección de plan y asistente de contratación en 3 pasos (`/checkout`) | **20 h** | `[x]` |
| **HU-06** | Administración centralizada del catálogo de planes y precios desde el panel interno | **8 h** | `[x]` |
| **HU-07** | Registro, inicio de sesión y recuperación de clave con botón de visualización de contraseña ("Ojito") | **10 h** | `[x]` |
| **HU-08** | Formulario de contacto comercial y solicitud de asesoría (`/contactus`) | **6 h** | `[x]` |
| **HU-09** | Generación de orden de cobro QR Empresarial con Banco Ganadero (Puntos 2 y 3 v1.17.4) | **16 h** | `[x]` |
| **HU-10** | Recepción de confirmación de pago del Banco Ganadero vía Webhook JWT (Puntos 6, 7 y 8 v1.17.4) | **16 h** | `[x]` |
| **HU-11** | Verificación automática de estado de cobro y conciliación diaria (Puntos 4 y 5 v1.17.4) | **10 h** | `[x]` |
| **HU-12** | Facturación automática, activación de suscripción y aprovisionamiento de instancia Odoo 18 en Kubernetes | **24 h** | `[x]` |
| **HU-13** | Pantalla de confirmación con resumen de acceso y entrega de credenciales al cliente | **8 h** | `[x]` |
| **HU-14** | Diseño de marca AEI Software en el Portal de Clientes (`/my`) | **12 h** | `[ ]` |
| **HU-15** | Ciclo de vida de suscripciones (renovación, suspensión por mora y reactivación en K8s) | **12 h** | `[ ]` |
| **TOTAL** | **15 Historias de Usuario (162 h completadas / 24 h pendientes)** | **186 h** | — |

---

### HU-01: Presentación comercial e identidad visual en la página de inicio (`/`) — (8 horas)

**Como** Cliente que ingresa por primera vez al sitio web de AEI Software,  
**Quiero** ver una página de inicio clara, moderna y confiable que me muestre la propuesta de valor del sistema, las empresas bolivianas que ya confían en la plataforma, un recorrido por rubros de negocio, animaciones fluidas al desplazarme y las respuestas a las preguntas más frecuentes,  
**Para** entender rápidamente cómo el sistema se adapta a mi empresa y tomar confianza antes de contratar.

**Criterios de Aceptación:**
- [x] La página de inicio presenta un encabezado propio de la marca (ocultando la barra superior nativa de Odoo) con acceso rápido a Inicio, Planes y precios, Módulos, Nosotros, Contáctanos, Iniciar sesión y botón destacado «Pruébalo gratis ↗».
- [x] La portada principal comunica de forma directa el beneficio del sistema ERP en la nube con facturación SIAT e incluye una vista previa interactiva con 3 pestañas (Ventas y facturación, Flujo de caja e Inventario y compras).
- [x] Se muestra la franja de respaldo comercial con las empresas clientes que ya operan con la plataforma.
- [x] El visitante puede cambiar entre los distintos perfiles de empresa (Comercializadora, Importadora, Servicios e Industrial) para ver cómo se adapta el sistema a su rubro.
- [x] La página incluye una sección desplegable con las 8 preguntas frecuentes comerciales y operativas más comunes, un pie de página institucional completo y animaciones bidireccionales suaves al subir y bajar por la página.

**Escenario Gherkin:**
```gherkin
Escenario: Visitante recorre la página de inicio y consulta cómo aplica el sistema a su rubro
  Dado que el Cliente ingresa a la página principal de AEI Software ("/")
  Cuando recorre la portada y llega a la sección de perfiles empresariales
  Y selecciona el rubro "Importadora y distribuidora"
  Entonces la pantalla actualiza la recomendación mostrando el enfoque operativo para importaciones y distribución
  Y al desplazarse hacia el final puede abrir cualquiera de las 8 preguntas frecuentes para despejar sus dudas comerciales
```

---

### HU-02: Comparación transparente de planes de suscripción y capacidades incluidas — (5 horas)

**Como** Cliente que busca contratar el sistema,  
**Quiero** comparar en una misma vista los tres planes disponibles (Starter, Pro y Advanced) con su precio en Bolivianos, cantidad de usuarios permitidos, espacio de almacenamiento, horas de soporte mensual y cantidad de reportes incluidos,  
**Para** identificar qué plan se ajusta al tamaño actual de mi empresa y a mi presupuesto.

**Criterios de Aceptación:**
- [x] Se muestran los tres planes ordenados de menor a mayor precio: Starter (Bs 349/mes), Pro (Bs 649/mes) y Advanced (Bs 1.290/mes).
- [x] Cada tarjeta de plan detalla claramente los recursos incluidos: cantidad de usuarios, almacenamiento en gigabytes, horas de soporte al mes y cantidad de reportes operativos.
- [x] El plan Pro se resalta visualmente con el distintivo «Más elegido» para guiar la decisión del cliente hacia la opción más equilibrada.
- [x] Todos los precios se muestran expresados en Bolivianos (Bs) con el formato numérico estándar del país.

**Escenario Gherkin:**
```gherkin
Escenario: Cliente compara las capacidades y precios de los tres planes disponibles
  Dado que el Cliente se ubica en la sección de Planes de la página principal o en "/pricing"
  Cuando revisa las tarjetas de suscripción disponibles
  Entonces visualiza el plan "Starter" a Bs 349 al mes con 3 usuarios, 10 GB de espacio y 2 horas de soporte
  Y visualiza el plan "Pro" destacado como "Más elegido" a Bs 649 al mes con 10 usuarios, 25 GB de espacio y 5 horas de soporte
  Y visualiza el plan "Advanced" a Bs 1.290 al mes con 50 usuarios, 50 GB de espacio y 10 horas de soporte mensual
```

---

### HU-03: Selector de pago Mensual vs. Anual con cálculo automático de descuento (-20%) — (3 horas)

**Como** Cliente que evalúa el costo de la suscripción a mediano plazo,  
**Quiero** alternar entre la modalidad de pago Mensual y la modalidad Anual (-20%) y ver al instante cuánto pagaría por mes en promedio, cuál es el monto total anual y cuánto dinero ahorro al año en cada plan,  
**Para** decidir si me conviene aprovechar el descuento por pago anual.

**Criterios de Aceptación:**
- [x] Sobre las tarjetas de planes se muestra un selector visible con las opciones Mensual y Anual (-20%).
- [x] Por defecto, la página inicia mostrando los precios de facturación mensual flexible.
- [x] Al seleccionar Anual (-20%), las tres tarjetas actualizan automáticamente su valor al precio mensual equivalente con el 20% de descuento aplicado.
- [x] En modalidad anual, cada tarjeta muestra el monto total a facturar en el año y una etiqueta destacada con el ahorro exacto en Bolivianos (por ejemplo, en el plan Starter: equivalente a Bs 279,20/mes, Bs 3.350,40 facturados al año y ahorro de Bs 837,60 al año).
- [x] Al volver a presionar Mensual, las tarjetas regresan de inmediato a los valores mensuales originales sin recargar la página.

**Escenario Gherkin:**
```gherkin
Escenario: Cliente activa la modalidad anual para conocer su ahorro en Bolivianos
  Dado que el Cliente está viendo la sección de planes en modalidad "Mensual"
  Y el plan "Starter" muestra un valor de Bs 349 al mes
  Cuando el Cliente selecciona la opción "Anual (-20%)" en la barra de facturación
  Entonces la tarjeta del plan "Starter" actualiza su precio a Bs 279,20 por mes
  Y muestra la leyenda "Bs 3.350,40 facturados al año" junto con el beneficio "Ahorras Bs 837,60 al año"
  Y la tarjeta del plan "Pro" actualiza su precio a Bs 519,20 por mes indicando "Ahorras Bs 1.557,60 al año"
```

---

### HU-04: Consulta detallada de módulos, procesos operativos y matriz comparativa (`/pricing`) — (3 horas)

**Como** Cliente que necesita confirmar si el sistema cubre las áreas operativas de mi negocio,  
**Quiero** abrir una ventana de detalle desde cada módulo o plan, y además contar con una página dedicada de Planes y Precios (`/pricing`) con una tabla comparativa filtrable por área empresarial,  
**Para** saber exactamente qué procesos y reportes vienen incluidos en Starter, Pro y Advanced antes de contratar.

**Criterios de Aceptación:**
- [x] En la sección de módulos de inicio, cada área operativa cuenta con un botón «Explorar procesos» que abre una ventana emergente con todos los flujos que resuelve ese módulo y desde qué plan está disponible.
- [x] En cada tarjeta de plan, el botón «Ver módulos y procesos» abre una ventana emergente con el resumen completo del plan, sus capacidades técnicas y el listado exacto de módulos y procesos que incluye.
- [x] La página dedicada `/pricing` presenta las 3 tarjetas de planes, los 4 distintivos de garantía («Instancia privada», «Facturación SIAT*», «Roles y contador», «Respaldos y exportación») y las notas aclaratorias legales.
- [x] En `/pricing#modulos` se muestra la matriz comparativa completa con filtros interactivos por categoría (`Todos`, `Comercial`, `Operaciones`, `Finanzas`, `RRHH`) y en `/pricing#reportes` el desglose de los 7 reportes base de Starter y los 15 reportes de Pro y Advanced.

**Escenario Gherkin:**
```gherkin
Escenario: Cliente filtra la matriz comparativa de módulos en la página de precios
  Dado que el Cliente ingresa a la página dedicada "/pricing"
  Cuando se desplaza hasta la tabla comparativa "#modulos" y selecciona el filtro "Operaciones"
  Entonces la tabla muestra únicamente los módulos operativos (Compras e Inventario, Proyectos y Servicios, Producción MRP) indicando con íconos qué plan incluye cada uno
  Y al bajar a la sección "#reportes" visualiza los 7 reportes financieros de Starter y los 8 reportes adicionales de Pro y Advanced
```

---

### HU-05: Selección de plan y asistente de contratación en 3 pasos (`/checkout`) — (10 horas)

**Como** Cliente que ya eligió el plan adecuado para su empresa,  
**Quiero** presionar el botón de contratación («Elegir Starter / Pro / Advanced» o «Probar 15 días gratis») y ser llevado a un asistente guiado de 3 pasos con diseño AEI Software («1. Tu cuenta», «2. Tu empresa», «3. Activación / Pago QR») sin pasar por el carrito genérico de Odoo,  
**Para** completar mi registro, cargar los datos de mi negocio y activar mi suscripción o prueba gratuita en una sola experiencia clara y en Bolivianos.

**Criterios de Aceptación:**
- [x] Cada tarjeta de plan presenta dos botones de acción claros: «Probar 15 días gratis ↗» y «Elegir <Nombre del Plan>».
- [x] Al presionar cualquiera de los botones (o al intentar abrir `/shop/cart`), el sistema redirige automáticamente al asistente `/checkout?plan=<plan>&cycle=<ciclo>&mode=<modo>` ocultando la barra superior nativa de Odoo (`YourLogo`).
- [x] El panel derecho «TU SELECCIÓN» muestra en todo momento el plan elegido, permite alternar en vivo entre Mensual y Anual (-20%) o entre Prueba gratuita y Comprar ahora, calcula el total en Bolivianos (`Bs`) y permite aplicar el cupón de descuento `AEI10` (10 % adicional).
- [x] El Paso 1 («01 / TU CUENTA») permite crear una cuenta nueva o iniciar sesión; el Paso 2 («02 / TU EMPRESA») registra el tipo de cuenta, rubro, nombre de la empresa, NIT, teléfono y ciudad directamente en la ficha del cliente (`res.partner`); y el Paso 3 («03 / PAGO POR QR» o «03 / TU PRUEBA GRATUITA») presenta el código QR del Banco Ganadero o la activación directa de los 15 días sin tarjeta.

**Escenario Gherkin:**
```gherkin
Escenario: Cliente selecciona el plan Pro y avanza por los 3 pasos del asistente de contratación
  Dado que el Cliente revisó los planes en "/pricing" y decidió contratar el plan "Pro"
  Cuando presiona el botón "Elegir Pro"
  Entonces el sistema lo dirige a "/checkout?plan=pro&cycle=monthly&mode=paid" mostrando el título "Ya casi es tuyo." y el resumen lateral por Bs 649,00
  Y una vez que completa el Paso 1 (Cuenta) y el Paso 2 (Datos de su empresa), avanza al Paso 3 donde visualiza el código QR de pago listo para escanear
```

---

### HU-06: Administración centralizada del catálogo de planes y precios desde el panel interno — (4 horas)

**Como** Administrador comercial de AEI Software,  
**Quiero** gestionar los nombres, precios, recursos incluidos (usuarios, almacenamiento y horas de soporte) y la visibilidad pública de cada plan directamente desde el panel administrativo de Odoo, sin depender de cambios manuales en el diseño de la página,  
**Para** actualizar tarifas o pausar planes de forma inmediata y sin riesgo de mostrar información contradictoria a los clientes.

**Criterios de Aceptación:**
- [x] Si el Administrador modifica el precio de venta de un plan en el panel administrativo, la página pública (`/`, `/pricing` y `/checkout`) actualiza automáticamente el precio mensual, el precio anual con descuento y el monto de ahorro anual.
- [x] Si el Administrador modifica la cantidad de usuarios, los gigabytes de almacenamiento o las horas de soporte en la plantilla del plan (`sale.subscription.template`), el nuevo valor se refleja automáticamente en las tarjetas, en `/checkout` y en las ventanas de detalle.
- [x] Si el Administrador desactiva la publicación de un plan en el sitio web (`is_published = False`), esa tarjeta deja de mostrarse al público de inmediato sin afectar la visualización de los demás planes.
- [x] Al actualizar el sistema en un entorno existente, los precios y nombres oficiales (Starter, Pro y Advanced) se actualizan automáticamente sin perder la configuración previa.

**Escenario Gherkin:**
```gherkin
Escenario: Administrador actualiza el precio de un plan y oculta temporalmente otro
  Dado que los planes "Starter", "Pro" y "Advanced" se encuentran publicados en el sitio web
  Cuando el Administrador ingresa al panel de gestión y cambia el precio del plan "Pro" a Bs 700
  Y desmarca la opción de publicación web del plan "Advanced"
  Entonces un Cliente que visite "/" o "/pricing" verá únicamente los planes "Starter" y "Pro"
  Y el plan "Pro" mostrará automáticamente el nuevo precio de Bs 700 al mes y su nuevo cálculo anual con descuento
```

---

### HU-07: Registro, inicio de sesión y recuperación de clave con botón de visualización de contraseña ("Ojito") — (5 horas)

**Como** Cliente que crea su cuenta o inicia sesión en AEI Software,  
**Quiero** contar con formularios de acceso claros en `/account` (`/web/signup`, `/web/login`, `/web/reset_password`) y en el Paso 1 de `/checkout`, que incluyan un botón de "ojito" dentro del campo de contraseña,  
**Para** verificar visualmente lo que estoy escribiendo y evitar bloquear mi acceso por errores de tipeo.

**Criterios de Aceptación:**
- [x] La ruta `/account` redirige automáticamente a `/web/signup` (y `/account?mode=login` redirige a `/web/login`), manteniendo la estética dividida de AEI Software con lista de beneficios a la izquierda y formulario a la derecha.
- [x] En el formulario de registro (`/web/signup` y Paso 1 de `/checkout`), los campos se presentan en orden natural: «Tu nombre», «Correo electrónico», «Contraseña» y «Confirmar contraseña».
- [x] Todos los campos de contraseña incluyen a la derecha el botón interactivo del "ojito" (`.aei-password-toggle` con ícono `.fa-eye`).
- [x] Al presionar el botón del "ojito", el campo alterna entre texto oculto (`type="password"`) y texto visible (`type="text"`), cambiando el ícono a `.fa-eye-slash` y actualizando la etiqueta de accesibilidad (`Mostrar contraseña` / `Ocultar contraseña`).
- [x] Todos los envíos de autenticación validan el token de seguridad `csrf_token` y almacenan la clave cifrada en el motor nativo de Odoo 18.

**Escenario Gherkin:**
```gherkin
Escenario: Cliente verifica su contraseña usando el botón del ojito antes de registrarse
  Dado que el Cliente se encuentra creando su cuenta en "/web/signup" o en el Paso 1 de "/checkout"
  Cuando escribe su clave en el campo "Contraseña" y presiona el ícono del ojito situado a la derecha del campo
  Entonces el campo muestra los caracteres reales de la contraseña y el ícono cambia al ojo tachado
  Y cuando vuelve a presionar el ícono, la contraseña vuelve a ocultarse con puntos de seguridad
```

---

### HU-08: Formulario de contacto comercial y solicitud de asesoría (`/contactus`) — (4 horas)

**Como** Visitante o empresa que desea recibir asesoría antes de contratar un plan,  
**Quiero** completar el formulario de contacto en `/contactus` indicando mi nombre, empresa, correo, teléfono, rubro y mensaje,  
**Para** que el equipo comercial de AEI Software reciba mi consulta por correo y se comunique conmigo.

**Criterios de Aceptación:**
- [x] La página `/contactus` presenta los canales directos de atención (WhatsApp, correo electrónico, horario y ubicación en Santa Cruz de la Sierra) junto al formulario de consulta con estética AEI Software.
- [x] El servidor valida que el nombre, el correo electrónico (con formato válido) y el mensaje estén presentes antes de aceptar el envío, protegiendo la petición con `csrf_token`.
- [x] Al enviarse un formulario válido, el sistema registra el correo saliente en `mail.mail` dirigido a la casilla comercial de AEI Software y redirige al visitante a la pantalla de confirmación `/contactus-thank-you`.

**Escenario Gherkin:**
```gherkin
Escenario: Visitante envía una consulta comercial desde la página de contacto
  Dado que el Visitante ingresa a "/contactus"
  Cuando completa su nombre, correo "gerencia@empresa.bo", selecciona el rubro "Comercial" y escribe su consulta
  Y presiona el botón de envío
  Entonces el sistema registra el mensaje de contacto y muestra la pantalla "/contactus-thank-you" confirmando la recepción
```

---

### HU-09: Generación de orden de cobro QR Empresarial con Banco Ganadero (Puntos 2 y 3 v1.17.4) — (6 horas)

**Como** Cliente que llega al Paso 3 de pago en `/checkout`,  
**Quiero** que el sistema genere automáticamente un código QR por el importe exacto de mi suscripción en Bolivianos (`Bs`),  
**Para** escanearlo desde GanaMóvil o cualquier aplicación bancaria habilitada con QR Simple y pagar sin cargar datos de tarjeta.

**Criterios de Aceptación:**
- [x] El módulo `payment_qr_ganadero` implementa la autenticación saliente hacia `/ws-servicio-codigo-qr-empresas/service/v1/qrcode/access` (Punto 2) enviando la cabecera `XApi--Key` y conservando el token JWT en caché durante 50 minutos.
- [x] Implementa la generación de orden de cobro hacia `/ws-servicio-codigo-qr-empresas/service/v1/qrcode/collections` (Punto 3) enviando `accountReference`, `amount`, `currency` (`BOB` o `USD`), `gloss`, `expirationDate` en formato `ddmmyyyy`, `singleUse=1`, `userName` y `apiKey`.
- [x] El sistema valida automáticamente que ninguna orden en Bolivianos supere el tope máximo permitido por el banco de **Bs 69.000,00**.
- [x] Mientras el proveedor se encuentra en estado *Prueba* (`state = 'test'`), el sistema genera un QR de demostración (`TEST-<referencia>`) para pruebas de extremo a extremo sin requerir conexión al banco.
- [ ] **Pendiente externo:** Cargar las credenciales oficiales del Banco Ganadero (`URL`, `XApi--Key`, `userName`, `password`, `accountReference` solicitadas el `04/11/2026`) y pasar el proveedor a *Habilitado* (`enabled`) para emitir el QR bancario real.

**Escenario Gherkin:**
```gherkin
Escenario: Generación de código QR en el Paso 3 del checkout para el plan Starter
  Dado que el Cliente completó los datos de su empresa y avanzó al Paso 3 en modalidad de compra ("mode=paid")
  Cuando el sistema prepara la transacción de pago con el proveedor "QR Banco Ganadero"
  Entonces se registra la transacción por Bs 349,00 con su identificador "qrId" y se muestra en pantalla la imagen del código QR junto a la referencia del pedido
```

---

### HU-10: Recepción de confirmación de pago del Banco Ganadero vía Webhook JWT (Puntos 6, 7 y 8 v1.17.4) — (8 horas)

**Como** Sistema de cobros de AEI Software,  
**Quiero** exponer los servicios seguros de autenticación (`/payment/qr_ganadero/login`) y notificación de pago (`/payment/qr_ganadero/payments`) exigidos por el Banco Ganadero en su especificación v1.17.4,  
**Para** recibir la confirmación instantánea cuando el cliente paga el QR desde su celular y activar su suscripción sin intervención humana.

**Criterios de Aceptación:**
- [x] El servicio `POST /payment/qr_ganadero/login` (Punto 6) valida `userName` y `password` en tiempo constante (`hmac.compare_digest`), exige que sean estrictamente alfanuméricos sin caracteres especiales (Punto 8) y devuelve `COD000` con un token JWT firmado en `HS256` válido por 1 hora (o `COD001` / `COD002` si faltan datos o tienen formato inválido).
- [x] El servicio `POST /payment/qr_ganadero/payments` (Punto 7) exige la cabecera `Authorization: Bearer <token>`, valida la presencia de `qrId`, `transactionId` y `payDate`, y localiza la transacción pendiente en Odoo.
- [x] El registro de pago es **idempotente**: si el Banco Ganadero envía dos veces la confirmación del mismo `qrId` por un reintento de red, el sistema responde `COD000` sin duplicar pagos, facturas ni contenedores.
- [x] Cuando el proveedor está en modo producción (`enabled`), el sistema bloquea cualquier intento de confirmar el pago manualmente desde el navegador, aceptando únicamente la confirmación autenticada del banco.
- [ ] **Pendiente externo:** Confirmación del Banco Ganadero sobre las rutas enviadas en la Solicitud Técnica del `04/11/2026` y prueba de notificación desde el servidor del banco.

**Escenario Gherkin:**
```gherkin
Escenario: Banco Ganadero autentica su sesión y notifica el pago de un código QR
  Dado que existe una transacción pendiente con qrId "QR01202611130001"
  Cuando el Banco Ganadero solicita un token en "/payment/qr_ganadero/login" con sus credenciales alfanuméricas válidas
  Y envía la notificación de pago a "/payment/qr_ganadero/payments" con el token Bearer y el qrId "QR01202611130001"
  Entonces el sistema marca la transacción como pagada, responde con código "COD000" ("Resultado satisfactorio") y dispara la facturación y el aprovisionamiento del cliente
```

---

### HU-11: Verificación automática de estado de cobro y conciliación diaria (Puntos 4 y 5 v1.17.4) — (8 horas)

**Como** Administrador financiero y Cliente en pantalla de espera de pago,  
**Quiero** que el sistema consulte periódicamente al Banco Ganadero el estado de los QR pendientes (`/qrcode/status`) y permita consultar el resumen de órdenes del día (`/qrcode/transactions`),  
**Para** confirmar pagos incluso si hubo una demora en la notificación entrante y conciliar los cobros diarios.

**Criterios de Aceptación:**
- [x] El módulo implementa el método de consulta de estado individual hacia `/ws-servicio-codigo-qr-empresas/service/v1/qrcode/status` (Punto 5), interpretando `orderState = 1` (Registrado), `2` (Pagado → confirma la transacción) y `3` (Anulado → cancela la transacción).
- [x] Cuenta con una tarea programada (`ir.cron` «QR Banco Ganadero: verificar pagos pendientes») que revisa automáticamente las transacciones pendientes de las últimas 24 horas.
- [x] Implementa el método de consulta de órdenes diarias hacia `/ws-servicio-codigo-qr-empresas/service/v1/qrcode/transactions` (Punto 4) por rango de fechas `startDate` y `endDate` (`ddmmyyyy`).
- [ ] Conectar el auto-refresco en vivo en el Paso 3 del asistente `/checkout` para que, cuando el proveedor esté en modo real y la transacción pase a pagada, la pantalla avance sola a la vista de éxito sin que el cliente tenga que recargar.

**Escenario Gherkin:**
```gherkin
Escenario: Tarea programada detecta un QR pagado en el Banco Ganadero
  Dado que existe una transacción QR en estado "Pendiente"
  Cuando se ejecuta la verificación de estado contra el servicio "/qrcode/status" del Banco Ganadero y éste retorna "orderState: 2" (Pagado)
  Entonces el sistema actualiza la transacción a estado "Confirmado", guarda el número de transacción bancaria y activa la suscripción del cliente
```

---

### HU-12: Facturación automática, activación de suscripción y aprovisionamiento de instancia Odoo 18 en Kubernetes — (16 horas)

**Como** Cliente que acaba de confirmar su pago por QR o su prueba gratuita de 15 días,  
**Quiero** que el sistema confirme mi pedido, emita mi factura como pagada, active mi suscripción y cree automáticamente mi propio ambiente Odoo 18 aislado en la nube,  
**Para** recibir mi sistema listo para operar con los recursos contratados en mi plan.

**Criterios de Aceptación:**
- [x] Al confirmarse el pago QR, Odoo confirma automáticamente el pedido de venta (`sale.order`), genera y concilia la factura (`account.move` en estado `Pagado`) y pasa la suscripción (`sale.subscription`) a estado `En progreso`.
- [x] Se crea automáticamente el registro de instancia SaaS (`saas.instance`) con el subdominio derivado del nombre de la empresa y los recursos del plan contratado (`Starter`, `Pro` o `Advanced`).
- [x] El servicio aprovisionador (`portal/` en FastAPI) crea una base de datos exclusiva en PostgreSQL y despliega en el clúster Kubernetes (K3s) un Namespace propio (`odoo-<subdominio>`), `Secret` con contraseña de administrador de 16 caracteres, `ResourceQuota`, `NetworkPolicy` de aislamiento entre clientes, volumen persistente (`PVC`), `Deployment` de Odoo 18 e `Ingress` de acceso web.
- [x] El envío del PDF de la factura por correo se delega de forma segura al proceso en segundo plano si la confirmación ocurre desde el sitio web, evitando errores de renderizado durante la compra.

**Escenario Gherkin:**
```gherkin
Escenario: Pago confirmado dispara la creación automática del ambiente del cliente en Kubernetes
  Dado que el Cliente "Constructora Andina" confirma el pago de su plan "Starter" en "/checkout"
  Cuando la transacción de pago pasa a estado "Confirmado"
  Entonces el pedido de venta pasa a confirmado, su factura queda en estado "Pagado" y la suscripción pasa a "En progreso"
  Y el aprovisionador de Kubernetes crea el namespace aislado y levanta el contenedor Odoo 18 del cliente hasta quedar en estado "Listo" ("ready")
```

---

### HU-13: Pantalla de confirmación con resumen de acceso y entrega de credenciales al cliente — (4 horas)

**Como** Cliente que finalizó su compra o activó su prueba gratuita en `/checkout`,  
**Quiero** ver una pantalla de confirmación clara con el subdominio asignado a mi empresa, mi usuario de administración (`admin`), el enlace directo para abrir mi ambiente y recibir mis credenciales por correo electrónico,  
**Para** ingresar de inmediato a mi nuevo sistema Odoo 18.

**Criterios de Aceptación:**
- [x] Al completar el Paso 3, el asistente muestra la pantalla de éxito (`.aei-success`) con el plan contratado, estado (`Activa` o `En prueba`), fecha de vigencia y el bloque «Tu ambiente AEI ya está listo».
- [x] El resumen de acceso muestra el enlace clicable al ambiente asignado, el usuario real del sistema (`admin`) y el botón «Abrir mi ambiente ↗».
- [x] En entorno de demostración (`state == 'test'`), la pantalla muestra además la contraseña autogenerada de 16 caracteres y enruta el botón a `<subdominio>.localhost:8080/web/login` para poder ingresar de inmediato sin depender de correo ni DNS externo; en producción (`state == 'enabled'`), la contraseña se oculta de la pantalla por seguridad.
- [x] El módulo `odoo_k8s_saas` cuenta con las 2 plantillas de correo automáticas («Instancia en Preparación» y «¡Tu sistema Odoo está listo! — Credenciales de acceso»).
- [ ] Configurar las credenciales del servidor de correo saliente (SMTP) en el entorno de Staging/Producción para que el correo llegue a la bandeja real del cliente.

**Escenario Gherkin:**
```gherkin
Escenario: Cliente visualiza los datos de acceso a su nuevo ambiente al terminar el checkout
  Dado que el Cliente acaba de confirmar el Paso 3 en "/checkout"
  Cuando se carga la pantalla de confirmación "step=done"
  Entonces visualiza el subdominio asignado a su empresa, el usuario "admin" y el botón "Abrir mi ambiente ↗"
  Y al presionar "Abrir mi ambiente ↗" accede a la pantalla de inicio de sesión de su propia instancia Odoo 18
```

---

### HU-14: Diseño de marca AEI Software en el Portal de Clientes (`/my`) — (4 horas) *(Pendiente — Semana 1)*

**Como** Cliente con suscripción activa que ingresa a «Mi cuenta» (`/my`),  
**Quiero** que el portal donde consulto mis pedidos, mis facturas, mis suscripciones y mis tickets de soporte conserve el encabezado, pie de página y estilo visual de AEI Software (sin mostrar el encabezado genérico `YourLogo` de Odoo),  
**Para** tener una experiencia visual coherente en toda la plataforma.

**Criterios de Aceptación:**
- [x] El portal `/my` ya permite al cliente autenticado consultar sus pedidos (`Your Orders`), sus facturas (`Your Invoices`), sus suscripciones (`Suscripciones`) y sus tickets de soporte (`Tickets`).
- [ ] Reemplazar en `/my` y sus sub-rutas el encabezado y pie de página nativos de Odoo (`YourLogo`) por el encabezado y pie de página de AEI Software (`aei_website.header` y `aei_website.footer`).
- [ ] Unificar la estética de las tarjetas de acceso del portal del cliente con la paleta y tipografía de AEI Software.

**Escenario Gherkin:**
```gherkin
Escenario: Cliente ingresa a su portal y visualiza su cuenta con la identidad visual de AEI Software
  Dado que el Cliente inició sesión y presiona "Ir a mi portal" ("/my")
  Cuando se carga la página de su cuenta
  Entonces visualiza el encabezado y pie de página de AEI Software sin el logotipo genérico "YourLogo"
  Y puede acceder a sus Suscripciones, Facturas y Tickets de soporte
```

---

### HU-15: Ciclo de vida de suscripciones (renovación, suspensión por mora y reactivación en K8s) — (6 horas) *(Verificación final — Semana 2)*

**Como** Administrador de la plataforma AEI Software,  
**Quiero** que el sistema controle automáticamente el vencimiento de las suscripciones, suspenda los contenedores cuyos pagos estén vencidos tras el periodo de gracia y los reactive cuando el cliente renueve su pago por QR,  
**Para** operar el SaaS de forma automatizada sin costos de infraestructura por cuentas inactivas.

**Criterios de Aceptación:**
- [x] El módulo `odoo_k8s_saas_subscription` cuenta con las tareas programadas (`ir.cron`) para sincronizar cantidad de usuarios activos, facturar usuarios adicionales, suspender instancias vencidas (`_cron_suspend_overdue`) y limpiar instancias cerradas tras el periodo de gracia (`_cron_sync_closed_subscriptions`).
- [ ] Ejecutar y certificar la prueba integral de renovación con QR Banco Ganadero y reactivación automática de un contenedor suspendido antes del pase a producción (`18.0`).

**Escenario Gherkin:**
```gherkin
Escenario: Suscripción vencida se suspende automáticamente y se reactiva al registrar el pago de renovación
  Dado que la suscripción de un Cliente superó su fecha de vencimiento y el periodo de gracia sin pago registrado
  Cuando se ejecuta la tarea programada de control de vencimientos
  Entonces la instancia del cliente en Kubernetes pasa a estado suspendido
  Y cuando el Cliente realiza el pago de su factura de renovación, la instancia vuelve a activarse automáticamente
```

 