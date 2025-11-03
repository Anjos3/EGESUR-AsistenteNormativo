# Política de Privacidad - Despliegue en Netlify

Esta carpeta contiene el sitio web de Política de Privacidad para el GPT de Normativas EGESUR.

## 📁 Contenido

- `index.html` - Página de políticas de privacidad
- `styles.css` - Estilos profesionales y responsive
- `README.md` - Este archivo

## 🚀 Despliegue en Netlify (Drag & Drop)

### Paso 1: Acceder a Netlify

1. Ve a: https://app.netlify.com/
2. Inicia sesión o crea una cuenta gratuita

### Paso 2: Desplegar el Sitio

1. En el dashboard de Netlify, busca la sección **"Want to deploy a new site without connecting to Git?"**
2. Arrastra la carpeta `privacy-policy/` completa hacia el área de drop
   - O haz click en **"browse to upload"** y selecciona la carpeta
3. **Netlify desplegará automáticamente** el sitio en ~30 segundos

### Paso 3: Obtener la URL

1. Una vez desplegado, verás una URL generada automáticamente, por ejemplo:
   ```
   https://graceful-unicorn-abc123.netlify.app
   ```

2. **Personalizar el nombre del sitio (opcional):**
   - Click en **"Site settings"**
   - Click en **"Change site name"**
   - Ingresa un nombre personalizado, ejemplo: `egesur-normativas-privacy`
   - La URL será: `https://egesur-normativas-privacy.netlify.app`

### Paso 4: Usar la URL en el GPT

1. Copia la URL de Netlify
2. Ve a la configuración de tu GPT en ChatGPT
3. En la sección de privacidad/publicación, pega la URL en el campo **"Privacy Policy"**
4. Guarda los cambios

## 🔧 Actualizar el Contenido

Si necesitas modificar las políticas de privacidad:

1. Edita el archivo `index.html`
2. Vuelve a arrastrar la carpeta a Netlify (sobrescribirá el sitio existente)
3. O conecta el repositorio de GitHub a Netlify para despliegues automáticos

## ✅ Verificación

Después del despliegue, verifica que:
- La página se vea correctamente en navegadores de escritorio
- La página sea responsive en móviles
- Todos los enlaces funcionen
- El diseño se vea profesional

## 📝 Personalización

Si necesitas personalizar la política:

1. **Información de contacto:** Edita la sección 11 en `index.html`
2. **Fecha de actualización:** Modifica el `<p class="last-updated">` en el header
3. **Colores:** Ajusta los gradientes en `styles.css` (busca `#667eea` y `#764ba2`)
4. **Logo:** Agrega un `<img>` en el header si lo deseas

## 🌐 Características del Sitio

- ✅ **100% Responsive:** Se adapta a móviles, tablets y escritorio
- ✅ **Sin dependencias:** HTML y CSS puro
- ✅ **Optimizado para impresión:** Tiene estilos específicos para print
- ✅ **Accesible:** Estructura semántica HTML5
- ✅ **SEO básico:** Meta tags configurados
- ✅ **Diseño profesional:** Gradientes y animaciones sutiles

## 📱 Vista Previa Local

Para ver el sitio antes de desplegarlo:

1. Abre `index.html` directamente en tu navegador
2. O usa un servidor local:
   ```bash
   # Con Python
   python -m http.server 8000

   # Con Node.js
   npx http-server
   ```

## 🔒 Seguridad

- No contiene scripts externos (sin trackers, sin analytics)
- No usa cookies
- HTTPS habilitado automáticamente por Netlify
- Sin formularios ni procesamiento de datos

## 💡 Notas Importantes

1. **Plan gratuito de Netlify:** Suficiente para este sitio estático
2. **Dominio personalizado:** Puedes agregar tu propio dominio en Netlify (ej: `privacy.egesur.com`)
3. **SSL/HTTPS:** Habilitado automáticamente por Netlify
4. **Uptime:** 99.9% garantizado por Netlify

## 🆘 Soporte

Si encuentras problemas con el despliegue:
- Documentación de Netlify: https://docs.netlify.com/
- Soporte de Netlify: https://www.netlify.com/support/

---

**Última actualización:** Noviembre 2025
