# Manual de Facturación Electrónica SIAT

**Producto:** Aei SaaS Starter 19.0
**Fecha:** 2026-08-14
**Versión del manual:** 1.0

---

## Introducción

Este manual explica cómo configurar y usar la **facturación electrónica** de Bolivia (SIAT) dentro de su instancia de **Aei SaaS Starter 19.0**, construida sobre Odoo 19.

Con esta funcionalidad usted puede emitir **Facturas Comerciales de Venta (FCV)** electrónicas directamente desde una factura de cliente confirmada en Odoo, obtener el **CUF** (Código Único de Facturación) que exige el Servicio de Impuestos Nacionales (SIN), y anular una factura emitida si fuera necesario.

El flujo descrito en este manual fue **validado de punta a punta** en un ambiente PILOTO del SIN, con emisión real y CUF obtenido.

### Cómo funciona por detrás

Odoo **no se comunica directamente con el SIN**. El módulo de facturación electrónica delega en un servicio propio de AEI (llamado internamente **SBA**), que recibe los datos de la factura desde Odoo, los firma y dialoga con los sistemas del SIN en su nombre. La URL de ese servicio la configura AEI durante el alta de su empresa — usted no necesita conocerla ni administrarla. El ambiente en el que se emiten sus facturas (**PILOTO** de pruebas o **producción** real) y las credenciales de firma también las administra AEI por cada emisor, fuera de Odoo.

En términos prácticos, esto significa que si usted ve un error de comunicación con el servicio de facturación electrónica, casi siempre es un tema de **configuración incompleta en Odoo** (los campos que se explican en este manual) — no algo que usted deba resolver contactando al SIN.

---

## Requisitos

Antes de emitir su primera factura electrónica, verifique que cuenta con lo siguiente:

- Su empresa debe estar **registrada como emisor en el sistema de facturación electrónica del SIN**, con al menos una **actividad económica** y un **código de modalidad** (Electrónica o Computarizada) asignados por el SIN.
- AEI debe haber configurado la **URL del servicio** de facturación electrónica para su instancia (ver sección de Configuración).
- El **catálogo de productos del SIN** para su NIT y actividad debe incluir los productos/servicios que usted factura. Si un producto no está en ese catálogo, primero debe registrarse ante el SIN.
- Permisos de usuario: rol de **Contabilidad / Facturación** o superior para configurar; cualquier usuario con acceso a **Facturación** puede emitir una vez que la configuración está lista.

⚠️ Por confirmar: el nombre exacto del grupo de seguridad que AEI asigna por defecto a los usuarios de facturación en el producto Aei SaaS Starter puede variar según el plan contratado.

---

## Configuración

Esta sección se hace **una sola vez** por instancia (los pasos 1 y 2), y una vez por diario/producto/cliente nuevo que use facturación electrónica (pasos 3 a 5).

### 1. Ajustes generales de facturación electrónica

1. Vaya a **Ajustes → Ajustes Generales**.
2. Ubique la sección **Facturación Electrónica**.
3. Complete los siguientes campos:

   | Campo | Descripción |
   |---|---|
   | **URL del Servicio** | Dirección del servicio de facturación electrónica de AEI. La configura AEI durante el alta de su empresa — normalmente no debe modificarla usted mismo. |
   | **Código de modalidad** | La modalidad de facturación registrada para su NIT ante el SIN: **1 = Electrónica**, **2 = Computarizada**. Debe coincidir con lo que el SIN tiene registrado para usted; si no coincide, el SIN rechaza el documento. |
   | **Tipo de Facturación** | Normalmente **1 = Factura con Derecho a Crédito Fiscal** (la opción estándar para la mayoría de las empresas). |
   | **Documento Tributario** | El tipo de documento que emite: en este producto, **FCV — Factura Comercial de Venta**. |
   | **Tipo de Documento Interno** | Identificador interno del tipo de comprobante (por defecto, Factura — "FAC"). |

4. Guarde los cambios.

[CAPTURA: pantalla de Ajustes Generales, sección Facturación Electrónica]

### 2. Datos de la compañía

El SIN exige que los datos fiscales de su empresa estén completos antes de poder emitir cualquier factura.

