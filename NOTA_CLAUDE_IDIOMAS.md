NO EJECUTAR hasta que Claudio lo ordene expresamente

# Idiomas nuevos de aromario.app — publicación y selector

Contexto: las 12 páginas del sitio están traducidas y auditadas a cero fallos en 7 idiomas (portugués, francés, alemán, italiano, árabe, turco y polaco). Los entregables van en `traducciones-web.zip`, en la raíz de esta rama: por idioma, las 5 páginas principales y las 7 de guías (en la carpeta guias de cada idioma). El portugués conserva los nombres base (index.html, deseos.html…) para su carpeta; los demás idiomas traen los nombres ya sufijados.

Cambios:

- Cambio: publicación de las páginas por idioma en su ruta (/pt/, /fr/, /de/, /it/, /ar/, /tr/, /pl/, según el patrón ya usado por /en/), enlazadas entre sí con hreflang completos de las 9 versiones.
- Cambio: selector de idioma nuevo en TODAS las páginas, incluidas las actuales en español e inglés: fuera el interruptor de enlaces; botón de tres barritas que abre el menú de idiomas, con «Automático» como opción por defecto (detecta el idioma del navegador y recuerda la elección) y debajo los 9 idiomas.
- Cambio: las páginas en árabe se sirven con dir="rtl" (ya lo traen en el entregable).
- Cambio: las cifras y los textos vigentes se conservan tal como están en vivo (catálogo 12.600+ y cierre de portada en revisión de Google) en todas las versiones.
- Sin tocar: review-images.html queda como está.
- Al cierre: GitHub Pages despliega solo; Bishi verifica el sitio en vivo en los 9 idiomas.
