# Manual de Reportes

**Producto:** Aei SaaS Starter 19.0
**Fecha:** 2026-08-14
**Versión del manual:** 1.0

---

## Introducción

Este manual describe los reportes contables y de inventario incluidos en **Aei SaaS Starter 19.0**, adaptados a la normativa y práctica contable boliviana: reportes financieros dinámicos, kardex de inventario, libro diario, numeración de comprobantes contables, actualización de tipo de cambio del Banco Central de Bolivia (BCB), y las plantillas de impresión de AEI para documentos comerciales.

---

## Requisitos

- Permisos de grupo **Contabilidad / Contable** o superior para los reportes financieros, el Libro Diario y el Tipo de Comprobante.
- Permisos de grupo **Inventario / Administrador** para el Kardex Físico y el Kardex de Costos.
- Para que el **Kardex de Costos** y otros reportes de valorización muestren datos, las categorías de producto deben tener configurado un **Método de Costeo** (Promedio, FIFO o Estándar) y **Valoración de Inventario** en Tiempo Real o Manual.

---

## Configuración

Los reportes de este manual no requieren configuración adicional más allá de la instalación estándar del producto: se activan automáticamente. La única configuración relevante para el usuario es la de **tipo de cambio automático del BCB**, descrita en su propia sección más abajo.

---

## Uso

### 1. Reportes contables dinámicos

Los reportes financieros dinámicos se encuentran en **Contabilidad → Reportes → Dynamic Financial Reports** (submenú propio de este producto, dentro del menú estándar de Reportes de Odoo). Incluye:

| Reporte (nombre en pantalla) | Equivalente en español |
|---|---|
| General Ledger | Libro Mayor |
| Trial Balance | Balance de Sumas y Saldos |
| Partner Ledger | Mayor de Terceros |
| Cash Book | Libro Caja |
| Balance Sheet | Balance General |
| Income Statement | Estado de Resultados (PyG) |
| Aged Receivable | Antigüedad de Cuentas por Cobrar |
| Aged Payable | Antigüedad de Cuentas por Pagar |
| Tax Report | Reporte de Impuestos |
| Evolution Patrimony | Evolución Patrimonial |

> **Nota:** los nombres de estos reportes aparecen **en inglés** en el menú y dentro de la pantalla del reporte (botones, filtros) en esta versión del producto, aun cuando el resto de Odoo esté en español. No es un error — es el idioma en que están definidos estos reportes en el módulo. La columna "Equivalente en español" de esta tabla es solo para su referencia.

#### Cómo usar cualquiera de estos reportes

1. Vaya a **Contabilidad → Reportes → Dynamic Financial Reports** y elija el reporte deseado.
2. En la parte superior derecha, use el filtro **Date Range** (Rango de Fechas) para acotar el período: puede elegir un rango predefinido (This Month, This Quarter, This Year, Last Month, Last Quarter, Last Year) o ingresar manualmente **Start Date** y **End Date**.
3. Según el reporte, puede haber filtros adicionales (por ejemplo, por diario/Journal).
4. Las cuentas o filas del reporte pueden **expandirse y colapsarse** individualmente haciendo clic sobre ellas; el botón **Unfold All** despliega todas las cuentas de una vez.
5. Use los botones de la parte superior para exportar:
   - **Print (PDF)** — genera un PDF del reporte con los filtros aplicados.
   - **Export (XLSX)** — descarga el mismo reporte en un archivo Excel.

[CAPTURA: pantalla del Libro Mayor (General Ledger) con el filtro de fechas y los botones Print/Export]

[CAPTURA: cuenta expandida (Unfold) mostrando el detalle de apuntes]

⚠️ Por confirmar: en el código de este producto existen también componentes para "Bank Book" (Libro de Banco) y una versión anterior de "Profit and Loss", pero **no están conectados a ningún menú** en esta versión — solo **Cash Book** (Libro Caja) está activo. Si su negocio necesita un Libro de Banco separado, consulte con AEI si está previsto habilitarlo.

**Nota conocida:** algunas entradas de menú de reportes pueden aparecer **duplicadas** en la instancia (por ejemplo, dos accesos a "General Ledger" o a "Libro Diario"). Es un **defecto cosmético conocido**: ambos accesos apuntan al mismo reporte, sin diferencia funcional entre uno u otro.

---

### 2. Kardex Físico y Kardex de Costos (Inventario)

Estos dos reportes viven en **Inventario → Reportes → Reportes Bolivia**:

