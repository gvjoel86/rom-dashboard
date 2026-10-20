"""ROM Dashboard para R36S Plus / ArkOS.

Dashboard local (solo Python estandar, sin dependencias) que:
  - muestra cuantos juegos hay por sistema en la tarjeta SD (particion EASYROMS)
    o en la carpeta compartida por red (Samba) de ArkOS,
  - detecta el sistema de los archivos que dejes en una carpeta "Entrada"
    y los copia/mueve a la carpeta correcta,
  - comprueba las BIOS (nombre exacto + MD5),
  - muestra espacio libre,
  - avisa cuando hay una version nueva en GitHub; con el boton "Actualizar
    ahora" la descarga, verifica su SHA-256 y se reinicia (nunca sin tu clic).

Uso:  doble clic en "Iniciar Dashboard.bat"  (o:  python rom_dashboard.py)
Se abre en el navegador en http://127.0.0.1:8765 . Solo escucha en tu PC.
"""

import hashlib
import json
import os
import re
import shutil
import sys
import threading
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST, PORT = "127.0.0.1", 8765
APP_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
CONFIG_FILE = Path(__file__).resolve().parent / "config.json"
VERSION_FILE = APP_DIR / "version.json"
RESTART_FLAG = APP_DIR / ".reiniciando"
RESTART_CODE = 3  # "Iniciar Dashboard.bat" vuelve a arrancar el programa con este codigo
UPDATE_URL = "https://raw.githubusercontent.com/gvjoel86/rom-dashboard/main/"

DEFAULT_CONFIG = {
    # Ejemplos:  "E:\\"  (SD en el lector)   o   "\\\\192.168.1.50\\roms"  (Samba)
    "roms_path": "",
    "inbox_path": str(Path.home() / "Downloads" / "ROMs-entrada"),
}

# Nombre de carpeta ArkOS -> (nombre legible, extensiones)
SYSTEMS = {
    "nes": ("Nintendo NES", [".nes", ".unf", ".unif"]),
    "fds": ("Famicom Disk System", [".fds"]),
    "snes": ("Super Nintendo", [".sfc", ".smc", ".fig", ".swc"]),
    "n64": ("Nintendo 64", [".n64", ".z64", ".v64"]),
    "gb": ("Game Boy", [".gb"]),
    "gbc": ("Game Boy Color", [".gbc"]),
    "gba": ("Game Boy Advance", [".gba"]),
    "nds": ("Nintendo DS", [".nds"]),
    "virtualboy": ("Virtual Boy", [".vb"]),
    "pokemini": ("Pokemon Mini", [".min"]),
    "megadrive": ("Mega Drive", [".md", ".gen", ".smd"]),
    "genesis": ("Genesis", [".md", ".gen", ".smd"]),
    "mastersystem": ("Master System", [".sms"]),
    "gamegear": ("Game Gear", [".gg"]),
    "sg-1000": ("SG-1000", [".sg"]),
    "sega32x": ("Sega 32X", [".32x"]),
    "segacd": ("Sega CD", [".chd", ".cue"]),
    "dreamcast": ("Dreamcast", [".cdi", ".gdi", ".chd"]),
    "psx": ("PlayStation", [".chd", ".cue", ".pbp", ".m3u"]),
    "psp": ("PSP", [".iso", ".cso"]),
    "pcengine": ("PC Engine", [".pce"]),
    "pcenginecd": ("PC Engine CD", [".chd", ".cue"]),
    "atari2600": ("Atari 2600", [".a26"]),
    "atari7800": ("Atari 7800", [".a78"]),
    "atarilynx": ("Atari Lynx", [".lnx"]),
    "ngp": ("Neo Geo Pocket", [".ngp"]),
    "ngpc": ("Neo Geo Pocket Color", [".ngc"]),
    "wonderswan": ("WonderSwan", [".ws"]),
    "wonderswancolor": ("WonderSwan Color", [".wsc"]),
    "coleco": ("ColecoVision", [".col"]),
    "msx": ("MSX", [".rom", ".mx1", ".mx2"]),
    "pico-8": ("PICO-8", [".p8"]),
    "tic80": ("TIC-80", [".tic"]),
    "arcade": ("Arcade", []),
    "mame": ("MAME", []),
    "fbneo": ("FinalBurn Neo", []),
    "neogeo": ("Neo Geo", []),
    "ports": ("Ports (PortMaster)", [".sh"]),
}
GENERIC_EXTS = {".zip", ".7z", ".bin", ".iso", ".img", ".chd", ".cue", ".rom"}
NOT_ROMS = {
    ".xml", ".png", ".jpg", ".jpeg", ".txt", ".cfg", ".srm", ".sav", ".state",
    ".auto", ".db", ".ini", ".log", ".nfo", ".pdf", ".md5", ".dat", ".mp4",
}
SKIP_DIRS = {"bios", "themes", "backup", "videos", "images", "media", "screenshots"}

