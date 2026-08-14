# Manual de Nómina Boliviana

**Producto:** Aei SaaS Starter 19.0 — módulo `l10n_bo_payroll_bolivia_base`
**Fecha:** 2026-08-14
**Versión del manual:** 1.0

---

## Introducción

Este manual explica cómo usar el módulo de **Nómina Boliviana** dentro de su instancia de **Aei SaaS Starter 19.0** (Odoo 19). Con él usted puede administrar contratos, calcular boletas de sueldo mensuales conforme a la normativa boliviana (AFP, RC-IVA, aporte patronal), gestionar anticipos, préstamos, aguinaldo, vacaciones y liquidaciones, y exportar la Planilla de Sueldos y Salarios que exige el Ministerio de Trabajo (MTSS).

Está dirigido a la persona de **Contabilidad / Recursos Humanos** que procesa la planilla cada mes. No requiere conocimientos técnicos de Odoo, solo los conceptos contables/laborales habituales.

Todas las funciones descritas cuelgan de un único menú: **Nómina Bolivia**. No se debe confundir con el módulo "Nómina" estándar de Odoo Enterprise — este producto no lo usa ni lo instala; todo el cálculo vive en `l10n_bo_payroll_bolivia_base`.

> ✅ **Nota de la versión actual:** los totalizadores de la boleta (**Total Ganado**, **Total Deducciones** y **Líquido Pagable**) fueron corregidos el 13 de agosto de 2026. Antes de esa fecha podían mostrar **0.0** sin importar los datos cargados, por un problema interno de categorización de las reglas de cálculo. Si su instancia se aprovisionó después de esa fecha, este problema ya no aplica.

[CAPTURA: menú Nómina Bolivia desplegado, con todos sus submenús visibles]

---

## Estructura del menú Nómina Bolivia

```
Nómina Bolivia                          (abre directamente la lista de empleados)
├── Vacaciones
│   └── Resumen
├── Gestión de Trabajadores
│   ├── Desvinculaciones
│   ├── Afectaciones Salariales
│   ├── Aguinaldo
│   ├── Liquidaciones
│   ├── Anticipo
│   └── Préstamo
├── Lotes de recibos de sueldo
│   ├── Listado
│   └── Exportar Planilla MTSS
├── Recibos de sueldo
└── Configuración
    ├── Parámetros de Cálculo
    ├── Categorías de Reglas
    ├── Reglas salariales
    └── Estructuras Salariales
```

---

## 1. Crear un empleado y su contrato

1. Vaya a **Nómina Bolivia** (menú raíz) — se abre la lista de empleados, con columnas de Contrato y Salario mensual. También puede llegar al mismo formulario desde la app estándar **Empleados**.
2. Abra un empleado existente o cree uno nuevo con los datos generales habituales de Odoo (nombre, cargo, departamento, etc.).
3. Abra la pestaña **Nómina Boliviana** y complete:

   | Campo | Descripción |
   |---|---|
   | **Fecha de Inicio** | Fecha de inicio del contrato. **Requerido.** |
   | **Fecha de Finalización** | Solo para contratos a plazo fijo. |
   | **Tipo de Contrato** | Indefinido / Plazo fijo / Eventual / Práctica. |
   | **Salario Nómina** | Salario mensual base del empleado, sobre el que se calculan todas las reglas (AFP, aguinaldo, indemnización, etc.). |
   | **Jornada** | Completa / Medio tiempo / Turnos. |
   | **Modalidad** | Presencial / Híbrido / Remoto. |
   | **Estructura Salarial** | Opcional — ver sección 2. |

   ⚠️ **Atención con el nombre del campo:** en el contrato interno este mismo salario aparece etiquetado como "Salario Neto Mensual", aunque en la práctica es el **salario base** que alimenta todas las fórmulas (no es el líquido pagable final — ese resultado se calcula aparte en cada boleta, ver sección 3). Trátelo siempre como el salario base mensual acordado con el empleado, no como el monto que el empleado recibe en mano.

4. El **Sueldo por día** se calcula automáticamente como **Salario Nómina ÷ 30** (siempre 30, no los días reales del mes en curso). Este valor alimenta el cálculo del Haber Básico de cada boleta.
5. Guarde. El sistema crea o actualiza el registro de contrato asociado y muestra su **Estado** (Nuevo / En Proceso / Vencido / Terminado / Cancelado), calculado automáticamente según las fechas.