1. Vaya a **Ajustes → Empresas → [su compañía]** (o **Ajustes → Ajustes Generales → Empresas → Actualizar Información**).
2. Verifique que estén completos:
   - **NIT** (campo "NIF/VAT" del formulario de compañía).
   - **Razón social** (nombre de la compañía).
   - **Ciudad** / **Municipio**.
   - **Dirección**.
   - **Teléfono**.
3. Guarde los cambios.

Estos cuatro datos (NIT, ciudad/municipio, dirección, teléfono) son obligatorios: si falta alguno, el sistema le impedirá emitir facturas y se lo indicará con un mensaje de error específico (ver la tabla de errores frecuentes).

[CAPTURA: formulario de datos de la compañía con NIT, dirección y teléfono resaltados]

### 3. Sucursal y Punto de Venta

1. Vaya a **Contabilidad → Configuración → Facturación electrónica**.
2. Cree (o revise) la **Sucursal**:
   - Si su empresa opera desde una sola sede (casa matriz), use **código 0**.
3. Cree (o revise) el **Punto de Venta**:
   - Para el punto de venta principal, use **código 0**.

Estos códigos deben coincidir con los que el SIN tiene registrados para su empresa. Si su negocio tiene varias sucursales o puntos de venta, cada uno debe registrarse primero ante el SIN y luego darse de alta aquí con el mismo código.

[CAPTURA: menú Contabilidad → Configuración → Facturación electrónica, con Sucursales y Puntos de Venta]

### 4. Diario de ventas

1. Vaya a **Contabilidad → Configuración → Diarios**.
2. Abra el diario de tipo **Ventas** que usará para facturar (por ejemplo, "Facturas de Clientes").
3. Abra la pestaña **Facturación Electrónica** y complete:

   | Campo | Descripción |
   |---|---|
   | **Sucursal** | La sucursal SIAT creada en el paso 3. |
   | **Punto de Venta** | El punto de venta SIAT creado en el paso 3. |
   | **Ciudad** | Departamento/ciudad donde opera este diario. |
   | **Zona** | Zona geográfica de la dirección de facturación. |
   | **Teléfono** | Teléfono de contacto para este punto de facturación. |
   | **Dirección** | Dirección física de facturación. |
   | **Método de pago** (por defecto) | Método de pago habitual, por ejemplo **1 = EFECTIVO**. Solo aplica a diarios de banco/caja. |
   | **Actividad Económica** | El código de actividad económica **hoja** (el más específico) registrado en el SIN para su NIT — por ejemplo `4530000`, no el código padre `453000`. |
   | **Tipo de Facturación** | Heredado de Ajustes; visible aquí como referencia. |
   | **Documento Tributario** | Heredado de Ajustes; visible aquí como referencia. |
   | **Tipo de Documento Interno** | Heredado de Ajustes; visible aquí como referencia. |

4. El check **"Deshabilitar para SIAT"** (campo "Estado SIAT" desmarcado) apaga la emisión electrónica para ese diario en particular — útil si tiene un diario de pruebas o uno que no debe emitir al SIN.
5. Guarde los cambios.

⚠️ Por confirmar: si "Deshabilitar para SIAT" está activo por defecto en diarios nuevos o si hay que activarlo manualmente — verifíquelo en su instancia antes de facturar.

[CAPTURA: pestaña Facturación Electrónica del diario de ventas]

### 5. Productos

1. Vaya a **Inventario → Configuración → Categorías de Producto** (o **Ventas → Productos → Categorías de producto**).
2. Abra la categoría del producto que va a facturar.
3. Complete:
   - **Código de Producto SIN**: el código del catálogo de productos que el SIN registró para su NIT y actividad. Si el producto que busca no aparece en la lista, primero debe darse de alta en el SIN con ese código.
   - **Actividad Económica**: la actividad SIAT asociada a los productos de esta categoría.
4. La búsqueda de estos dos datos es **recursiva**: si el producto no tiene una categoría propia con código SIN o actividad, el sistema busca en la **categoría padre**. Esto le permite configurar el código una sola vez en una categoría general y que todos los productos hijos lo hereden.
5. Adicionalmente, cada **unidad de medida** usada por sus productos necesita su código SIAT correspondiente (por ejemplo, **57 = UNIDAD (BIENES)** para productos vendidos por unidad). Esto se revisa en **Inventario → Configuración → Unidades de Medida**.

[CAPTURA: formulario de categoría de producto con Código de Producto SIN y Actividad Económica]

