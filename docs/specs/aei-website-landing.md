# SDD: Sitio web público de AEI Software (landing, precios, contacto) en `aei_website`

- **Estado:** En ejecución. El responsable pidió aplicar el diseño (05/11/2026); las decisiones se
  resolvieron con las recomendaciones de la sección 5, salvo D1 (usuarios), que sigue abierta.
- **Módulo:** `addons/aei_website` (depende de `odoo_k8s_saas_subscription`)
- **Fuente del diseño:** exportación en Next.js de la landing aprobada, revisión del 03/11/2026, en
  `C:\Users\Ronald\Documents\RIBENTEK\AEI-SOFTWARE\lading_page_next\aei-software-next`
  (fuera de este repositorio). Es solo una referencia visual y de contenido. No se despliega código de Next.js.

## 1. Objetivo

Reproducir el diseño aprobado de la landing dentro de Odoo 18 Website, versionado en código, para que
un visitante pueda conocer la oferta, elegir un plan y llegar al carrito nativo de Odoo. Los planes,
precios y capacidades deben salir de registros de Odoo, no de copias dentro de las plantillas.

## 2. Estado actual (verificado el 05/11/2026)

- `aei_website` se instala sin errores en una base limpia; se crean la vista de la portada y los 3
  productos de plan.
- Sus planes son **provisionales e incorrectos**: nombres Inicial/Crecimiento/Empresarial,
  Bs 199/399/799 y 50 usuarios en el plan superior. Además, los precios están escritos fijos en la
  plantilla QWeb.
- `data/saas_plans.xml` y las plantillas de suscripción se cargan con `noupdate="1"`: editar el XML
  **no** modifica una base ya instalada (ver riesgo R1).

## 3. Fuente de verdad de los planes (según el diseño, pendiente de D1)

| Plan | Precio (Bs/mes) | Usuarios | Almacenamiento | Soporte/mes |
|---|---|---|---|---|
| Starter | 349 | 3 | 10 GB | 2 h |
| Pro | 649 | 10 | 20 GB | 5 h |
| Advanced | 1.290 | 25 | 50 GB | 10 h |

Plantillas de suscripción existentes: starter 3 usuarios / 10 GB / 2 h, pro 10 / 20 GB / 5 h,
**enterprise 50 usuarios** / 50 GB / 10 h. Solo el plan superior no coincide (25 frente a 50 usuarios).

## 4. Alcance

**Incluye:** portada (8 secciones), página de precios (planes, matriz de módulos, reportes, preguntas
frecuentes), página de contacto, encabezado y pie de página, activos de marca, productos de plan y su
vínculo con las plantillas de suscripción, y pruebas.

**No incluye:**
- Las pantallas de tienda, carrito, checkout, cuenta y portal. Las gestionan Odoo (`website_sale`,
  `portal`) y `odoo_k8s_saas_subscription`. Las versiones de Next son simulaciones.
- `commerce.js` (simulación de checkout con localStorage) y `editor.js` (editor visual).
- Prueba gratuita de 15 días, facturación anual y cupón: el diseño los muestra, pero el backend aún
  no los soporta (ver D4).
- Todo lo relacionado con Banco Ganadero o pagos.
- Alojar o compilar el proyecto Next.js.

## 5. Decisiones requeridas del responsable

**Estado de las decisiones (05/11/2026):** D2, D3 y D4 se aplican con la recomendación, porque el
responsable pidió aplicar el diseño. D1 aplica la clave técnica y el nombre; **los usuarios del plan
superior siguen abiertos**: la tarjeta lee el valor de la plantilla de suscripción (hoy 50) y se
corrige con un solo cambio de dato cuando el responsable decida.

**Restricción de estilo (del responsable):** CSS propio, bien estructurado y ordenado. El módulo no
usa clases, componentes ni dependencias de Bootstrap. Odoo Website carga Bootstrap en su bundle y eso
no se puede quitar; lo que se garantiza es que el marcado y el CSS de `aei_website` no lo usan.