[CAPTURA: pestaña "Nómina Boliviana" del formulario de empleado]

---

## 2. Estructura salarial (opcional)

Menú: **Nómina Bolivia → Configuración → Estructuras Salariales**

Una estructura salarial es simplemente un **nombre + una lista de reglas salariales** que quiere permitir para un grupo de empleados (por ejemplo, una estructura reducida para personal a medio tiempo que no debe recibir ciertos bonos).

- Si el contrato de un empleado **no tiene** estructura asignada, el sistema aplica **todas las reglas salariales activas** al calcular su boleta.
- Si el contrato **sí tiene** una estructura asignada, solo se aplican las reglas incluidas en esa estructura.

No es necesario crear una estructura para que la nómina funcione; es una herramienta para limitar qué conceptos aplican a ciertos empleados.

[CAPTURA: formulario de Estructura Salarial con su lista de reglas incluidas]

---

## 3. Generar una boleta individual

Menú: **Nómina Bolivia → Recibos de sueldo → Crear**

1. Complete **Empleado**, **Contrato**, y el **período** (fecha de inicio y fecha de fin).
2. Haga clic en **Recalcular**. El sistema recorre, en este orden: cuotas de préstamo pendientes, anticipos aprobados, afectaciones salariales aprobadas, y las reglas de la estructura salarial (o todas las reglas activas si el contrato no tiene estructura) — y genera las líneas de la boleta.
3. Revise las líneas generadas. Las más relevantes para validar antes de confirmar:

   | Línea | Qué representa |
   |---|---|
   | **Básico** | Haber Básico = Sueldo por día × días trabajados del período. |
   | **AFP 12,71%** | Aporte laboral obligatorio a la AFP (deducción). |
   | **Total Ganado** | Suma de todos los haberes (Básico + bonos + horas extra, etc.). |
   | **Total Deducciones** | Suma de todas las deducciones (AFP, RC-IVA, anticipos, préstamos, etc. — se muestra en negativo). |
   | **Líquido Pagable** | El monto final que el empleado recibe: Total Ganado + Total Deducciones. |

   El detalle de la fórmula de cada regla (incluidas las 22 reglas predefinidas del sistema, con sus códigos exactos) está documentado en el anexo **REGLAS.md** del módulo — ver sección "Anexo de fórmulas" al final de este manual.

4. Si todo está correcto, haga clic en **Confirmar**. Esto vuelve a calcular la boleta y además **marca como consumidos** los anticipos, cuotas de préstamo y afectaciones que se hayan aplicado (no podrán volver a descontarse en otra boleta).
5. Con la boleta confirmada, puede usar **Generar Asiento Contable** y luego **Registrar pago** (ver sección 10).
6. Una boleta en borrador se puede **Cancelar**; una boleta ya con pago registrado, no.

[CAPTURA: boleta de sueldo con las líneas Básico, AFP 12,71%, Total Ganado, Total Deducciones y Líquido Pagable]

---

## 4. Lotes de recibos de sueldo (payslip.run)

Menú: **Nómina Bolivia → Lotes de recibos de sueldo → Listado → Crear**

Útil para procesar la planilla completa del mes de una sola vez:

1. Complete **fecha de inicio** y **fecha de fin** del período.
2. Haga clic en **Generar recibos de sueldo**: el sistema crea (o actualiza) una boleta por cada contrato vigente en ese rango de fechas y las calcula automáticamente.
3. Revise las boletas generadas (accesibles desde el propio lote).
4. Haga clic en **Confirmar recibos**: confirma todas las boletas que sigan en borrador.
5. Haga clic en **Generar asiento contable**: crea **un solo asiento consolidado**, agregando los montos por cuenta contable (con ajuste automático de cualquier residuo de redondeo). El lote pasa a estado **Cerrado**.

[CAPTURA: lote de recibos de sueldo con la lista de boletas incluidas]

---

## 5. Anticipos

Menú: **Nómina Bolivia → Gestión de Trabajadores → Anticipo**

1. **Crear** un anticipo: empleado, monto total, fecha.
2. **Enviar** (pasa a estado "Pendiente").
3. **Aprobar** (requiere permiso de Gerencia de RRHH). A partir de aquí, el anticipo queda disponible para descontarse.
4. **No es necesario hacer nada más para que se descuente**: al calcular (o recalcular) la boleta del empleado cuyo período incluye la fecha del anticipo, el sistema busca anticipos **aprobados y aún no aplicados a ninguna boleta**, y agrega automáticamente una línea "Anticipo" (deducción). Al **confirmar** esa boleta, el anticipo queda marcado como consumido.
5. Por separado, cuando efectivamente entrega el dinero al empleado, use el botón **Registrar pago** del anticipo para generar el asiento contable correspondiente y pasarlo a estado **Pagado**.