### 6. Clientes

1. Vaya a **Contactos** y abra (o cree) el cliente.
2. Abra la pestaña **Facturación electrónica** y complete:
   - **Razón Social**: nombre legal completo del cliente (puede diferir del nombre comercial del contacto).
   - **Tipo de documento**: **1 = CI**, **5 = NIT**, y otras opciones (CEX, PAS, OD) según el tipo de identificación del cliente.
   - **NIT** (campo "NIT" del formulario): el número de documento correspondiente al tipo elegido.
   - **Complemento**: si el NIT tiene complemento (dígito o letra adicional), regístrelo aquí.
3. Haga clic en **Verificar NIT** para consultar el dato contra los registros del SIN. El resultado se muestra debajo del botón.

Recomendación: verifique el NIT de un cliente **antes** de facturarle por primera vez, para evitar rechazos del SIN al momento de emitir.

[CAPTURA: pestaña Facturación electrónica del contacto, con el botón Verificar NIT]

---

## Uso

### Emitir una factura electrónica

1. Cree y confirme una **factura de cliente** normalmente: **Contabilidad → Clientes → Facturas → Crear**, agregue las líneas de producto y haga clic en **Confirmar**.
2. Una vez que la factura está en estado **Publicado**, aparece el botón **Generar factura SIAT**.
3. Haga clic en **Generar factura SIAT**.
4. Si toda la configuración está completa, el sistema:
   - Envía la factura al servicio de AEI, que la firma y la transmite al SIN.
   - Recibe de vuelta el **CUF** y actualiza el estado de la factura a **VÁLIDO**.
5. El estado se muestra como una insignia en la parte superior de la factura (**VÁLIDO** en verde).

**Sobre el IVA:** siguiendo la convención boliviana, el **13% de IVA va incluido en el precio** que usted configura en sus productos — no se agrega como un cargo aparte al momento de facturar.

[CAPTURA: factura confirmada con el botón "Generar factura SIAT" visible]

[CAPTURA: factura con estado VÁLIDO y CUF visible tras la emisión]

### Anular una factura

1. Abra la factura ya emitida (estado VÁLIDO).
2. Haga clic en **Anular factura SIAT**.
3. Ingrese el **motivo de anulación** cuando el sistema lo solicite.
4. Confirme. El estado cambia a **ANULADO**.

### Revertir una anulación

Si anuló una factura por error, dentro de las condiciones que permite el SIN puede revertir la anulación:

1. Abra la factura en estado **ANULADO**.
2. Haga clic en **Revertir Anulación**.
3. El sistema confirma la reversión contra el servicio de AEI y el estado vuelve a **VÁLIDO**.

### Generar varias facturas SIAT a la vez

Si tiene varias facturas ya **pagadas** pendientes de emitir al SIN, puede procesarlas en lote:

1. Vaya a la lista de **Facturas de Clientes**.
2. Seleccione las facturas que desea emitir.
3. En el menú de acciones, elija **Generar Facturas SIAT**.
4. El sistema procesa únicamente las facturas que están **pagadas** y que **aún no tienen** una emisión SIAT generada; el resto de la selección se omite sin error.

[CAPTURA: acción "Generar Facturas SIAT" desde la vista de lista de facturas]

---

## ⚠️ Limitaciones actuales

Sea honesto con sus usuarios sobre estas limitaciones conocidas de la versión actual del producto:

- **Punto de Venta (POS):** en esta versión, el POS **no captura los datos fiscales del cliente** (NIT, razón social, tipo de documento) al cerrar una venta. Si necesita facturar electrónicamente ventas de mostrador, hágalo desde una factura de cliente convencional en Contabilidad, no desde el POS.
- **Nota de Crédito-Débito:** la emisión electrónica de Notas de Crédito-Débito **aún no está disponible** en este producto. Las devoluciones o ajustes deben gestionarse por otros medios mientras esta funcionalidad se completa.
- **Descarga de PDF/XML:** según cómo esté configurado el servicio de facturación electrónica para su instancia, los botones de descarga del PDF/XML generados por el SIAT pueden no estar disponibles. Consulte con AEI si necesita esta funcionalidad habilitada.

---

## Errores frecuentes

La mayoría de los errores al emitir son de **configuración incompleta**, no de comunicación con el SIN. La siguiente tabla resume los mensajes más comunes:

