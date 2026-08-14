# Manual de Usuario — AEI Assistant

**Producto:** Aei SaaS Starter 19.0
**Fecha:** 2026-08-14
**Versión:** 1.0

## Introducción

**AEI Assistant** es el asistente de inteligencia artificial que viene incluido en su sistema
Odoo. Funciona como una conversación normal dentro de **Conversaciones (Discuss)** — el mismo
lugar donde chatea con sus compañeros de equipo — y puede responder preguntas sobre los datos de
su propio Odoo: ventas, inventario, contactos, facturas, y en general cualquier información a la
que usted mismo tenga acceso dentro del sistema.

AEI Assistant viene **instalado de fábrica** en todas las instancias Aei SaaS Starter 19.0, sin
costo adicional de la plataforma. Usted paga únicamente por el uso de su propia clave de IA
(ver sección "Configurar su propia API key" más abajo) — AEI Software nunca ve ni cobra por ese
consumo.

## Requisitos Previos

- Ser **usuario interno** de Odoo (no un usuario de portal/cliente externo).
- Haber iniciado sesión al menos una vez en su instancia.
- Para uso continuo sin límites: una **API key propia** de un proveedor de IA compatible (ver
  sección de configuración). Sin esto, el asistente funciona igual pero con un crédito de
  prueba limitado (ver más abajo).

## Uso Paso a Paso

### 1. Abrir el asistente

Hay dos formas de acceder a AEI Assistant:

**a) Saludo automático en su primer ingreso.** La primera vez que un usuario inicia sesión en la
instancia, AEI Assistant se anuncia solo: aparece un mensaje de bienvenida en Conversaciones
(Discuss), sin que usted tenga que abrir nada. Esto ocurre una sola vez por usuario.

[CAPTURA: mensaje de bienvenida de AEI Assistant en Discuss]

**b) Menú "AEI Assistant".** En cualquier momento puede abrir el chat desde el menú
**AEI Assistant**, visible en la grilla de aplicaciones (ícono de cuadrícula, arriba a la
izquierda).

[CAPTURA: menú AEI Assistant en la grilla de aplicaciones]

### 2. Conversar con el asistente

Escriba su pregunta o pedido como si le escribiera a una persona, por ejemplo:

- "¿Cuántas facturas tengo pendientes de cobro este mes?"
- "Dame un resumen de los productos con menos de 5 unidades en stock."
- "¿Quién es el contacto principal del cliente Acme Corp?"

El asistente responde consultando los datos de su Odoo, **siempre dentro de los mismos permisos
que tiene el usuario que le escribe**. Es decir: si usted no tiene acceso a ver, por ejemplo,
los sueldos de Recursos Humanos, el asistente tampoco podrá mostrárselos.

### 3. Qué puede hacer

- Consultar y responder preguntas sobre los datos de su Odoo (ventas, inventario, contactos,
  contabilidad, etc.), respetando sus permisos de usuario.
- Responder preguntas generales sobre cómo usar el sistema.

### 4. Qué NO puede hacer

Por diseño, y **sin excepción**, AEI Assistant tiene bloqueado:

- **Crear o modificar usuarios** (altas, bajas, cambios de permisos).
- **Instalar, actualizar o desinstalar aplicaciones/módulos.**

Estas acciones están bloqueadas a nivel del propio sistema, no dependen de lo que usted le pida
al asistente: aunque se lo solicite explícitamente, el asistente rechazará la acción.

### 5. Crédito de prueba (trial)

Si todavía no configuró su propia API key, AEI Assistant funciona igual usando una clave de
prueba de AEI Software, con un **tope de gasto en dólares (USD)**. Este tope es configurable por
usted (por defecto, un monto pequeño pensado solo para probar el asistente y llegar a configurar
su propia clave).

Puede ver cuánto lleva consumido del crédito de prueba en **Ajustes → Ajustes Generales →
AEI Assistant**, sección "Trial (no key yet)": muestra "Usado hasta ahora" sobre el total del
tope, en USD. Esta sección desaparece automáticamente en cuanto usted configura su propia API
key.

[CAPTURA: sección Trial en Ajustes → Ajustes Generales → AEI Assistant]

### 6. Configurar su propia API key

1. Vaya a **Ajustes → Ajustes Generales**.
2. Busque la sección **AEI Assistant**.
3. Complete:

   | Campo | Descripción |
   |---|---|
   | Proveedor de IA | `Anthropic (Claude)`, `DeepSeek`, `Moonshot / Kimi`, o `Custom / self-hosted (Ollama, ...)` |
   | Endpoint URL | Solo si eligió `Custom / self-hosted`: la URL de su propio servidor |
   | API Key | Su clave propia del proveedor elegido |
   | Modelo | Opcional — déjelo vacío para usar el modelo por defecto del proveedor |

   [CAPTURA: formulario Ajustes → Ajustes Generales → AEI Assistant]

4. Guarde los cambios.

El cambio aplica **desde el siguiente mensaje que envíe al asistente** — no necesita reiniciar
ni esperar nada.

> AEI Software nunca ve ni paga por el uso de su clave: el consumo se factura directamente entre
> usted y el proveedor de IA que eligió.

### 7. Solución de problemas

**El asistente no responde:**

1. Verifique que su API key esté correctamente escrita en **Ajustes → Ajustes Generales →
   AEI Assistant** (sin espacios de más, copiada completa).
2. Confirme que eligió el **Proveedor** correcto para la clave que está usando.
3. Si eligió `Custom / self-hosted`, confirme que la **Endpoint URL** es correcta y accesible.

> ⚠️ **Nota honesta:** hoy en día, si la API key es inválida, el asistente simplemente **no
> responde** — no muestra ningún mensaje de error explicando el problema. Si el asistente queda
> en silencio, lo primero que debe revisar es que la clave configurada sea correcta.

Si después de revisar la clave el asistente sigue sin responder, contacte a soporte a través de
su Portal del Cliente.

## Preguntas Frecuentes

**P: ¿AEI Assistant tiene un costo adicional en mi plan?**
R: No, el asistente en sí no tiene costo de plataforma. Lo único que usted paga es el consumo de
su propia API key ante el proveedor de IA que elija (Anthropic, DeepSeek, Moonshot/Kimi, o su
propio servidor).

**P: ¿Puede el asistente ver datos que yo no tengo permiso de ver?**
R: No. Cada respuesta se genera con los mismos permisos del usuario que escribe, nunca como
superusuario.

**P: ¿Puedo pedirle al asistente que instale una app o cree un usuario?**
R: Puede pedírselo, pero la acción será rechazada. Estas dos operaciones están bloqueadas por
diseño, sin excepciones.

**P: Se me acabó el crédito de prueba, ¿qué pasa?**
R: Configure su propia API key en **Ajustes → Ajustes Generales → AEI Assistant** (sección 6).
Sin una clave propia y sin crédito de prueba disponible, el asistente no podrá responder.

**P: ¿Dónde veo el historial de conversación con el asistente?**
R: Igual que cualquier conversación de Discuss: queda guardada en el canal donde conversó con
"AEI Assistant".