⚠️ **Nota importante:** el estado "Pagado" del anticipo (paso 5, sobre el dinero entregado al empleado) es independiente de que el anticipo ya se haya descontado en una boleta (pasos 3-4, que depende solo del estado "Aprobado"). Un anticipo puede estar ya descontado en la boleta del mes y seguir figurando como "no pagado" si todavía no se registró la entrega física del dinero.

⚠️ **Por confirmar:** el sistema tiene un segundo camino con el mismo propósito — el menú **Préstamo** (sección 6) permite crear un registro de tipo "Anticipo" con plan de cuotas. Este manual documenta el flujo de **Anticipo** (esta sección) como el principal por ser el más directo, pero ambos caminos están activos en el sistema. Confirme con AEI cuál debe usar su empresa de forma consistente para evitar confusión entre ambos registros.

[CAPTURA: formulario de Anticipo con el flujo de estados Borrador → Pendiente → Aprobado → Pagado]

---

## 6. Préstamos con cuotas

Menú: **Nómina Bolivia → Gestión de Trabajadores → Préstamo**

1. **Crear**: empleado, cantidad de cuotas, tasa de interés (si aplica), periodicidad (mensual/trimestral).
2. Haga clic en **Generar plan de cuotas**: el sistema calcula el monto de cada cuota y las crea.
3. **Enviar** y luego **Aprobar**: al aprobar se genera el asiento contable de desembolso y se fijan las fechas de vencimiento de las cuotas (la primera vence el día 5 del mes siguiente).
4. Cada cuota **pendiente y vencida** se descuenta automáticamente en la boleta del período correspondiente (línea "Préstamo"), igual que un anticipo — no requiere ninguna acción adicional del usuario.
5. También puede pagar una cuota por adelantado manualmente desde la propia cuota, con **Registrar pago**.
6. Cuando todas las cuotas quedan pagadas, el préstamo pasa automáticamente a estado **Pagado**.

[CAPTURA: préstamo con su tabla de cuotas y estados]

---

## 7. Aguinaldo

Menú: **Nómina Bolivia → Gestión de Trabajadores → Aguinaldo**

1. **Crear**: empleado, tipo (Primer Aguinaldo / Segundo Aguinaldo).
2. Haga clic en **Calcular Aguinaldo**: el sistema busca hasta 12 boletas confirmadas del empleado en el año, promedia el **Líquido Pagable** de las últimas 3, y prorratea el resultado según los meses efectivamente trabajados.
3. Revise el **Monto Calculado**.
4. Haga clic en **Registrar Pago / Generar Asiento Contable**: requiere que el diario contable de aguinaldo (código `AGUI`) y las cuentas correspondientes estén parametrizados en Ajustes de Contabilidad.
5. El aguinaldo pasa a **Pagado** cuando el monto pagado alcanza el monto calculado.

Requisito para que el cálculo sea correcto: el empleado debe tener boletas **confirmadas** (no en borrador) dentro del año que se está liquidando.

[CAPTURA: formulario de Aguinaldo con el monto calculado y el botón de pago]

---

## 8. Finiquito / Liquidación

El proceso empieza siempre con una **Desvinculación**.

1. Menú: **Nómina Bolivia → Gestión de Trabajadores → Desvinculaciones → Crear**.
2. Complete: empleado, CI, **tipo** (Renuncia / Despido / Jubilación / Muerte / Fin de contrato), **condición** (Con responsabilidad del empleador / Sin responsabilidad del empleador / No aplica), fecha de baja.
3. **Confirmar**. Esto genera automáticamente una **Liquidación** asociada al empleado.
4. Vaya a **Nómina Bolivia → Gestión de Trabajadores → Liquidaciones**, abra la liquidación generada.
5. Haga clic en **Calcular Liquidación**. El sistema calcula, según la normativa citada en el propio sistema (Art. 44 de la Ley General del Trabajo, DS 3150, DS 0110/2009):

   | Concepto | Cuándo aplica |
   |---|---|
   | **Vacaciones no gozadas** | Siempre, según días acumulados no consumidos (escala de 15/20/30 días según antigüedad). |
   | **Aguinaldo proporcional** | Siempre, prorrateado por meses trabajados en el año de la baja. |
   | **Indemnización** | Exenta si la baja fue "sin responsabilidad del empleador"; aplica en el resto de los casos. |
   | **Desahucio** | Solo si la baja fue con responsabilidad del empleador, jubilación o muerte (3 veces el promedio salarial). |