| Mensaje de error | Causa | Solución |
|---|---|---|
| "El Documento Tributario no está configurado" | Falta el parámetro global en Ajustes | Ir a **Ajustes → Ajustes Generales → Facturación Electrónica** y completar Documento Tributario |
| "El Tipo de Facturacion no está configurado" | Falta el parámetro global en Ajustes | Completar **Tipo de Facturación** en Ajustes Generales |
| "El Tipo de Documento Interno no está configurado" | Falta el parámetro global en Ajustes | Completar **Tipo de Documento Interno** en Ajustes Generales |
| "El Código de modalidad de factura no está configurado" | Falta el parámetro global en Ajustes | Completar **Código de modalidad** en Ajustes Generales |
| "El campo 'Municipio' de la Compañía está vacío" | Falta la ciudad/municipio en los datos de la empresa | Ir a **Ajustes → Empresas** y completar la ciudad |
| "El campo 'Ciudad' del Diario está vacío" | Falta la ciudad en el diario de ventas | Ir a **Contabilidad → Configuración → Diarios**, pestaña Facturación Electrónica |
| "La 'Dirección' está vacía" | Falta la dirección en el diario o en la compañía | Completarla en el Diario o en Ajustes → Empresas |
| "El 'Teléfono' está vacío" | Falta el teléfono en el diario o en la compañía | Completarlo en el Diario o en Ajustes → Empresas |
| "El producto '...' no tiene Actividad Económica SIAT configurada..." | La categoría del producto (ni sus categorías padre) tiene actividad, y el diario tampoco tiene una actividad de respaldo | Configurar la **Actividad Económica** en la categoría del producto, o en el diario de ventas |
| "El producto '...' no tiene Código de Producto SIN configurado..." | La categoría del producto (ni sus categorías padre) tiene código SIN | Configurar el **Código de Producto SIN** en la categoría del producto |
| "No hay archivo PDF/XML disponible para descargar" | La factura aún no fue generada en el SIAT, o la descarga no está habilitada para su instancia | Generar primero la factura con el botón "Generar factura SIAT"; si el problema persiste, consultar con AEI |
| "No existe un CUF para revertir la anulación" | Se intentó revertir una anulación sobre una factura sin CUF asignado | Verificar que la factura efectivamente fue anulada con un CUF previo |

---

## FAQ

**¿Por qué el botón "Generar factura SIAT" no aparece?**
El botón solo se muestra cuando la factura está en estado **Publicado** (confirmada) y aún no tiene una emisión SIAT generada. Si la factura está en borrador, confírmela primero.

**¿Puedo emitir una factura en dólares (USD)?**
Sí, el módulo soporta facturación en moneda extranjera. El sistema calcula automáticamente el monto equivalente en bolivianos usando la tasa de cambio vigente de la factura, ya que el SIN exige los montos también en bolivianos.

**¿Qué pasa si mi NIT no verifica correctamente con el botón "Verificar NIT"?**
Revise que el número y el tipo de documento coincidan exactamente con el registro del SIN. Si el cliente es extranjero o tiene una situación especial, use el tipo de documento correspondiente (CEX, PAS, OD) en lugar de NIT/CI.

**¿La factura generada tiene validez legal inmediatamente?**
Sí, una vez que el estado cambia a **VÁLIDO** y se muestra el CUF, la factura ya fue aceptada por el SIN en el ambiente configurado para su emisor (PILOTO o producción, según lo que AEI haya habilitado para usted).

**¿Cómo sé si estoy en ambiente PILOTO o en producción?**
Ese ambiente lo administra AEI por cada emisor, fuera de Odoo. Si tiene dudas sobre en qué ambiente está emitiendo, consulte con AEI antes de facturar operaciones reales.

**¿Puedo tener más de un punto de venta o sucursal?**
Sí. Cada sucursal y punto de venta adicional debe registrarse primero ante el SIN, y luego darse de alta en **Contabilidad → Configuración → Facturación electrónica** con el mismo código que le asignó el SIN.

⚠️ Por confirmar: comportamiento exacto de la acción masiva "Generar Facturas SIAT" cuando alguna de las facturas seleccionadas falla por configuración incompleta (si detiene el lote completo o solo omite esa factura) — no se validó explícitamente en las pruebas realizadas.