| ID | Pregunta | Recomendación |
|---|---|---|
| D1 | Plan superior: nombre y tamaño. El diseño dice **Advanced, 25 usuarios**; el repositorio y el portal dicen **enterprise, 50 usuarios**. | Mantener la clave técnica `enterprise` (el `PLAN_RESOURCES` del portal y K8s dependen de ella) y mostrar **Advanced** en el sitio. Renombrar la clave afecta al módulo de suscripciones, al portal y a las migraciones. Usuarios: lo define el responsable (25 o 50). |
| D2 | Precios finales. ¿Los valores del diseño (349/649/1.290) reemplazan los provisionales? | Sí, si el diseño está aprobado. Moneda BOB. |
| D3 | Encabezado y pie: ¿reemplazar los de Odoo por los del diseño o aplicar estilo a los de Odoo? | Reemplazarlos mediante herencia de la plantilla de layout, conservando los widgets de carrito e inicio de sesión de Odoo. |
| D4 | Prueba gratuita, selector anual y cupón: ¿fase 1 o posterior? | Posterior. La fase 1 entrega solo planes mensuales; el selector y los botones de prueba se ocultan, no se simulan. Cada uno tendrá su propio spec. |

## 6. Escenarios (Dado / Cuando / Entonces)

**E1. La portada muestra los planes desde los datos.**
Dado que los tres productos de plan están publicados, cuando un visitante abre `/`, entonces la
página responde 200 y muestra tres tarjetas de plan cuyo precio y capacidades coinciden con el
producto y su plantilla de suscripción.

**E2. Una tarjeta de plan lleva al carrito nativo.**
Dado un visitante en `/` o `/pricing`, cuando elige un plan, entonces se envía un POST con un token
CSRF válido a `/shop/cart/update` con el producto de ese plan, y el carrito contiene exactamente ese
producto.

**E3. Los precios no están duplicados.**
Dado un producto de plan cuyo `list_price` cambia, cuando la página se vuelve a renderizar, entonces la
tarjeta muestra el nuevo precio sin editar ninguna plantilla.

**E4. Plan no publicado o inexistente.**
Dado que un producto de plan no está publicado, cuando un visitante abre `/pricing`, entonces esa
tarjeta no se muestra y la página sigue respondiendo 200.

**E5. Contenido de la página de precios.**
Dado un visitante que abre `/pricing`, entonces ve la sección de planes, la comparativa de módulos
(`#modulos`), la sección de reportes y las preguntas frecuentes, y los enlaces ancla del encabezado
funcionan.

**E6. Contacto.**
Dado un visitante que abre `/contactus`, cuando envía el formulario con datos válidos, entonces la
solicitud se acepta con protección CSRF y el mensaje llega al canal configurado. Los datos inválidos
se rechazan con un mensaje genérico.

**E7. Interactividad sin DOM inseguro.**
Dado un visitante que usa el detalle de planes, el explorador de módulos o el selector de rubro,
entonces la página se actualiza usando solo `textContent` o creación de elementos. En el JS del módulo
no existe `innerHTML`, `outerHTML`, `insertAdjacentHTML` ni `document.write`.

**E8. El vínculo con el aprovisionamiento se mantiene.**
Dado cualquier producto de plan de este módulo, entonces pertenece a la categoría
`odoo_k8s_saas.product_category_odoo_saas` y tiene una plantilla de suscripción, de modo que una orden
pagada sigue disparando el aprovisionamiento.

**E9. Sin Bootstrap en el módulo.**
Dado el código del módulo, entonces ninguna plantilla QWeb ni hoja de estilo usa nombres de clase de
Bootstrap (`container`, `row`, `col-*`, `btn`, `d-*`, `py-*`, etc.) y toda clase propia lleva el
prefijo `aei-`.

## 7. Criterios de aceptación

- [ ] E9: ninguna plantilla ni hoja de estilo del módulo usa nombres de clase de Bootstrap. Todas las clases propias llevan el prefijo `aei-`. Lo verifica una prueba.
- [ ] El CSS está dividido por responsabilidad (tokens, base, layout, componentes, secciones), con variables CSS y sin reglas globales sobre `body`, `html` ni etiquetas desnudas.
- [ ] E1 a E8 tienen cada uno una prueba automatizada que falló antes de existir el código (Red) y ahora pasa (Green).
- [ ] Ningún precio ni capacidad aparece como literal en QWeb o JS; se leen de registros.
- [ ] Todo formulario POST lleva `csrf_token`; `.github/scripts/security_gate.sh` pasa.
- [ ] Flake8 (reglas críticas) y Bandit pasan; el módulo se instala en una base limpia sin advertencias nuevas.
- [ ] El texto público está en español (Bolivia). El código, los identificadores y los comentarios están en inglés.
- [ ] No hay recursos remotos. Fuentes, CSS y logos se sirven desde `static/` del módulo.
- [ ] Se revisan visualmente móvil y escritorio frente al diseño (manual, declarado como tal).
- [ ] Se actualiza la lista de deuda conocida de `addons/aei_website/AGENTS.md` y se guardan las notas en Engram.

## 8. Plan

