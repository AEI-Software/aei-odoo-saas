# SDD: Pantallas de Cuenta (`/web/login`, `/web/signup`), Contacto (`/contactus`) y Animaciones Bidireccionales de Scroll en `aei_website`

- **Estado:** Aprobado para implementación (11/11/2026)
- **Módulo:** `addons/aei_website`
- **Referencias visuales:**
  - `https://aei-software-editable.alexandersaucedopaz.chatgpt.site/account/`
  - `https://aei-software-editable.alexandersaucedopaz.chatgpt.site/contactus/`

## 1. Objetivo

1. Reemplazar la vista nativa de inicio de sesión, registro y recuperación de contraseña de Odoo (`/web/login`, `/web/signup`, `/web/reset_password`, más ruta amigable `/account`) por el diseño aprobado de AEI Software (`/account/`), manteniendo el motor real de autenticación y sesiones de Odoo 18.
2. Reemplazar la vista nativa de contacto (`/contactus` y `/contactus-thank-you`) por el diseño aprobado de AEI Software (`/contactus/`), con envío real protegido por CSRF hacia el correo configurado de la compañía.
3. Incorporar animaciones y transiciones fluidas de **entrada y salida al hacer scroll** (bidireccionales y escalonadas) en la portada, cuenta y contacto, respetando `prefers-reduced-motion`.

## 2. Alcance y Límites

### Incluye
- Herencia de `web.login_layout` / `website.login_layout`, `web.login`, `auth_signup.signup` y `auth_signup.reset_password` con encabezado y pie propios (`aei_website.header`, `aei_website.footer`), sin clases Bootstrap y con prefijo `aei-`.
- Redirección amigable `GET /account` → `/web/login`.
- Herencia de `website.contactus` y `website.contactus_thanks` + desactivación del header/footer nativo de Odoo en todas las copias `website.page` de `/`, `/contactus` y `/contactus-thank-you`.
- Controlador HTTP con CSRF activo (`POST /contactus/submit`) y modelo `website` (`submit_aei_contact_form`) que valida entradas y registra el mensaje en `mail.mail`.
- Motor de transiciones de entrada/salida por scroll (`IntersectionObserver` continuo en `landing.js` + reglas CSS en `foundation/effects/motion.css` y `refinements/effects/motion.css`).

### Fuera de alcance
- Autenticación simulada en `localStorage` o botón de Google simulado (se usa únicamente autenticación real de Odoo; si `auth_oauth` tiene proveedores activos, se renderizan).
- Modificación de reglas de negocio de suscripciones o checkout (`odoo_k8s_saas_subscription`).

## 3. Escenarios (Dado / Cuando / Entonces)

### E10. Pantalla de inicio de sesión (`/web/login` y `/account`)
- **Dado** un visitante no autenticado que hace clic en "Iniciar sesión" o abre `/web/login` (o `/account`),
- **Cuando** se renderiza la respuesta HTTP,
- **Entonces** devuelve 200 (o redirección a `/web/login` desde `/account`), oculta el header/footer nativo de Odoo (`d-none` / `no_header`), muestra `aei-site-header`, `aei-account-section` ("TU CUENTA AEI", "Tu empresa. Un nuevo comienzo."), la tarjeta `.aei-auth-panel` ("01 / TU CUENTA", "Comienza por ti."), las pestañas Crear cuenta / Iniciar sesión y el formulario `POST /web/login` con `csrf_token`, campos `login` y `password`, y enlace a `/web/reset_password`.

### E11. Pantallas de registro (`/web/signup`) y recuperación (`/web/reset_password`)
- **Dado** un visitante que abre `/web/signup` o `/web/reset_password`,
- **Cuando** se renderiza la página,
- **Entonces** responde 200 dentro del mismo layout `.aei-account-section` con `csrf_token` válido y cero clases Bootstrap en las plantillas del módulo.

### E12. Pantalla de contacto (`/contactus`) y envío con protección CSRF
- **Dado** un visitante que abre `/contactus`,
- **Cuando** visualiza la página y envía `POST /contactus/submit` con `csrf_token` y datos válidos (`name`, `email_from`, `subject`, `description`),
- **Entonces** `/contactus` muestra el encabezado `.aei-page-heading` ("CONVERSEMOS", "Tu siguiente paso empieza aquí."), el formulario `.aei-contact-form` y la columna `.aei-contact-aside` ("Nos vemos en Santa Cruz", WhatsApp y Google Maps); al enviar datos válidos se crea el registro `mail.mail` y redirige a `/contactus-thank-you`; si los datos son inválidos responde con un mensaje genérico sin filtrar detalles internos; si falta `csrf_token` rechaza la petición (400/403).

### E13. Animaciones de entrada y salida al hacer scroll
- **Dado** cualquier página pública de `aei_website` (portada `/`, `/web/login`, `/contactus`),
- **Cuando** el usuario hace scroll hacia abajo o hacia arriba,
- **Entonces** los bloques marcados con `.aei-reveal` (y sus variantes direccionales/escalonadas) transicionan suavemente al entrar (`.aei-is-visible`) y al salir del viewport (`.aei-is-exiting`) mediante `IntersectionObserver` sin `unobserve`, desactivándose automáticamente si `prefers-reduced-motion: reduce` está activo.

### E14. Cumplimiento estático y estructural
- **Dado** el árbol completo de `addons/aei_website`,
- **Cuando** se ejecutan `TestStaticRules` y `structure_gate.py`,
- **Entonces** ninguna plantilla ni CSS usa clases Bootstrap ni selectores globales desnudos, toda clase lleva prefijo `aei-`, ningún archivo supera las 200–250 líneas, y el JS no usa `innerHTML`, `outerHTML`, `insertAdjacentHTML` ni `document.write`.

## 4. Plan de Verificación de Seguridad (DevSecOps)

- **CSRF obligatorio:** Todos los formularios POST (`/web/login`, `/web/signup`, `/web/reset_password`, `/contactus/submit`) incluyen `<input type="hidden" name="csrf_token" t-att-value="request.csrf_token()"/>` y jamás usan `csrf=False`.
- **Validación y saneamiento de entradas:** En `submit_aei_contact_form`, validación estricta de tipos, longitudes máximas (`name <= 120`, `email_from <= 150`, `phone <= 40`, `company <= 120`, `subject <= 180`, `description <= 4000`), formato de correo electrónico y campo *honeypot* (`website_url`) contra bots.
- **Prevención de XSS:** Renderizado exclusivo mediante QWeb auto-escapado (`t-esc` / `t-out`) y manipulación DOM segura en `landing.js` (`classList`, `setAttribute`, `textContent`).
- **Gestión de sesiones y credenciales:** Delegada íntegramente al motor nativo de Odoo (`web` / `auth_signup` / `saas_security_hardening`), sin almacenar tokens en `localStorage`/`sessionStorage` ni registrar credenciales en logs.
- **Activos locales:** Cero scripts o fuentes desde CDNs externos.

## 5. Criterios de Aceptación

- [ ] Pruebas automatizadas en `tests/test_account_and_contact.py` fallan antes de implementar (Red) y pasan después (Green).
- [ ] Las pruebas existentes (`test_landing.py`, `test_landing_offers.py`, `test_static_rules.py`) siguen pasando al 100%.
- [ ] `python3 .github/scripts/structure_gate.py` reporta `0 new violation(s)`.
- [ ] `bash .github/scripts/security_gate.sh` pasa sin errores.