# BIOS que buscan los emuladores de ArkOS (carpeta EASYROMS/bios).
# Si el hash no coincide puede ser otra revision valida: se avisa, no se borra nada.
BIOS = [
    {"system": "PlayStation", "need": "una de estas", "group": "psx", "files": [
        ("scph1001.bin", "924e392ed05558ffdb115408c263dccf"),
        ("scph5501.bin", "490f666e1afb15b7362b406ed1cea246"),
        ("scph7001.bin", "1e68c231d0896b7eadcad1d7d8e76129")]},
    {"system": "Game Boy Advance", "need": "opcional", "files": [
        ("gba_bios.bin", "a860e8c0b6d573d191e4ec7db1b1e4f6")]},
    {"system": "Famicom Disk System", "need": "obligatoria", "files": [
        ("disksys.rom", "ca30b50f880eb660a320674ed365ef7a")]},
    {"system": "Sega CD", "need": "segun region", "group": "segacd", "files": [
        ("bios_CD_U.bin", "2efd74e3232ff260e371b99f84024f7f"),
        ("bios_CD_E.bin", "e66fa1dc5820d254611fdcdba0662372"),
        ("bios_CD_J.bin", "278a9397d192149e84e820ac621a8edd")]},
    {"system": "PC Engine CD", "need": "obligatoria", "files": [
        ("syscard3.pce", "38179df8f4ac870017db21ebcbf53114")]},
    {"system": "Atari Lynx", "need": "obligatoria", "files": [
        ("lynxboot.img", "fcd403db69f54290b51035d82f835e7b")]},
    {"system": "Nintendo DS", "need": "opcional", "files": [
        ("bios7.bin", "df692a80a5b1bc90728bc3dfc76cd948"),
        ("bios9.bin", "a392174eb3e572fed6447e956bde4b25")]},
    {"system": "Dreamcast", "need": "obligatoria", "files": [
        ("dc/dc_boot.bin", "e10c53c2f8b90bab96ead2d368858623"),
        ("dc/dc_flash.bin", "0a93f7940c455905bea6e392dfde92a4")]},
]

_lock = threading.Lock()


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def count_roms(folder):
    """Cuenta juegos en una carpeta de sistema (sin partidas guardadas ni medios).
    Los .bin que acompanan a un .cue no cuentan como juego aparte."""
    files = [e for e in os.scandir(folder) if e.is_file() and not e.name.startswith(".")]
    roms = [e for e in files if Path(e.name).suffix.lower() not in NOT_ROMS
            and not Path(e.name).suffix.lower().startswith(".state")]
    has_cue = any(e.name.lower().endswith(".cue") for e in roms)
    if has_cue:
        roms = [e for e in roms if not e.name.lower().endswith(".bin")]
    size = sum(e.stat().st_size for e in files)
    return len(roms), size


def candidates_for(filename, existing):
    """Sistemas posibles para un archivo, priorizando carpetas que ya existen."""
    ext = Path(filename).suffix.lower()
    found = [s for s, (_, exts) in SYSTEMS.items() if ext in exts]
    found.sort(key=lambda s: s not in existing)
    return found, ext in GENERIC_EXTS or len(found) != 1


