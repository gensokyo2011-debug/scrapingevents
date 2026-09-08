# Scraper de eventos - Ciudad de Panamá

Recolecta eventos de fuentes **estáticas** (HTML plano) y **dinámicas**
(cargadas con JS) para mapear dónde tu marca podría activar o patrocinar.

## Instalación

```bash
pip install -r requirements.txt
playwright install chromium
```

## Uso

```bash
python scraper_eventos_panama.py
```

Genera `eventos_panama.csv` y `eventos_panama.json` con: nombre, fecha,
lugar, categoría, organizador, email, teléfono, url, fuente y tipo_fuente
(estatica/dinamica).

Para correr solo las fuentes estáticas (más rápido, sin Playwright):

```python
from scraper_eventos_panama import recolectar_todo, exportar
exportar(recolectar_todo(incluir_dinamicas=False))
```

## Notas importantes

- **Selectores CSS**: cada función tiene comentarios `# SELECTOR:` en los
  puntos donde depende de la estructura HTML actual del sitio. Si un sitio
  rediseña su página, esos selectores hay que actualizarlos (inspecciona con
  DevTools → clic derecho en la tarjeta de evento → "Inspeccionar").
- **Contacto**: la mayoría de agendas culturales no publican email/teléfono
  directo del organizador; el script busca patrones de email/teléfono en el
  texto de cada tarjeta o página de detalle, pero muchas veces solo obtendrás
  el nombre del organizador o un link de contacto indirecto (ej. Eventbrite).
- **Rate limiting**: el script incluye pausas básicas entre requests. Si vas
  a correrlo con frecuencia, considera añadir más delay o rotar user-agent
  para evitar bloqueos.
- **Fuentes adicionales recomendadas** para tu caso de uso (activaciones de
  marca), no incluidas aún: Ciudad del Saber (agenda de eventos corporativos),
  Panama Convention Center, Facebook Events (requiere API/token), Cámara de
  Comercio de Panamá. Puedo agregarlas si quieres — dime cuáles priorizar.

## Próximo paso sugerido

Cruzar el output con criterios de tu marca (categoría de evento, tamaño de
audiencia, tipo de público) para priorizar cuáles vale la pena contactar.
Puedo armar esa capa de scoring si me das los criterios.

## Hostear en línea (Render, gratis, ~2 minutos)

No puedo desplegar el servidor desde aquí, pero el paquete ya está listo
para deploy en un clic:

1. Sube esta carpeta a un repo de GitHub (nuevo repo, público o privado).
2. Entra a https://render.com → **New +** → **Blueprint**.
3. Conecta el repo. Render detecta `render.yaml` y `Dockerfile` automáticamente.
4. Click **Apply** → espera el build (~3-5 min, instala Chromium de Playwright).
5. Render te da la URL pública, ej: `https://eventos-panama.onrender.com`

Alternativa sin GitHub: Render también permite "Deploy from a Git URL" o
subir el zip directo en algunos planes; GitHub es el camino más simple.

Nota: el plan free de Render duerme el servicio tras inactividad (primer
request tarda ~30s en despertar) — normal para un MVP.
