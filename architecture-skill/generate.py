#!/usr/bin/env python3
"""Render cloud-architecture SVGs (AWS · GCP · Azure) from a specs.json (list of specs).

    uv run --with diagrams python generate.py [specs.json] [out_dir]

Defaults: ``./specs.json`` next to this script, output written beside the specs file.
Writes ``<key>-architecture.svg`` per spec (+ a ``.png`` raster if ``rsvg-convert`` is on
PATH). Reproducible: same specs.json → byte-identical SVGs. Edit the spec, never the SVG.
See ``_archviz.py`` for the node / edge / group grammar and the icon vocabulary.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # find the bundled _archviz.py regardless of cwd
import _archviz as A  # noqa: E402


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
    for raw in json.loads(specs_path.read_text()):
        spec = normalize(raw)
        svg = A.write(spec, out_dir)
        print(f"wrote {svg.name}: {len(spec['nodes'])} nodes, {len(spec.get('edges', []))} edges")
        if rsvg:
            w, h = spec["size"]
            png = svg.with_suffix(".png")
            subprocess.run([rsvg, "-w", str(w * 2), "-h", str(h * 2), str(svg), "-o", str(png)],
                           check=True)
            print(f"  + {png.name}")
    if not rsvg:
        print("rsvg-convert not found — SVGs written; PNG fallbacks skipped "
              "(brew install librsvg / apt install librsvg2-bin to enable).")


if __name__ == "__main__":
    main()
