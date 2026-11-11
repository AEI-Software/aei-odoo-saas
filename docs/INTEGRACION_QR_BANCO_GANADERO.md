# Requerimientos e Integración Técnica — QR Empresarial Banco Ganadero (v1.17.4)

**Documento de referencia:** `Especificaciones_Técnicas_Integración_Qr_v_1_17_4 3.pdf` (Banco Ganadero, versión 1.17.4)  
**Sistema destino:** Odoo 18 (`aei-odoo-saas`)  
**Ambientes del proyecto:**
- **Staging (Pruebas / Certificación):** `https://staging.aeisoftware.com` (rama `main`, namespace `staging`)
- **Producción:** `https://admin.aeisoftware.com` (rama `18.0`, namespace `odoo-admin`)

---

## 1. Resumen Ejecutivo

La integración QR Empresarial del Banco Ganadero opera mediante un esquema **bidireccional con autenticación JWT en ambos sentidos**:

1. **Flujo saliente (Odoo → Banco Ganadero):** Odoo se autentica ante el banco (Punto 2), solicita la generación del código QR de cobro (Punto 3) y, de forma complementaria, puede consultar el estado de una orden (Punto 5) o el listado diario de transacciones (Punto 4).
2. **Flujo entrante / Webhook (Banco Ganadero → Odoo):** A diferencia de otras pasarelas donde se envía una URL de `callback` dinámica por cada QR generado, el Banco Ganadero requiere que la empresa exponga dos servicios fijos en HTTPS:
   - Un servicio de autenticación (`POST /.../login`, Punto 6) donde el banco obtiene un token JWT emitido por Odoo.
   - Un servicio de notificación de pagos (`POST /.../payments`, Punto 7) donde el banco confirma el cobro enviando el token JWT en la cabecera `Authorization: Bearer <token>`.

---

## 2. Datos que se deben solicitar al Banco Ganadero

Para configurar el proveedor de pago en Odoo (tanto en el entorno de certificación/pruebas como en producción), el Banco Ganadero debe entregar los siguientes parámetros:

| # | Parámetro | Uso en la API del Banco | Descripción |
| :- | :--- | :--- | :--- |
| 1 | **URL Base API (Certificación / Sandbox)** | Todos los endpoints salientes (Puntos 2, 3, 4 y 5) | Host y puerto de pruebas donde se publica `/ws-servicio-codigo-qr-empresas/service/v1/qrcode/...` |
| 2 | **URL Base API (Producción)** | Todos los endpoints salientes (Puntos 2, 3, 4 y 5) | Host y puerto productivo del servicio QR del banco. |
| 3 | **Clave de seguridad (`apiKey`)** | Cabecera `XApi--Key` en Punto 2; campo `apiKey` en el cuerpo de Puntos 3, 4 y 5 | Clave alfanumérica (hasta 350 caracteres) asignada a la empresa. El manual escribe la cabecera como `XApi--Key` (doble guion); confirmar con el banco. |
| 4 | **`userName`** | Cuerpo JSON en Puntos 2, 3, 4 y 5 | Código de cliente con rol cobrador de la empresa. |
| 5 | **`password`** | Cuerpo JSON en Punto 2 (`/qrcode/access`) | Clave del cliente con rol cobrador de la empresa. |
| 6 | **`accountReference`** | Cuerpo JSON en Punto 3 (`/qrcode/collections`) | Referencia o alias de la cuenta recaudadora (máx. 20 caracteres), parametrizada en **GanaNet / Administración QR**. |

---

## 3. Datos que AEI Software debe entregar al Banco Ganadero (Puntos 6, 7 y 8)

El documento del banco utiliza la notación `/.../login` (Punto 6) y `/.../payments` (Punto 7). Los puntos suspensivos (`/.../`) representan la ruta base que la empresa define en su servidor antes del nombre final del endpoint.

Siguiendo la convención de controladores de Odoo del proyecto (como en `payment_qr_mercantil` que utiliza `/payment/qr_mercantil/...`), las rutas propuestas para registrar en el Banco Ganadero son:

### 3.1 Endpoints para Ambiente de Certificación / Pruebas (Staging)
- **Autenticación en Empresa (Punto 6):**  
  `https://staging.aeisoftware.com/payment/qr_ganadero/login`
- **Registro de Pago en Empresa (Punto 7):**  
  `https://staging.aeisoftware.com/payment/qr_ganadero/payments`

### 3.2 Endpoints para Ambiente de Producción
- **Autenticación en Empresa (Punto 6):**  
  `https://admin.aeisoftware.com/payment/qr_ganadero/login`
- **Registro de Pago en Empresa (Punto 7):**  
  `https://admin.aeisoftware.com/payment/qr_ganadero/payments`

