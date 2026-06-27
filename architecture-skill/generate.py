#!/usr/bin/env python3
"""Render cloud-architecture diagrams (AWS · GCP · Azure) from a specs.json (list of specs).

    uv run --with diagrams python generate.py [specs.json] [out_dir]

Defaults: ``./specs.json`` next to this script, output written beside the specs file.
Per spec it writes ``<key>-architecture.svg`` (+ a ``.png`` raster if ``rsvg-convert`` is on
PATH) and an **editable** ``<key>-architecture.drawio`` (draw.io / diagrams.net), plus one
combined multi-tab ``architecture.drawio``. Reproducible: same specs.json → byte-identical
output. Edit the spec, never the generated files. See ``_archviz.py`` for the node / edge /
group grammar and the icon vocabulary; ``_drawio.py`` for the draw.io exporter.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # find the bundled _archviz.py / _drawio.py regardless of cwd
import _archviz as A  # noqa: E402
import _drawio as D  # noqa: E402


def normalize(raw: dict) -> dict:
    """specs.json shape (nodes as a list, size as {w,h}) → the renderer's shape."""
    spec = dict(raw)
    spec["nodes"] = {n["key"]: {k: v for k, v in n.items() if k != "key"}
                     for n in raw["nodes"]}
    spec["size"] = (raw["size"]["w"], raw["size"]["h"])
    return spec


def main() -> None:
    specs_path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "specs.json"
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else specs_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    rsvg = shutil.which("rsvg-convert")
    specs = [normalize(raw) for raw in json.loads(specs_path.read_text())]
    for spec in specs:
        svg = A.write(spec, out_dir)
        drawio = D.write_drawio(spec, out_dir)
        print(f"wrote {svg.name}: {len(spec['nodes'])} nodes, {len(spec.get('edges', []))} edges")
        print(f"  + {drawio.name}")
        if rsvg:
            w, h = spec["size"]
            png = svg.with_suffix(".png")
            subprocess.run([rsvg, "-w", str(w * 2), "-h", str(h * 2), str(svg), "-o", str(png)],
                           check=True)
            print(f"  + {png.name}")
    combined = D.write_drawio_multi(specs, out_dir)
    print(f"wrote {combined.name}: {len(specs)} tabs (all planes, one file)")
    if not rsvg:
        print("rsvg-convert not found — SVGs written; PNG fallbacks skipped "
              "(brew install librsvg / apt install librsvg2-bin to enable).")


if __name__ == "__main__":
    main()