- **Kardex Físico**: historial cronológico de movimientos de **cantidades** de un producto, con saldo acumulado. Permite filtrar por producto y rango de fechas, y opcionalmente agrupar por ubicación de almacén.
- **Kardex de Costos**: historial de **valorización financiera** del inventario (cantidades, costos unitarios y valores monetarios de entrada/salida/saldo), compatible con Costo Promedio (AVCO), FIFO y Costo Estándar. Permite agrupar por almacén.

Ambos generan salida en **PDF** ("Imprimir PDF") y **Excel** ("Exportar Excel").

Requisito importante: para que el Kardex de Costos muestre valores, el producto debe tener configurado el Método de Costeo y la Valoración de Inventario en su categoría — de lo contrario, el sistema no genera capas de valorización (`stock.valuation.layer`) y el reporte aparece vacío o en ceros.

[CAPTURA: diálogo del Kardex Físico con selección de producto y fechas]

Para el detalle completo de columnas, agrupaciones y preguntas frecuentes de estos dos reportes, consulte el manual del módulo de origen:
`aei-l10n-bo/addons/l10n_bo_stock_reports/MANUAL.md`.

---

### 3. Libro Diario

El **Libro Diario** presenta los asientos contables en orden cronológico agrupados por fecha, con totales de Debe y Haber.

1. Vaya a **Contabilidad → Reportes → Reportes → Libro Diario**.

   (Sí, el nombre "Reportes" aparece repetido en la ruta del menú — es la misma duplicación cosmética mencionada arriba, no un error de este manual.)

2. En el wizard, configure:

   | Campo | Descripción | Obligatorio |
   |---|---|:---:|
   | Fecha Inicio / Fecha Fin | Rango del período a reportar | Sí |
   | Movimientos | Publicados / Todos los Asientos | Sí |
   | Tipo de Comprobante | Filtrar por Ingreso, Egreso, Traspaso, Op. Varias o Todos | No |
   | Diarios | Filtrar por diarios específicos (vacío = todos) | No |

3. Genere el reporte con **Imprimir PDF** o **Exportar Excel**.

El PDF muestra en su cabecera el nombre, dirección, departamento y país de la empresa (izquierda), el título y rango de fechas (centro), y el NIT de la empresa (derecha).

[CAPTURA: Libro Diario en PDF, con la cabecera de la empresa visible]

---

### 4. Tipo de Comprobante (ING / EGR / TRA / OPV)

Este producto numera automáticamente los asientos contables según su tipo, con cuatro secuencias:

| Prefijo | Tipo de Comprobante |
|---|---|
| **ING-** | Ingreso |
| **EGR-** | Egreso |
| **TRA-** | Traspaso (valor por defecto en asientos manuales) |
| **OPV-** | Operaciones Varias |

**Cómo se asigna:**

- En un **asiento manual** (**Contabilidad → Contabilidad → Asientos contables**), el campo **Tipo de Comprobante** aparece en la cabecera del formulario; selecciónelo antes de confirmar el asiento.
- En **facturas de venta** y notas de crédito/débito de cliente, el sistema asigna **Ingreso** automáticamente.
- En **facturas de compra** y notas de crédito/débito de proveedor, el sistema asigna **Egreso** automáticamente.
- Al **confirmar** el asiento, el sistema genera el **Nro. Comprobante** (por ejemplo, `ING-0001`).

> Los asientos que ya existían antes de instalar este producto **no** reciben numeración retroactiva; solo los asientos confirmados después de la instalación.

**Dónde verlo:** las columnas **Tipo Comp.** y **Nro. Comp.** aparecen automáticamente en el reporte **Libro Mayor** (General Ledger), justo después de la columna de Fecha.

**Administrar las secuencias:** en **Ajustes → Técnico → Secuencias e Identificadores → Secuencias**, busque "Comprobante de Ingreso", "Comprobante de Egreso", "Comprobante de Traspaso" o "Comprobante de Operaciones Varias" para ajustar el número actual, prefijo o padding.

[CAPTURA: campo Tipo de Comprobante en la cabecera de un asiento contable]

---

### 5. Actualización automática del tipo de cambio (BCB)

Este producto mantiene actualizadas las tasas de cambio (USD, UFV y otras monedas habilitadas) usando el servicio oficial del **Banco Central de Bolivia (BCB)**.

#### Actualización automática (diaria)

Todos los días, aproximadamente a las **00:05 hora Bolivia**, el sistema consulta al BCB y actualiza automáticamente las tasas de las monedas habilitadas para este mecanismo (por defecto: **USD** y **UFV**, además de otras monedas que AEI pueda habilitar). No requiere ninguna acción de su parte.

#### Actualización manual (por rango de fechas)

Si necesita forzar una actualización o completar tasas de un período pasado:

