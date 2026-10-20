"""Genera version.json para publicar una version nueva.

Uso:  python make_manifest.py 1.1.0 "Que cambia en esta version"
Luego commit + push de todo a main: los dashboards instalados veran el aviso.
"""
import hashlib
import json
import sys
from pathlib import Path

# Archivos que se actualizan solos. El .bat y config.json quedan fuera a proposito.
FILES = ["rom_dashboard.py", "dashboard.html", "LEEME.txt"]

here = Path(__file__).resolve().parent
version, notes = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "")
manifest = {
    "version": version,
    "notes": notes,
    "files": {f: hashlib.sha256((here / f).read_bytes()).hexdigest() for f in FILES},
}
(here / "version.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps(manifest, indent=2, ensure_ascii=False))
