# SDD: Pasarela de Pago QR Empresarial Banco Ganadero (`payment_qr_ganadero`)

- **Estado:** En ejecución (10/11/2026).
- **Módulo:** `addons/payment_qr_ganadero` (depende de `payment`, `website_sale`).
- **Especificación de referencia:** Manual técnico Banco Ganadero *Integración QR Empresarial v1.17.4* (09/06/2026) y [INTEGRACION_QR_BANCO_GANADERO.md](../INTEGRACION_QR_BANCO_GANADERO.md).

---

## 1. Objetivo

Integrar el servicio **QR Empresarial v1.17.4 del Banco Ganadero** como proveedor de pago nativo en Odoo 18 (`code = 'qr_ganadero'`), permitiendo:
1. Autenticación saliente con caché de JWT en base de datos (Punto 2: `/qrcode/access`), generación de orden de cobro QR (Punto 3: `/qrcode/collections`), consulta de estado individual (Punto 5: `/qrcode/status`) y listado diario de órdenes (Punto 4: `/qrcode/transactions`).
2. Exposición de los dos servicios entrantes requeridos por el Banco Ganadero: autenticación del banco en la empresa (Punto 6: `/login`) y confirmación de pagos con JWT Bearer e idempotencia (Punto 7: `/payments`), cumpliendo estrictamente la tabla de códigos `COD000`, `COD001`, `COD002` y `COD003` (Punto 8).
3. Operación completa en **Modo Prueba (`state == 'test'`)** con generación de QR SVG de demostración y simulación segura, permitiendo certificar el flujo de checkout y aprovisionamiento SaaS en K3s sin depender de las credenciales productivas del banco.

---

## 2. Alcance

### Incluye
- Proveedor de pago `qr_ganadero` en `payment.provider` y método `qr_ganadero` en `payment.method` y `account.payment.method`.
- Consumo saliente de los Puntos 2 (`/qrcode/access`), 3 (`/qrcode/collections`), 4 (`/qrcode/transactions`) y 5 (`/qrcode/status`).
- Endpoints entrantes para el banco: Punto 6 (`/payment/qr_ganadero/login`) y Punto 7 (`/payment/qr_ganadero/payments`).
- Pantalla pública de pago QR (`/payment/qr_ganadero/display`), polling de estado (`/payment/qr_ganadero/status`), simulación en modo test (`/payment/qr_ganadero/simulate`) y cron de respaldo cada 2 minutos (`_cron_qr_ganadero_poll_pending`).
- Suite de pruebas automatizadas (`TransactionCase` / `HttpCase`) con `unittest.mock.patch` (cero llamadas de red reales).

### Fuera de alcance
- Modificar `addons/payment_qr_mercantil` (ambos proveedores coexisten de manera independiente).
- Reglas externas de WAF en Cloudflare (se documentan como requisito de infraestructura).

---

## 3. Arquitectura y Estructura de Archivos (`structure_gate.py`)

Todos los archivos `.py` y `.xml` cumplen el límite de **≤ 200 líneas** (máximo duro 250), docstrings obligatorios en cada clase/método y modelos organizados en subcarpetas por dominio:

```text
addons/payment_qr_ganadero/
├── AGENTS.md
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   ├── bank_webhook.py          # Puntos 6 (/login) y 7 (/payments) con JWT HS256 y COD000..COD003
│   ├── display_qr.py            # GET /payment/qr_ganadero/display
│   ├── simulate_payment.py      # POST /payment/qr_ganadero/simulate (solo state == 'test')
│   └── status_polling.py        # POST /payment/qr_ganadero/status (polling con SKIP LOCKED)
├── data/
│   ├── ir_cron_poll.xml         # Cron cada 2 min para pagos pendientes
│   └── payment_provider_data.xml # payment.method, account.payment.method y payment.provider
├── models/
│   ├── __init__.py
│   ├── payment_method/
│   │   ├── __init__.py
│   │   └── account_payment_method.py
│   ├── provider/
│   │   ├── __init__.py
│   │   ├── inbound_jwt.py       # Emisión y verificación HS256 del JWT para el banco (Puntos 6 y 7)
│   │   ├── provider_fields.py   # Campos de configuración y credenciales en payment.provider
│   │   ├── qr_requests.py       # Puntos 3 (/collections), 4 (/transactions) y 5 (/status)
│   │   └── token_auth.py        # Punto 2 (/access) y caché de JWT en BD con threading.Lock
│   └── transaction/
│       ├── __init__.py
│       ├── payment_transaction.py # Generación de valores de QR y procesamiento de notificación
│       └── transaction_cron.py    # Cron de respaldo _cron_qr_ganadero_poll_pending
├── security/
│   └── ir.model.access.csv
├── static/
│   └── src/
│       └── js/
│           └── qr_ganadero_form.js # Polling frontend seguro (sin innerHTML) + botón Demo
├── tests/
│   ├── __init__.py
│   ├── test_bank_webhooks.py    # Tests TDD de Puntos 6, 7 y 8 (COD000, COD001, COD002, COD003)
│   └── test_outbound_api.py     # Tests TDD de Puntos 2, 3, 4 y 5 con mocks HTTP
└── views/
    ├── payment_provider_views.xml
    └── payment_qr_ganadero_templates.xml
```

---

## 4. Escenarios Given / When / Then (Base para TDD)

- **S1 — Autenticación saliente y caché de JWT (Punto 2):**
  - *Given* un proveedor `qr_ganadero` en estado `enabled` sin token en caché,
  - *When* se invoca `_qr_ganadero_get_token()`,
  - *Then* envía `POST /ws-servicio-codigo-qr-empresas/service/v1/qrcode/access` con header `XApi--Key` y cuerpo `{"userName", "password"}`, verifica `result == "COD000"`, guarda el token en `qr_ganadero_token_cache` y una segunda llamada reutiliza el caché sin hacer otra petición HTTP.
