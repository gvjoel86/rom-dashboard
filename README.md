# ROM Dashboard

Dashboard local para Windows que organiza ROMs y BIOS para una consola **R36S Plus con ArkOS**.

- Cuenta juegos por sistema en la SD (`EASYROMS`) o por WiFi (`\\IP\roms`).
- Detecta el sistema de los archivos de una carpeta de entrada y los copia a la carpeta correcta.
- Comprueba BIOS (nombre exacto y MD5).
- Descarga carátulas de [libretro-thumbnails](https://thumbnails.libretro.com/) y las registra en `gamelist.xml` sin perder partidas ni favoritos.
- Avisa de versiones nuevas; se actualiza solo cuando pulsas **Actualizar ahora** (verifica SHA-256).

Solo Python estándar, sin dependencias. Escucha únicamente en `127.0.0.1`.

## Instalar

1. Python 3 desde la Microsoft Store ("Python 3.13").
2. Descarga el repositorio (Code → Download ZIP) y descomprímelo.
3. Doble clic en `Iniciar Dashboard.bat`.

## Publicar una versión nueva

```
python make_manifest.py 1.1.0 "Qué cambia"
git commit -am "v1.1.0" && git push
```

`version.json` lleva el SHA-256 de cada archivo actualizable; el `.bat` y `config.json` nunca se actualizan solos.
No incluye ni enlaza ROMs comerciales.
