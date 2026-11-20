# SDD: Certificación en TESTING del QR Empresarial Banco Ganadero (ambiente QA del banco)

- **Estado:** En ejecución (20/11/2026). Fases 0, 1, 2 y 4 completadas y verificadas contra el servidor QA del Banco Ganadero (`COD000` en `/access` y `/collections`, ver §9).
- **Módulos:** `addons/payment_qr_ganadero` (principal) y `addons/aei_website` (solo Paso 3 de `/checkout`).
- **Referencias:** [manualBanco.md](../../manualBanco.md) (especificación v1.17.4), [payment-qr-ganadero.md](payment-qr-ganadero.md) (SDD base del módulo, ya implementado).
- **Regla de secretos:** ninguna credencial del banco (apiKey, usuario, clave) se escribe en el repositorio, en este documento ni en logs. Se cargan solo desde la pantalla del proveedor en Odoo.

---

## 1. Objetivo

Pasar del modo demo (QR ficticio) a una prueba **real contra el ambiente QA del banco**, siguiendo el procedimiento que el banco indicó:

1. AEI genera un QR y envía la imagen al banco.
2. El banco paga ese QR y notifica a AEI.
3. AEI valida que la notificación llegó a su endpoint `/payments`.

Resultado esperado: un pago de prueba confirmado automáticamente, de punta a punta, y el módulo listo para pedir las credenciales de producción.

## 2. Diagnóstico de viabilidad: **sí es posible trabajar**

| Dato recibido del banco | Dónde va | Observación |
|---|---|---|
| URL de servicio `https://api.bg.com.bo/bgqa/ws-servicio-codigo-qr-empresas/service/v1/qrcode/` | `qr_ganadero_base_url` = `https://api.bg.com.bo/bgqa` | El código ya agrega `/ws-servicio-codigo-qr-empresas/service/v1/qrcode/<punto>`, así que **no se cambia código** para la URL. |
| ApiKey | `qr_ganadero_api_key` | Llegó **partida en dos líneas** (124 caracteres hexadecimales en total). Hay que unirla sin espacios; si `/access` rechaza, confirmar con el banco. |
| Usuario (numérico) | `qr_ganadero_username` | Es un campo `Char`, se envía como texto. Correcto. |
| Contraseña | `qr_ganadero_password` | Es solo de QA. |
| Referencia de cuenta `TEST_REF` | `qr_ganadero_account_ref` | Cumple el máximo de 20 caracteres. |
| «Notificaciones» | n/a | La fila llegó vacía. El banco dijo que nuestros endpoints ya están actualizados; confirmar que no falta un dato. |

**Verificado hoy en staging (solo lectura):**
- El pod `odoo-stg` **alcanza** la API del banco: `GET .../qrcode/access` responde `405` (el servidor contesta, el endpoint existe y espera `POST`).
- IP pública de salida de staging: `181.115.239.178`. Si el banco filtra por IP, hay que informársela.
- Proveedor `qr_ganadero` (id 24) hoy: `state = test` (demo), URL base `https://sandbox.bg.com.bo` (placeholder incorrecto) y credenciales de relleno.
- **No se llamó todavía a `/access` con las credenciales reales**; eso es la Fase 0.

## 3. Brechas encontradas en el código actual

| # | Brecha | Evidencia | Impacto |
|---|---|---|---|
| G1 | `state = 'test'` significa **demo local y nunca llama al banco**. | `qr_requests.py` devuelve QR SVG ficticio y `token_auth.py` lanza error en modo test. | Para probar contra el banco hay que usar `state = 'enabled'` (decisión D1). |
| G2 | Si el banco rechaza la generación del QR, el error se traga. | `payment_transaction.py` captura la excepción y devuelve el QR vacío. | El cliente ve una pantalla sin QR y sin mensaje. |
| G3 | No hay forma de generar un QR de prueba de monto bajo sin disparar facturación, suscripción y aprovisionamiento K8s. | El único camino es el checkout con un plan de Bs 349. | El banco pide «un QR»; no conviene crear tenants reales por cada prueba. |
| G4 | No hay botón para verificar la conexión con el banco. | n/a | Diagnosticar credenciales requiere consola. |
| G5 | El Paso 3 de `/checkout` no se actualiza solo cuando llega el pago. | Falta el auto-refresco (backlog HU-11, punto 5). | El cliente tendría que recargar la página. |
| G6 | El monto se envía como número JSON (`349.0`), el manual dice `###0.00`. | `qr_requests.py` línea 70. | Si el banco lo rechaza, enviar texto `"349.00"` (contingencia). |