6. Registre el pago con **Registrar Pago Parcial** (el sistema valida que no exceda el total pendiente) o publique el asiento contable completo. Cuando el pago acumulado alcanza el total, la liquidación pasa a **Pagada**.
7. Para imprimir el formulario de finiquito en Excel, use el asistente de impresión disponible desde la Desvinculación.

Nota adicional: si el empleado vuelve a ser contratado, existe un botón **Recontratar Empleado** en su ficha (visible cuando está marcado "de baja"), que genera un nuevo contrato sin necesidad de crear el empleado de cero.

[CAPTURA: liquidación con los 4 conceptos calculados y el botón "Registrar Pago Parcial"]

---

## 9. Vacaciones

Menú: **Nómina Bolivia → Vacaciones → Resumen**

Este módulo **no tiene un formulario propio de solicitud de vacaciones**: reutiliza el módulo estándar de **Ausencias** de Odoo. El resumen muestra, por empleado: **Días acumulados**, **Días consumidos** y **Días disponibles**.

- Para que un empleado solicite vacaciones, use el módulo estándar de **Ausencias** de Odoo y elija el tipo de ausencia **"Vacaciones"**.
- El día que se aprueba la solicitud, el sistema toma una fotografía del sueldo diario vigente para calcular el monto correspondiente.

⚠️ **Atención:** el sistema busca el tipo de ausencia por el nombre exacto **"Vacaciones"**. Si en su instancia el tipo de permiso se llama de otra forma, el Resumen mostrará **0 días disponibles sin ningún mensaje de error**. Verifique el nombre exacto en **Ausencias → Configuración → Tipos de Ausencias** si el resumen no coincide con lo esperado.

[CAPTURA: pantalla Resumen de vacaciones por empleado]

---

## 10. Exportar la Planilla MTSS

Menú: **Nómina Bolivia → Lotes de recibos de sueldo → Exportar Planilla MTSS**

1. Abra el asistente.
2. Complete **Año** y **Mes** (y, opcionalmente, un lote específico si quiere acotar la exportación a un solo lote de boletas).
3. Haga clic en **Exportar**. El sistema descarga un archivo **Excel** con el Formato de Planilla Mensual, con los datos de todas las boletas **confirmadas** del período elegido.

[CAPTURA: asistente de exportación de Planilla MTSS con los campos Año y Mes]

---

## 11. Pago de una boleta

Desde una boleta **confirmada** (o desde un lote ya cerrado), haga clic en **Registrar pago**:

1. Se abre un asistente con: diario contable, fecha de pago, y una nota/memo opcional.
2. Al **confirmar**, el sistema genera el asiento contable correspondiente: débito a la cuenta configurada en Ajustes de Contabilidad para el pago de boletas, y crédito a la cuenta por defecto del diario elegido (banco o caja).
3. Si la boleta pertenece a un lote que ya tiene su propio asiento contable consolidado, el pago hace referencia a ese asiento en lugar de crear uno nuevo.

[CAPTURA: asistente de pago de boleta, con diario y fecha de pago]

---

## Configuración de parámetros de cálculo

Menú: **Nómina Bolivia → Configuración → Parámetros de Cálculo**

Cada parámetro tiene un **código único**, un nombre, un tipo de valor (Porcentaje o Monto fijo) y su valor. Los más relevantes que trae el sistema por defecto:

| Código | Nombre | Valor de referencia |
|---|---|---|
| `smn_bo` | Salario Mínimo Nacional | Bs 2.750,00 |
| `ded_afp` | Aporte laboral a la AFP | 12,71% |
| `app` | Aporte patronal | 17,21% |
| `imp_rciva` | RC-IVA | 13% |
| `fac_hex` | Factor de hora extra | 2,00 |
| `inc_perc` | Incremento salarial | 5% |
| `ant_01`…`ant_07` / `porc_01`…`porc_07` | Escala de antigüedad para el Bono de Antigüedad | 50% a 5% según años de servicio |