- **S2 — Generación de orden de cobro QR y límite de monto (Punto 3 y Punto 8):**
  - *Given* una transacción en `BOB` por `349.00` (≤ `69000.00` Bs),
  - *When* se invoca `_qr_ganadero_generate_qr()`,
  - *Then* envía `POST .../qrcode/collections` con `Authorization: Bearer <token>` y cuerpo JSON conteniendo todas las llaves (`accountReference`, `amount`, `currency`, `gloss`, `expirationDate` en formato `ddmmyyyy`, `singleUse`, `userName`, `apiKey`), y almacena `qrId` y `qrImage` en `payment.transaction`. Si el monto supera `69000.00` Bs, lanza `ValidationError`.
- **S3 — Modo Demo (`state == 'test'`):**
  - *Given* el proveedor `qr_ganadero` en estado `test`,
  - *When* un cliente genera un QR en checkout y presiona Simular Pago,
  - *Then* se genera un QR SVG ficticio (`TEST-<ref>`) sin llamadas HTTP al banco y `/payment/qr_ganadero/simulate` confirma la transacción (`state == 'done'`). Si `state != 'test'`, `/simulate` rechaza la petición.
- **S4 — Autenticación entrante del Banco en Odoo (Punto 6 y Punto 8):**
  - *Given* credenciales entrantes alfanuméricas configuradas en el proveedor (`qr_ganadero_bank_user` y `qr_ganadero_bank_password`),
  - *When* el banco envía `POST /payment/qr_ganadero/login` con `{"userName", "password"}`,
  - *Then* si faltan campos devuelve `{"result": "COD001", ...}`; si tienen caracteres no alfanuméricos o no coinciden devuelve `{"result": "COD002", ...}`; si coinciden devuelve `{"result": "COD000", "message": "Resultado satisfactorio", "token": "<jwt>"}`.
- **S5 — Confirmación de pago entrante e Idempotencia (Punto 7 y Punto 8):**
  - *Given* una transacción pendiente con `qr_ganadero_qr_id = "QR12345"` y un JWT válido emitido por `/login`,
  - *When* el banco envía `POST /payment/qr_ganadero/payments` con `Authorization: Bearer <jwt>` y `{"qrId": "QR12345", "transactionId": "000012345678", "payDate": "10112026"}`,
  - *Then* la transacción pasa a `done` exactamente una vez y devuelve `{"result": "COD000", "message": "Resultado satisfactorio"}`. Si el banco reenvía la misma notificación, responde `COD000` sin reprocesar (idempotente).
- **S6 — Validación de errores en `/payments` (Punto 7 y Punto 8):**
  - *Given* el endpoint `/payment/qr_ganadero/payments`,
  - *When* falta algún parámetro (`qrId`, `transactionId`, `payDate`),
  - *Then* devuelve `COD001`; cuando `payDate` no cumple `ddmmyyyy` (8 dígitos) o `qrId` no existe, devuelve `COD002`; cuando el header `Authorization: Bearer` es inválido o expiró, devuelve HTTP `401` con `COD002`.
- **S7 — Consulta de estado y Cron de respaldo (Punto 5):**
  - *Given* una transacción pendiente con `qr_ganadero_qr_id` de las últimas 24 h,
  - *When* corre `_cron_qr_ganadero_poll_pending()` y `/qrcode/status` devuelve `orderState == 2` (Pagado),
  - *Then* la transacción se marca como `done` y guarda `transactionNumber` y `payday`.

---

## 5. Criterios de Aceptación

1. Todos los escenarios S1–S7 tienen tests automatizados en `addons/payment_qr_ganadero/tests/` y pasan en verde.
2. `python3 .github/scripts/structure_gate.py` reporta **0 nuevas violaciones**.
3. `bash .github/scripts/security_gate.sh` y Bandit pasan sin errores.
4. El módulo se instala limpiamente en la base `admin` del clúster K3s local.

---

## 6. Verification Plan (Security & Quality)

### Automated Security Check
- **Security Scanner & Gate**: Ejecutar `.github/scripts/security_gate.sh`, `structure_gate.py` y `bandit` sobre todos los archivos creados en `addons/payment_qr_ganadero/`.
- **Security Audit Controls Enforced**:
  - **Autenticación y JWT (Puntos 6 y 7):** Comparación de credenciales en tiempo constante (`hmac.compare_digest`), firma JWT con `HS256` verificando algoritmo explícito (rechazo de `alg: none`) y tiempo de expiración (`exp`). Secreto JWT generado con CSPRNG (`secrets.token_hex(32)`) por proveedor sin valores literales quemados en código.
  - **Excepción CSRF documentada:** `/payment/qr_ganadero/login` y `/payment/qr_ganadero/payments` usan `csrf=False` por ser webhooks servidor-a-servidor autenticados mediante credenciales y JWT Bearer, documentados en `addons/payment_qr_ganadero/AGENTS.md`.
  - **Prevención de XSS en Frontend:** `qr_ganadero_form.js` utiliza exclusivamente `textContent`, `createElement` y `replaceChildren` (prohibido `innerHTML`).
  - **Prevención de SQL Injection:** Consultas SQL parametrizadas (`%s`) para caché de token y `SELECT ... FOR UPDATE SKIP LOCKED`.
  - **Protección de Secretos en Logs:** Prohibido registrar en logs contraseñas, `apiKey` o tokens JWT completos.