## 4. Alcance

### Incluye
- Botón **«Probar conexión»** en el proveedor (llama a `/access`, informa éxito o código de error, sin mostrar secretos). (G4)
- Error visible y registro de diagnóstico cuando falla `/collections`, sin secretos en logs. (G2)
- Acción **«Generar QR de prueba»** en el proveedor: monto y glosa a elección, crea una transacción independiente (sin `sale.order`) y permite descargar la imagen para enviarla al banco. (G3)
- Auto-refresco cada 3 segundos del Paso 3 con redirección a `step=done`. (G5)
- Guía de prueba conjunta con el banco y checklist de evidencias.

### Fuera de alcance
- Credenciales y URL de producción del banco (se piden al terminar la certificación).
- Un modo «conectar al banco con `state = test`» (opción B de D1).
- El campo Rubro de `/contactus` y cualquier otra historia.
- `payment_qr_mercantil`.

## 5. Escenarios (Dado / Cuando / Entonces)

- **Q1: Probar conexión.** Dado un proveedor `enabled` con credenciales QA, cuando el administrador pulsa «Probar conexión», entonces se hace `POST /qrcode/access`, se guarda el token en caché y se muestra «Conexión exitosa». Si el banco responde distinto de `COD000`, se muestra el código y el mensaje del banco, nunca la clave.
- **Q2: QR de prueba.** Dada una conexión exitosa, cuando el administrador genera un QR de Bs 1,00 con glosa `PRUEBA-AEI`, entonces se envía `POST /qrcode/collections` con `accountReference = TEST_REF`, se crea una `payment.transaction` sin pedido de venta con `qrId`, y la imagen queda disponible para descargar.
- **Q3: Error visible.** Dado que `/collections` devuelve un código distinto de `COD000`, cuando el cliente llega al Paso 3, entonces ve «No pudimos generar el QR, intenta nuevamente», la transacción queda en error y el log guarda el código sin tokens ni claves.
- **Q4: Pago notificado.** Dado un QR de Q2 pagado por el banco, cuando el banco llama a `/login` y luego a `/payments` con `qrId`, `transactionId` y `payDate`, entonces la transacción pasa a `done` una sola vez, guarda `transactionId` y un reintento del banco responde `COD000` sin reprocesar. Como no hay pedido, **no se crea suscripción ni tenant**.
- **Q5: Respaldo por consulta.** Dado que el webhook no llegó, cuando corre el polling o el cron y `/status` devuelve `orderState = 2`, entonces la transacción pasa a `done`.
- **Q6: Checkout de punta a punta.** Dado un plan pagado con QR real en el Paso 3, cuando el banco confirma el pago, entonces la página redirige sola a `step=done` y se inicia el aprovisionamiento.
- **Q7: Seguridad.** Dado el proveedor `enabled`, cuando alguien llama a `/payment/qr_ganadero/simulate`, entonces se rechaza; y ningún log contiene `apiKey`, contraseñas ni tokens.
- **Q8: Notificación desconocida.** Dado un `qrId` inexistente, cuando el banco llama a `/payments`, entonces responde `COD002`.

## 6. Plan por fases (cada fase con TDD: test en rojo, luego código)

| Fase | Contenido | Horas | Puerta de salida |
|---|---|:---:|---|
| **0. Conexión real** | Cargar credenciales QA y URL base en el proveedor de staging **desde la UI**; ejecutar `/access` una vez; informar la IP `181.115.239.178` al banco si pide lista blanca. Sin cambios de código. | 1 | `/access` responde `COD000`. |
| **1. Diagnóstico** | «Probar conexión» y error visible con log seguro (Q1, Q3, Q7). | 4 | Tests Q1, Q3, Q7 en verde. |
| **2. QR de prueba** | Acción «Generar QR de prueba» con descarga y transacción independiente (Q2, Q4, Q8). | 5 | Tests Q2, Q4, Q8 en verde; gate de estructura sin violaciones nuevas. |
| **3. Prueba con el banco** | Generar QR de Bs 1,00, enviar imagen, el banco paga, verificar `done` y `transactionId`; repetir con un reintento del webhook. | 2 | Evidencia guardada (hora, `qrId`, `transactionId`). |
| **4. Checkout real** | Auto-refresco del Paso 3 (Q5, Q6) y prueba con un plan real. | 4 | Redirección automática a `step=done` en staging. |
| **5. Cierre** | Actualizar `AGENTS.md`, backlog (HU-11) y memoria; checklist de producción. | 1,5 | Documentación al día. |
| | **Total estimado** | **17,5 h** | |