> **Riesgo a confirmar (Punto 8):** el manual dice que el path debe ser idéntico al especificado (`/.../login`, `/.../payments`) y que no se deben agregar sub-rutas "antes o después del nombre del endpoint". El prefijo `/payment/qr_ganadero/` es una **propuesta nuestra** y podría violar esa regla. Hay que preguntar al banco si lo acepta o si el path debe ser exactamente `/login` y `/payments` (en ese caso habría que verificar que no choquen con rutas existentes de Odoo, p. ej. usando un subdominio dedicado). Ver "Pendientes de confirmar" al final.

### 3.3 Credenciales de acceso para el Banco (Puntos 6 y 8)
AEI Software debe generar y entregar al banco un usuario y contraseña para que el banco invoque el endpoint `/login`:
- **`userName` (entrante):** Alfanumérico (máx. 50 caracteres), **sin caracteres especiales** (`^[A-Za-z0-9]+$`).
- **`password` (entrante):** Alfanumérico (máx. 50 caracteres), **sin caracteres especiales** (`^[A-Za-z0-9]+$`).

---

## 4. Especificación Técnica de los Endpoints a Implementar en Odoo

### 4.1 Servicios que consume Odoo hacia el Banco Ganadero

#### A. Autenticación de Usuario (Punto 2)
- **Ruta:** `POST /ws-servicio-codigo-qr-empresas/service/v1/qrcode/access`
- **Cabeceras:**
  - `XApi--Key`: `<apiKey>` (nombre tal como figura en el manual; confirmar con el banco)
  - `Content-Type`: `application/json`
- **Cuerpo (Request):**
  ```json
  {
    "userName": "<userName>",
    "password": "<password>"
  }
  ```
- **Respuesta esperada:**
  ```json
  {
    "result": "COD000",
    "message": "Resultado satisfactorio",
    "token": "<jwt_token_del_banco>"
  }
  ```

#### B. Generación de Orden de Cobro QR (Punto 3)
- **Ruta:** `POST /ws-servicio-codigo-qr-empresas/service/v1/qrcode/collections`
- **Cabeceras:**
  - `Authorization`: `Bearer <jwt_token_del_banco>`
  - `Content-Type`: `application/json`
- **Cuerpo (Request):**
  ```json
  {
    "accountReference": "<alias_cuenta_gananet>",
    "amount": 349.00,
    "currency": "BOB",
    "gloss": "Pedido S00001",
    "expirationDate": "05112026",
    "singleUse": 1,
    "userName": "<userName>",
    "apiKey": "<apiKey>"
  }
  ```
  - **Restricciones clave:**
    - Monto máximo permitido: `69000.00` Bs.
    - `expirationDate` usa formato `ddmmyyyy` (8 caracteres, sin barras `/`).
    - Según el **Punto 8**, los campos no requeridos (`gloss`, `singleUse`) **deben incluirse siempre como llaves en el JSON**.
- **Respuesta esperada:**
  ```json
  {
    "result": "COD000",
    "message": "Resultado satisfactorio",
    "qrId": "12345678901234567890",
    "qrImage": "<base64_png>"
  }
  ```
  - Odoo debe almacenar `qrId` en el registro `payment.transaction` de forma inmediata, ya que será el único identificador con el que el banco notificará el pago en el Punto 7.

#### C. Consulta de Estado de la Orden (Punto 5 — Respaldo / Polling)
- **Ruta:** `POST /ws-servicio-codigo-qr-empresas/service/v1/qrcode/status`
- **Cabeceras:**
  - `Authorization`: `Bearer <jwt_token_del_banco>`
  - `Content-Type`: `application/json`
- **Cuerpo (Request):**
  ```json
  {
    "qrId": "12345678901234567890",
    "userName": "<userName>",
    "apiKey": "<apiKey>"
  }
  ```
- **Respuesta esperada:**
  - `orderState`: `1` = Registrado, `2` = Pagado, `3` = Anulado, `5` = Tipo de orden incorrecta.
  - Incluye `payday` (`ddmmyyyy`), `payHour` (`hh:mm`) y `transactionNumber`.

---

### 4.2 Servicios que Odoo debe exponer para el Banco Ganadero (Puntos 6, 7 y 8)

> **Requisito en Odoo:** Ambos controladores deben declararse con `type='http'`, `auth='public'`, `methods=['POST']`, `csrf=False`, `save_session=False`. No se debe utilizar `type='json'` porque Odoo envuelve la salida en formato JSON-RPC (`{"jsonrpc": "2.0", "result": ...}`), lo cual incumple la estructura exigida por el banco.

#### A. Autenticación en Empresa (`POST /payment/qr_ganadero/login` — Punto 6)
- **Entrada recibida del banco:**
  ```json
  {
    "userName": "<usuario_alfanumerico>",
    "password": "<clave_alfanumerica>"
  }
  ```
- **Lógica en Odoo:**
  1. Verificar que `userName` y `password` estén presentes (si faltan, devolver `COD001`).
  2. Validar formato alfanumérico y coincidencia con las credenciales configuradas en el proveedor de pago (usando comparación en tiempo constante `hmac.compare_digest`).
  3. Generar un token JWT firmado (o token firmado con expiración) para el banco.