1. Vaya a **Ajustes → Contabilidad → Monedas** (o **Contabilidad → Configuración → Monedas**).
2. Abra la moneda que desea actualizar (por ejemplo, **USD** o **UFV**).
3. Haga clic en el botón **Actualizar desde BCB** (solo visible en monedas habilitadas para este mecanismo).
4. En el wizard, complete:
   - **Fecha de inicio**
   - **Fecha final** (por defecto, hoy)
   - **Forzar actualización**: actívela si quiere sobrescribir una tasa que ya tiene un valor para esa fecha.
5. Haga clic en **Actualizar**.

La respuesta del BCB para la última actualización queda visible en la pestaña **"Respuesta del BCB"** del formulario de la moneda.

[CAPTURA: formulario de moneda USD con el botón "Actualizar desde BCB"]

[CAPTURA: wizard de actualización con Fecha de inicio, Fecha final y Forzar actualización]

---

### 6. Plantillas de impresión AEI

Este producto incluye plantillas de impresión personalizadas para tres documentos comerciales frecuentes:

| Documento | Dónde se imprime | Nombre de la plantilla |
|---|---|---|
| Cotización / Orden de venta | **Ventas → Cotizaciones** (o pedidos de venta) → botón Imprimir | Cotización/Órden de venta |
| Orden de entrega | **Inventario → Transferencias** → botón Imprimir | Órden de entrega |
| Recibo de Ingreso/Pago | **Contabilidad → Pagos** → botón Imprimir | Recibo de Ingreso/Pago |

Estas plantillas reemplazan (o coexisten con) los reportes estándar de Odoo, con el formato y estilo propios de AEI.

[CAPTURA: PDF de una Cotización con la plantilla AEI]

---

## Errores frecuentes

| Problema | Causa probable | Solución |
|---|---|---|
| El Kardex de Costos muestra saldos pero sin filas de detalle | Todos los movimientos están fuera del rango de fechas seleccionado | Ampliar el rango de fechas para incluir las fechas de los movimientos |
| El Kardex de Costos muestra 0.00 en todo | La categoría del producto no tiene Valoración de Inventario en Tiempo Real, o no tiene Método de Costeo asignado | Configurar ambos campos en la categoría del producto |
| Un reporte de Inventario no muestra movimientos | El rango de fechas no coincide con las fechas reales de los movimientos, o los movimientos no están en estado "Hecho" | Verificar el rango de fechas y que los movimientos estén confirmados/validados |
| Aparecen dos entradas de menú para el mismo reporte | Defecto cosmético conocido (ver nota en la sección de reportes dinámicos) | Use cualquiera de las dos; el resultado es idéntico |
| Un asiento antiguo no tiene Nro. Comprobante | El asiento se confirmó antes de instalar este producto | Es un comportamiento esperado; solo los asientos confirmados después de la instalación reciben numeración |
| El botón "Actualizar desde BCB" no aparece en una moneda | Esa moneda no está habilitada para actualización automática del BCB | Consultar con AEI si esa moneda debe habilitarse |

---

## FAQ

**¿Por qué los reportes financieros dinámicos aparecen en inglés?**
Es el idioma en el que están definidos los textos de esos reportes (título, filtros, botones) en esta versión del producto. El resto de la interfaz de Odoo permanece en español.

**¿Puedo comparar dos períodos en el mismo reporte?**
Los filtros de fecha permiten elegir un solo rango a la vez (mes, trimestre, año o fechas personalizadas). Para comparar dos períodos, genere el reporte dos veces con rangos distintos.

**¿El Libro Diario y el Tipo de Comprobante son lo mismo?**
No. El **Tipo de Comprobante** es la clasificación (Ingreso/Egreso/Traspaso/Operaciones Varias) y numeración que se asigna a cada asiento al confirmarlo. El **Libro Diario** es un reporte que lista los asientos contables cronológicamente y puede filtrarse, entre otras cosas, por ese mismo Tipo de Comprobante.

**¿Qué pasa si la actualización automática del BCB falla un día (por ejemplo, el BCB no responde)?**
El mecanismo está diseñado para fallar de forma silenciosa ese día (sin bloquear otras operaciones de Odoo) y reintentar en la siguiente ejecución diaria. Si necesita la tasa de una fecha específica que no se actualizó, use la actualización manual por rango de fechas.

**¿Las plantillas de impresión AEI se pueden desactivar para volver a las plantillas estándar de Odoo?**
⚠️ Por confirmar: no se validó en este producto si existe una opción de usuario para alternar entre la plantilla AEI y la plantilla estándar de Odoo, o si el reemplazo es permanente mientras el módulo esté instalado.