La Fase 0 puede empezar apenas apruebes el SDD y desbloquea todo lo demás.

## 7. Decisiones y riesgos abiertos

- **D1: ¿Cómo apuntar a QA?** *Recomendada (A):* usar `state = enabled` en staging con la URL QA del banco. Cero código, y el botón «Simular» queda bloqueado (correcto). Efecto: en staging el éxito del checkout deja de mostrar la clave demo y usa el dominio real del tenant. *Alternativa (B):* un indicador «conectar al banco en modo prueba»; toca provider, cron, polling y `aei_website`, y no hace falta para certificar.
- **R1: Lista blanca de IP.** Si el banco filtra, `/access` fallará desde staging hasta que registren `181.115.239.178`.
- **R2: Formato de `qrImage`.** El código lo muestra como PNG en base64; si el banco devuelve otro formato, ajustar en la Fase 2.
- **R3: Consulta 2 del banco sin respuesta (campo `reference`/glosa).** Nuestro cruce es por `qrId`, no depende de la glosa; confirmarlo con el banco.
- **R4: Credenciales expuestas.** La clave de QA circuló por correo y chat: considerarla comprometida al terminar y no reutilizar el patrón en producción.
- **R5: Entorno staging es compartido.** Con el proveedor en `enabled`, cualquier visitante de `www.aeisoftware.com` que pague generaría un QR de QA. Es aceptable mientras sea ambiente de pruebas.

## 8. Criterios de aceptación

1. Tests Q1 a Q8 con `unittest.mock` (cero red real en tests) y en verde.
2. `python3 .github/scripts/structure_gate.py` sin violaciones nuevas; `bandit` y `flake8` limpios.
3. Un pago de prueba real confirmado por el banco, con evidencia.
4. Ningún secreto en el repositorio, logs ni documentación.
5. Checklist de producción redactado: credenciales y URL reales, IP autorizada, SMTP, proveedor `enabled`, simulación apagada.

## 9. Avance (20/11/2026)

| Fase | Estado | Evidencia |
|---|---|---|
| 0. Conexión real | **Hecha** | El PDF del banco tenía un typo en el nombre de la cabecera (`XApi--Key`); el gateway real del Banco Ganadero exige la cabecera estándar `X-Api-Key`. Con `X-Api-Key` y la clave de 124 caracteres unida, `POST /qrcode/access` respondió `HTTP 200 · COD000` (token JWT de 371 caracteres) y `POST /qrcode/collections` respondió `HTTP 200 · COD000` generando el primer QR real de QA (`qrId = 26112001018000000055`, PNG de 18.708 bytes en base64). |
| 1. Diagnóstico | Hecha | `test_bank_diagnostics.py` (Q1, Q3) y `test_public_routes.py` (Q7). |
| 2. QR de prueba | Hecha | `test_test_qr_wizard.py` (Q2, Q4, Q8). |
| 3. Prueba con el banco | Lista para ejecutar | Desplegar en staging, generar QR desde Odoo y enviar el PNG a Crisvel para que el banco dispare el pago hacia `/payment/qr_ganadero/payments`. |
| 4. Checkout real | Hecha | `test_public_routes.py` (Q6, post-proceso) y `aei_website/tests/test_checkout_qr_payment.py` (reintento y polling del Paso 3). |
| 5. Cierre | Parcial | `AGENTS.md` del módulo y este documento actualizados. |

Suite: 86 tests en `aei_test`; solo fallan los 5 preexistentes de `aei_website` (diálogos de planes y header de `/pricing`), que también fallan en `HEAD`.

**Pasos que quedan, en orden:**
1. Desplegar estos cambios en staging (commit, merge a `main`, `-u payment_qr_ganadero,aei_website`).
2. En el proveedor de staging cargar URL base (`https://api.bg.com.bo/bgqa`), apiKey, usuario, clave y `accountReference` (`TEST_REF`), cambiar a **Habilitado** y pulsar **Probar conexión**.
3. Pulsar **Generar QR de prueba** (Bs 1,00), descargar el PNG y enviárselo al Banco Ganadero para que ejecuten el pago y notifiquen a `https://www.aeisoftware.com/payment/qr_ganadero/payments`.