def scan(cfg):
    roms_path = Path(cfg["roms_path"]) if cfg["roms_path"] else None
    out = {"config": cfg, "connected": False, "systems": [], "inbox": [], "bios": [],
           "disk": None, "errors": []}

    existing = set()
    if roms_path and roms_path.is_dir():
        out["connected"] = True
        try:
            du = shutil.disk_usage(roms_path)
            out["disk"] = {"total": du.total, "used": du.used, "free": du.free}
        except OSError:
            pass
        for entry in sorted(os.scandir(roms_path), key=lambda e: e.name.lower()):
            if not entry.is_dir() or entry.name.lower() in SKIP_DIRS or entry.name.startswith("."):
                continue
            existing.add(entry.name)
            try:
                n, size = count_roms(entry.path)
            except OSError as exc:
                out["errors"].append(f"{entry.name}: {exc}")
                continue
            label = SYSTEMS.get(entry.name, (entry.name, []))[0]
            out["systems"].append({"id": entry.name, "label": label, "count": n, "size": size})
        out["bios"] = check_bios(roms_path / "bios")
    elif roms_path:
        out["errors"].append(f"No encuentro la carpeta de ROMs: {roms_path}")

    inbox = Path(cfg["inbox_path"]) if cfg["inbox_path"] else None
    if inbox and inbox.is_dir():
        for entry in sorted(os.scandir(inbox), key=lambda e: e.name.lower()):
            if not entry.is_file() or entry.name.startswith("."):
                continue
            cands, ambiguous = candidates_for(entry.name, existing)
            out["inbox"].append({"name": entry.name, "size": entry.stat().st_size,
                                 "candidates": cands, "ambiguous": ambiguous})
    out["all_systems"] = sorted(set(SYSTEMS) | existing)
    out["labels"] = {k: v[0] for k, v in SYSTEMS.items()}
    return out


def check_bios(bios_dir):
    present = {}
    if bios_dir.is_dir():
        for root, _, names in os.walk(bios_dir):
            for n in names:
                rel = os.path.relpath(os.path.join(root, n), bios_dir).replace("\\", "/")
                present[rel.lower()] = rel
    results = []
    for item in BIOS:
        files = []
        for name, md5 in item["files"]:
            path = bios_dir / name
            st = {"name": name, "status": "falta"}
            if path.is_file() and present.get(name.lower()) == name:
                try:
                    st["status"] = "ok" if md5_of(path) == md5 else "hash distinto"
                except OSError:
                    st["status"] = "error al leer"
            elif name.lower() in present:
                st["status"] = "mayusculas"
                st["found_as"] = present[name.lower()]
            files.append(st)
        ok = [f for f in files if f["status"] in ("ok", "hash distinto")]
        if item.get("group"):
            state = "ok" if ok else "falta"
        else:
            state = "ok" if len(ok) == len(files) else ("parcial" if ok else "falta")
        results.append({"system": item["system"], "need": item["need"], "state": state, "files": files})
    return results


def safe_child(base, name):
    """Evita que un nombre como '..\\algo' salga de la carpeta base."""
    base = Path(base).resolve()
    target = (base / name).resolve()
    if target.parent != base:
        raise ValueError(f"Nombre no permitido: {name}")
    return target


def transfer(cfg, items, mode):
    inbox, roms = cfg["inbox_path"], cfg["roms_path"]
    if not (inbox and roms and Path(roms).is_dir()):
        raise ValueError("Configura primero la carpeta de ROMs y la de entrada.")
    done, failed = [], []
    for it in items:
        try:
            system = it["system"]
            if not system or "/" in system or "\\" in system or system.startswith("."):
                raise ValueError("Sistema no valido")
            src = safe_child(inbox, it["name"])
            dest_dir = safe_child(roms, system)
            dest_dir.mkdir(exist_ok=True)
            dest = dest_dir / src.name
            if dest.exists():
                raise FileExistsError("ya existe en la consola")
            (shutil.move if mode == "move" else shutil.copy2)(str(src), str(dest))
            done.append(it["name"])
        except Exception as exc:  # noqa: BLE001 — se informa en la interfaz
            failed.append({"name": it.get("name"), "error": str(exc)})
    return {"done": done, "failed": failed}


def fix_bios_case(cfg, name, found_as):
    bios = Path(cfg["roms_path"]) / "bios"
    src = (bios / found_as).resolve()
    dst = (bios / name).resolve()
    if bios.resolve() not in src.parents or bios.resolve() not in dst.parents:
        raise ValueError("Ruta no permitida")
    tmp = src.with_name(src.name + ".tmp-rename")
    src.rename(tmp)  # dos pasos: Windows no distingue mayusculas
    tmp.rename(dst)


# ---------------------------------------------------------------- actualizaciones

def local_version():
    try:
        return json.loads(VERSION_FILE.read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError):
        return "0.0.0"


def vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def fetch(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "rom-dashboard", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def check_update(timeout=10):
    """Devuelve el manifiesto remoto si hay una version mas nueva, si no None."""
    manifest = json.loads(fetch(UPDATE_URL + "version.json", timeout))
    return manifest if vtuple(manifest["version"]) > vtuple(local_version()) else None


def apply_update(manifest):
    """Descarga todo, verifica SHA-256 y solo entonces reemplaza archivos.
    Nunca toca config.json ni el .bat (Windows lee el .bat mientras corre).
    La version anterior queda como *.old por si hay que volver atras."""
    staged = []
    try:
        for name, sha in manifest["files"].items():
            if not re.fullmatch(r"[\w][\w.-]*", name) or name in ("config.json", "version.json") \
                    or name.lower().endswith((".bat", ".cmd")):
                raise ValueError(f"Archivo no permitido en la actualizacion: {name}")
            data = fetch(UPDATE_URL + name)
            if hashlib.sha256(data).hexdigest() != sha:
                raise ValueError(f"{name}: la firma SHA-256 no coincide, actualizacion cancelada")
            tmp = APP_DIR / (name + ".new")
            tmp.write_bytes(data)
            staged.append((tmp, APP_DIR / name))
    except Exception:
        for tmp, _ in staged:
            tmp.unlink(missing_ok=True)
        raise
    for tmp, target in staged:
        if target.exists():
            os.replace(target, target.with_name(target.name + ".old"))
        os.replace(tmp, target)
    VERSION_FILE.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest["version"]


def restart():
    """Sale con RESTART_CODE; el .bat lo vuelve a abrir con la version nueva."""
    RESTART_FLAG.touch()
    print("Reiniciando con la version nueva...")
    os._exit(RESTART_CODE)


_update = {"available": None, "notes": None, "error": None, "just_updated": None}


def background_check():
    """Solo comprueba y avisa en la pagina; no instala nada."""
    try:
        m = check_update(timeout=8)
        _update["available"] = m and m["version"]
        _update["notes"] = m and m.get("notes")
    except Exception as exc:  # noqa: BLE001 — sin internet no es grave
        _update["error"] = f"No se pudo buscar actualizaciones: {exc}"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, (APP_DIR / "dashboard.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/status":
            with _lock:
                out = scan(load_config())
            out["version"] = local_version()
            out["update"] = _update
            self._send(200, out)
        else:
            self._send(404, {"error": "no encontrado"})

    def do_POST(self):
        # Solo aceptamos peticiones de la propia pagina (evita que otra web
        # abierta en el navegador mueva archivos).
        origin = self.headers.get("Origin", "")
        if origin and origin not in (f"http://{HOST}:{PORT}", f"http://localhost:{PORT}"):
            return self._send(403, {"error": "origen no permitido"})
        try:
            body = self._body()
            with _lock:
                cfg = load_config()
                if self.path == "/api/config":
                    for key in ("roms_path", "inbox_path"):
                        if key in body:
                            cfg[key] = str(body[key]).strip().strip('"')
                    if cfg["inbox_path"]:
                        Path(cfg["inbox_path"]).mkdir(parents=True, exist_ok=True)
                    save_config(cfg)
                    return self._send(200, {"ok": True})
                if self.path == "/api/transfer":
                    return self._send(200, transfer(cfg, body.get("items", []), body.get("mode", "copy")))
                if self.path == "/api/bios/rename":
                    fix_bios_case(cfg, body["name"], body["found_as"])
                    return self._send(200, {"ok": True})
                if self.path == "/api/update/check":
                    _update["error"] = None
                    background_check()
                    return self._send(200, {"update": _update, "version": local_version()})
                if self.path == "/api/update/apply":
                    m = check_update()
                    if not m:
                        return self._send(200, {"updated": False})
                    apply_update(m)
                    threading.Timer(0.5, restart).start()
                    return self._send(200, {"updated": True, "version": m["version"]})
                if self.path == "/api/open":
                    target = cfg.get(body.get("which", ""), "")
                    if target and os.name == "nt" and Path(target).is_dir():
                        os.startfile(target)  # abre el Explorador de Windows
                    return self._send(200, {"ok": True})
            self._send(404, {"error": "no encontrado"})
        except Exception as exc:  # noqa: BLE001
            self._send(400, {"error": str(exc)})


def main():
    reopened = RESTART_FLAG.exists()  # reinicio tras actualizar: la pagina ya esta abierta
    if reopened:
        RESTART_FLAG.unlink()
        _update["just_updated"] = local_version()
    threading.Thread(target=background_check, daemon=True).start()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}"
    print(f"ROM Dashboard v{local_version()} en {url}  (cierra esta ventana para salir)")
    if "--no-browser" not in sys.argv and not reopened:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