⚠️ **Estos valores son de referencia** cargados por el sistema al instalarse; verifique y actualice el SMN y los porcentajes vigentes según la normativa boliviana del año en curso **antes** de calcular boletas del período.

⚠️ **Por confirmar:** existen además parámetros de AFP desglosados por caja (`afp_010`, `afp_0171`, `afp_05`, etc.) cargados en el sistema pero que ninguna fórmula activa referencia hoy. No los modifique sin confirmar primero con soporte técnico si tienen algún uso vigente.

El **código** de cada parámetro debe ser único: si intenta crear uno duplicado, el sistema lo rechaza.

[CAPTURA: lista de Parámetros de Cálculo con código, nombre y valor]

---

## Anexo de fórmulas — REGLAS.md

El detalle exacto de las 22 reglas salariales predefinidas del sistema (haberes, deducciones, totalizadores y aporte patronal), con su fórmula Python y su código exacto, está documentado en el archivo **`REGLAS.md`** dentro del módulo del producto (`addons/l10n_bo_payroll_bolivia_base/REGLAS.md` en el repositorio de la localización). Este manual no lo duplica: consúltelo si necesita verificar o ajustar una fórmula específica.

Las reglas están organizadas en 6 bloques, en este orden de cálculo:

1. **Haberes** — Haber Básico, Bono de Antigüedad, Horas Extra, Vacaciones, bonos y subsidios fijos, Dominical, Facturas Presentadas (Form. 110).
2. **Total Ganado** — totalizador de todos los haberes.
3. **Deducciones** — AFP (12,71%), RC-IVA, Anticipo, Préstamo, descuentos, retención judicial, faltas injustificadas.
4. **Total Deducciones** — totalizador de todas las deducciones.
5. **Líquido Pagable** — Total Ganado + Total Deducciones.
6. **Aporte patronal** (17,21%) — no afecta el neto del empleado; es un costo adicional de la empresa.

Menú relacionado: **Nómina Bolivia → Configuración → Categorías de Reglas** y **→ Reglas salariales**, para consultar (no se recomienda modificar sin soporte técnico) las reglas y categorías cargadas.

---

## FAQ y errores comunes

**¿Por qué el Total Ganado, Total Deducciones o Líquido Pagable me dan 0.0?**
Este era un problema conocido de versiones anteriores al 13 de agosto de 2026 (falta de categorización interna de las reglas). Si su instancia es posterior a esa fecha, ya está corregido. Si aún lo ve, contacte a soporte técnico.

**¿Por qué el Resumen de Vacaciones muestra 0 días para todos los empleados?**
Verifique que el tipo de ausencia se llame exactamente **"Vacaciones"** en Ausencias → Configuración → Tipos de Ausencias (ver sección 9).

**Registré un anticipo y no se descontó en la boleta del mes.**
Verifique que el anticipo esté en estado **Aprobado** (no basta con "Pendiente") y que su fecha caiga dentro del período de la boleta. Recalcule la boleta después de aprobar el anticipo.

**¿Cuál es la diferencia entre "Anticipo" y "Préstamo" tipo Anticipo?**
Ambos existen activos en el sistema hoy (ver sección 5). Use el camino que su empresa haya adoptado de forma consistente; ⚠️ por confirmar con AEI cuál es el oficial para su instalación.

**Un contrato sin Estructura Salarial, ¿no calcula nada?**
Al contrario: si no asigna una estructura, el sistema aplica **todas** las reglas activas. La estructura sirve para **limitar**, no para habilitar, el cálculo (ver sección 2).

**Intenté crear un Parámetro de Cálculo con un código que ya existe y me lo rechazó.**
Es el comportamiento esperado: el código de cada parámetro debe ser único.

**La exportación de la Planilla MTSS no incluye a un empleado.**
Verifique que ese empleado tenga una boleta **confirmada** (no en borrador) para el año/mes que está exportando — la exportación solo toma boletas confirmadas.

---

⚠️ **Por confirmar con el equipo antes de considerar este manual cerrado:**
- Cuál de los dos caminos de anticipo (sección 5 y 6) debe documentarse como el flujo oficial.
- Si los parámetros AFP desglosados (`afp_010`, `afp_0171`, etc.) tienen algún uso vigente o son datos heredados a eliminar.
- El nombre exacto del grupo de seguridad requerido para aprobar anticipos/préstamos (documentado aquí como "Gerencia de RRHH", verificar el nombre exacto en su instancia).