| Fase | Entregable | Depende de |
|---|---|---|
| P0 | El responsable responde D1 a D4. | - |
| P1 | Datos de planes: nombres, precios y capacidades correctos; lectura desde registros; pruebas E3, E4, E8. Migración para bases existentes (R1). | D1, D2 |
| P2 | Activos y layout: fuentes, CSS, logos en `static/`; encabezado y pie; pruebas E1, E2. | D3 |
| P3 | Secciones 1 a 8 de la portada; interactividad como widget público de Odoo (E7). | P2 |
| P4 | Página de precios con matriz de módulos, reportes y preguntas frecuentes; prueba E5. | P2 |
| P5 | Página de contacto; prueba E6. | P2 |
| P6 | Control de calidad, revisión visual, documentación, despliegue a staging mediante merge a `main`. | P1 a P5 |

Cada fase sigue Red, Green, Refactor y termina con un commit convencional.

## 9. Riesgos

- **R1. Datos con `noupdate="1"`.** Cambiar precios o usuarios en el XML no actualiza una base
  instalada. Usar un script de migración o decidir explícitamente `noupdate="0"`.
- **R2. CSS global.** El CSS del diseño pesa cerca de 90 KB y está escrito para una página completa.
  Puede alterar el estilo de páginas propias de Odoo (carrito, portal). Acotarlo bajo una clase
  contenedora y revisar `/shop` y `/my` tras cargarlo.
- **R3. Recursos en caché.** Cloudflare puede servir bundles antiguos de `/web/assets/*` después de
  un despliegue (ver `CLAUDE.md`, sección CDN). Purgarlo tras cambiar recursos.
- **R4. El JS del diseño no cumple nuestras reglas.** Los scripts de referencia usan `innerHTML` y
  `localStorage`. Reimplementar, no copiar.
- **R5. Desajuste de la clave de plan** entre el sitio, el módulo de suscripciones y el portal, si D1
  se resuelve renombrando solo uno de los lados.
- **R6. Contenido extenso en línea.** La matriz de módulos son unas 300 líneas de marcado. Portarla
  como QWeb legible, dividida en subplantillas por sección, no en un único archivo de 40 KB.

## 10. Plan de pruebas (se escriben primero)

`HttpCase`, con etiquetas `post_install` y `-at_install`, en `addons/aei_website/tests/`:
`test_home_plans` (E1, E3, E4), `test_cart_link` (E2), `test_pricing_page` (E5),
`test_plan_provisioning_link` (E8), `test_contact_form` (E6) y una verificación estática de que el JS
del módulo no contiene las llamadas DOM prohibidas (E7).
Se ejecutan con el comando del `AGENTS.md` raíz (`--http-port=8099`, base de datos descartable).

## 11. Avance (05/11/2026)

| Fase | Estado | Evidencia |
|---|---|---|
| P1 Datos de planes | Hecha | Planes Starter, Pro y Advanced con precios del diseño (`plan_pricing.py` calcula anual `-20%` y ahorros); capacidades leídas de la plantilla de suscripción; migración `18.0.1.1.0` probada. |
| P2 Activos y layout | Hecha | CSS puro en dos capas (`foundation/` + `refinements/`) sin Bootstrap; fuentes e imágenes locales; encabezado y pie propios en la portada (`aei_use_own_chrome_on_homepage`). |
| P3 Portada (`/`) | Hecha | 7 secciones (portada, clientes, procesos, perfiles, planes con barra Mensual/Anual y botones de prueba + compra, 8 preguntas frecuentes y cierre) + modales de detalle de planes y explorador de módulos (`website_catalog.py` + `modules.json`). Verificada píxel a píxel con Chrome headless y 42 pruebas en verde. |
| P4 Página de precios (`/pricing`) | Pendiente | Los enlaces del encabezado apuntan a anclas de `/` hasta que se porte la vista dedicada `/pricing`. |
| P5 Contacto (`/contactus`) | Pendiente | `/contactus` conserva por ahora el estilo nativo de Odoo. |
| P6 Cierre | En curso | Pruebas automatizadas (42/42) y `structure_gate.py` (0 violaciones nuevas) en verde; falta actualizar la base local `prueba-sass` (`localhost:8075`) y el despliegue a staging. |

Escenarios cubiertos por pruebas: E1, E2, E3, E4, E7, E8 y E9.
E5 y E6 dependen de P4 (`/pricing`) y P5 (`/contactus`). En el plan Advanced, la tarjeta muestra `50 usuarios` porque lo lee de `subscription_template_saas_enterprise` (el diseño estático muestra `25 usuarios`, decisión D1).
