# Guía de Pruebas Funcionales para QA — Sitio Web AEI Software y Pago con QR Banco Ganadero

**Sitio web a probar:** [https://www.aeisoftware.com](https://www.aeisoftware.com)

Esta guía describe paso a paso cómo recorrer el sitio web desde el navegador, qué botones presionar y qué debe verse en pantalla en cada etapa. No requiere conocimientos técnicos ni uso de consola.

---

## 1. Prueba de la Página Principal (Portada)

1. Ingrese desde el navegador a **[https://www.aeisoftware.com](https://www.aeisoftware.com)**.
2. **Qué debe revisar en la parte superior (Menú):**
   - Debe verse el logotipo de **AEI Software**, los enlaces del menú (**Procesos**, **Perfiles**, **Planes**, **Preguntas**, **Contacto**) y el botón **Iniciar sesión**.
3. **Qué debe revisar al bajar y subir por la página (Animaciones):**
   - Deslice la página hacia abajo lentamente hasta llegar al pie de página y luego vuelva a subir hacia el inicio.
   - Verifique que cada bloque (títulos, tarjetas de procesos, perfiles y planes) aparezca con un movimiento suave al entrar en la pantalla y se oculte suavemente al salir.
4. **Qué debe revisar en la sección de Planes:**
   - Haga clic en el enlace **Planes** del menú superior para que la página baje hasta las tarjetas de precios.
   - Cambie entre las opciones de periodo (Mensual / Anual) y moneda para comprobar que los precios se actualicen en pantalla.
5. **Qué debe revisar en Preguntas Frecuentes:**
   - Baje hasta la sección **Preguntas frecuentes** y haga clic sobre cada pregunta para verificar que se despliegue y se cierre la respuesta correctamente.

---

## 2. Prueba de las Pantallas de Cuenta (Iniciar sesión, Crear cuenta y Contraseña)

1. En la esquina superior derecha de la portada, haga clic en el botón **Iniciar sesión** (o ingrese a **[https://www.aeisoftware.com/account](https://www.aeisoftware.com/account)**).
2. **Qué debe verse en pantalla:**
   - Una pantalla dividida en dos columnas con el diseño de AEI Software: a la izquierda el mensaje **"Tu empresa. Un nuevo comienzo."** y a la derecha la tarjeta **"Comienza por ti."** con dos pestañas: **Iniciar sesión** y **Crear cuenta**.
3. **Prueba de la pestaña "Crear cuenta":**
   - Haga clic en la pestaña **Crear cuenta**.
   - Verifique que aparezcan los campos para registrar un nuevo cliente (**Tu correo electrónico**, **Tu nombre**, **Contraseña** y **Confirmar contraseña**) manteniendo el mismo diseño visual.
4. **Prueba de "¿Olvidaste tu contraseña?":**
   - Vuelva a la pestaña **Iniciar sesión** y haga clic en el enlace **¿Olvidaste tu contraseña?**.
   - Verifique que se muestre la pantalla para recuperar el acceso ingresando el correo electrónico y el botón para regresar al inicio de sesión.
5. **Prueba de ingreso al sistema:**
   - Vuelva a **Iniciar sesión**, escriba el correo y la contraseña proporcionados por el equipo y presione el botón **Iniciar sesión**.
   - Verifique que el sistema permita ingresar correctamente a la cuenta.

---

## 3. Prueba de la Página de Contacto

1. En el menú superior del sitio, haga clic en **Contacto** (o ingrese a **[https://www.aeisoftware.com/contactus](https://www.aeisoftware.com/contactus)**).
2. **Qué debe verse en pantalla:**
   - El título principal **"Tu siguiente paso empieza aquí."**
   - a la izquierda, el formulario con los campos: **Nombre completo**, **Correo electrónico**, **Teléfono / WhatsApp**, **Empresa**, **Asunto** y **Mensaje**.
   - A la derecha, la tarjeta informativa **"Nos vemos en Santa Cruz"** con los botones de contacto directo por WhatsApp y ubicación en Google Maps.
3. **Prueba de envío del formulario:**
   - Complete los datos del formulario con una consulta de prueba y presione el botón **Enviar mensaje**.
   - **Resultado esperado:** El sistema debe llevarlo a una pantalla de confirmación agradeciendo el contacto e indicando que el mensaje fue recibido.

---

## 4. Prueba de Compra y Pago con QR Banco Ganadero (Modo de Prueba)

Actualmente el método de pago **QR Banco Ganadero** está configurado en **Modo de Prueba (Demo)** para que pueda realizar compras completas de principio a fin sin utilizar dinero real.

1. Desde la portada (**[https://www.aeisoftware.com](https://www.aeisoftware.com)**), baje a la sección **Planes** y elija cualquiera de los planes haciendo clic en su botón de contratación.
2. Complete los pasos del carrito de compras (nombre del subdominio o datos solicitados en pantalla) hasta llegar a la pantalla de **Pago**.
3. **Selección del método de pago:**
   - En la lista de métodos de pago disponibles, seleccione la opción **QR Banco Ganadero**.
   - Haga clic en el botón **Pagar ahora**.
4. **Qué debe verse en la pantalla del código QR:**
   - Un aviso amarillo en la parte superior que indica: **"MODO DEMO — No se realiza ningún cobro real en Banco Ganadero"**.
   - La imagen del código QR en el centro de la pantalla junto con el monto a pagar en Bolivianos (`BOB`) y el código identificador del QR.
   - Un mensaje celeste indicando: **"Esperando confirmación del Banco Ganadero…"**.
   - Un botón verde llamado **"Simular Pago (Demo)"**.
5. **Simulación del pago:**
   - Haga clic en el botón verde **"Simular Pago (Demo)"**.
   - **Resultado esperado:** El mensaje cambiará indicando que el pago fue confirmado y, tras unos segundos, el sistema lo llevará automáticamente a la pantalla de confirmación final de su pedido/suscripción.

---

## 5. Lista Rápida de Verificación (Para marcar al finalizar)

- [ ] **Portada:** Se visualiza correctamente en computadora y celular, sin errores visuales.
- [ ] **Animaciones:** Los bloques entran y salen suavemente al bajar y subir por la página.
- [ ] **Cuenta:** Las pantallas de **Iniciar sesión**, **Crear cuenta** y **Recuperar contraseña** muestran el nuevo diseño de AEI Software y permiten ingresar al sistema.
- [ ] **Contacto:** El formulario de la pestaña **Contacto** envía el mensaje y muestra la pantalla de agradecimiento.
- [ ] **Pago QR Banco Ganadero:** Aparece como opción de pago, genera el código QR en pantalla y confirma la compra al presionar **"Simular Pago (Demo)"**.

