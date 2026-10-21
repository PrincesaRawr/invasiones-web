# invasiones-web

Página pública con el daño de cada jugador en las Invasiones.

Los datos los envía el **Analizador de Invasiones** del PC (lee la pantalla de Discord)
a `POST /api/subir` con la cabecera `X-Clave`. Aquí no se lee nada, solo se enseña.
Los datos viven en memoria: si Render se duerme, la página se queda vacía hasta que
el analizador vuelve a enviarlos.

`web/index.html` es la misma página que sirve el analizador en local: si se cambia
una, copiar a la otra.