- **Respuesta de Odoo:**
  ```json
  {
    "result": "COD000",
    "message": "Resultado satisfactorio",
    "token": "<jwt_emitido_por_odoo>"
  }
  ```

#### B. Registro de Pago en Empresa (`POST /payment/qr_ganadero/payments` — Punto 7)
- **Cabecera recibida del banco:**
  - `Authorization: Bearer <jwt_emitido_por_odoo>`
- **Entrada recibida del banco:**
  ```json
  {
    "qrId": "12345678901234567890",
    "transactionId": "000012345678",
    "payDate": "04112026"
  }
  ```
- **Lógica en Odoo:**
  1. Validar la firma y vigencia del token en la cabecera `Authorization: Bearer`.
  2. Verificar que `qrId`, `transactionId` y `payDate` estén presentes (`COD001` si falta alguno) y cumplan el formato (`COD002` si el formato es inválido).
  3. Buscar la transacción en `payment.transaction` por el campo `qrId`.
  4. **Idempotencia:** Si la transacción ya se encuentra en estado `done`, responder `COD000` sin reprocesar.
  5. Si está pendiente, registrar `transactionId` y `payDate`, confirmar el pago (`_set_done()`) para disparar la activación de la suscripción y el aprovisionamiento del tenant en Kubernetes, y responder `COD000`.
- **Respuesta de Odoo:**
  ```json
  {
    "result": "COD000",
    "message": "Resultado satisfactorio"
  }
  ```

---

## 5. Tabla de Códigos de Respuesta Obligatorios (Punto 8)

Todas las respuestas de los servicios implementados por la empresa (`/login` y `/payments`) deben utilizar exclusivamente estos códigos en el campo `result`:

| Código | Significado según especificación | Cuándo devolverlo en Odoo |
| :--- | :--- | :--- |
| `COD000` | Resultado satisfactorio | Login válido o pago procesado (incluyendo notificaciones repetidas de un pago ya confirmado). |
| `COD001` | Parámetros de entrada insuficientes | Falta algún campo requerido en el JSON (`userName`, `password`, `qrId`, `transactionId`, `payDate`). |
| `COD002` | Parámetros fuera del formato establecido | Longitud o tipo inválido, o fecha que no cumple `ddmmyyyy`. *(Decisión nuestra, no definida por el manual: usarlo también para credenciales inválidas o `qrId` inexistente.)* |
| `COD003` | Problemas de procesamiento, vuelva a intentar | Error interno o excepción inesperada en base de datos para que el banco reintente la notificación. |

---

## 6. Consideraciones de Infraestructura (Cloudflare y Red)

1. **Regla WAF en Cloudflare:** Los dominios `staging.aeisoftware.com` y `admin.aeisoftware.com` están detrás de Cloudflare. Se debe verificar que **Bot Fight Mode** o desafíos interactivos (JS Challenge / Managed Challenge) estén desactivados para las rutas `/payment/qr_ganadero/login` y `/payment/qr_ganadero/payments`, permitiendo peticiones `POST` directas desde los servidores del Banco Ganadero.
2. **Salida HTTPS desde el pod de Odoo:** Si se aplica la `NetworkPolicy` de producción (`k8s/06b-odoo-admin-netpol.yaml`), se debe permitir explícitamente el tráfico de salida (`Egress`) hacia el puerto HTTPS (443 o el puerto que indique el Banco Ganadero) para que los workers de Odoo puedan consumir `/qrcode/access`, `/qrcode/collections` y `/qrcode/status`.


> Las recomendaciones de Cloudflare/NetworkPolicy de esta sección son **nuestras**, no figuran en el manual del banco.

---

## 7. Pendientes de confirmar con el banco

Contrastado contra el manual v1.17.4 (09/06/2026), estos puntos **no están definidos** y hay que preguntarlos:

1. **Path de los servicios (Punto 8):** ¿se acepta el prefijo `/payment/qr_ganadero/` o debe ser exactamente `/login` y `/payments`?
2. **Nombre de la cabecera:** el manual dice `XApi--Key` (doble guion). ¿Es literal o es `X-Api-Key`?
3. **Dato `Reference` (Punto 5):** el manual dice que se entrega al cliente para que lo escriba en la glosa al pagar desde su app, pero el Punto 3 (`/collections`) no tiene un campo `reference`. ¿Dónde se define y cómo se relaciona con `gloss` y `qrId`?
4. **URLs base** de Certificación y Producción: el manual solo trae rutas relativas.
5. **TTL del token**, **política de reintentos** ante `COD003` y **simulador de pagos en sandbox**: no figuran en el manual.
6. Inconsistencia menor del manual: el monto máximo es 69.000 Bs en el Punto 3, pero "5 veces el sueldo mínimo" en el Punto 4.
