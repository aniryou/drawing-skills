#!/usr/bin/env python3
"""Render cloud-architecture diagrams (AWS · GCP · Azure) from a specs.json (list of specs).

    uv run --with diagrams python generate.py [specs.json] [out_dir] [-f all|svg|png|drawio]

Defaults: ``./specs.json`` next to this script, output written beside the specs file, and
``--format all``. Per spec it writes ``<key>-architecture.svg`` (+ a ``.png`` raster if
``rsvg-convert`` is on PATH) and an **editable** ``<key>-architecture.drawio`` (draw.io /
diagrams.net), plus one combined multi-tab ``architecture.drawio``. Pass ``--format`` to emit
only one format (``png`` still rasterises via a transient SVG; the combined ``.drawio`` is only
written when draw.io is in the selection). Reproducible: same specs.json → byte-identical
output. Edit the spec, never the generated files. See ``_archviz.py`` for the node / edge /
group grammar and the icon vocabulary; ``_drawio.py`` for the draw.io exporter.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # find the bundled _archviz.py / _drawio.py regardless of cwd
import _archviz as A  # noqa: E402
import _drawio as D  # noqa: E402

FORMATS = ("all", "svg", "png", "drawio")


def normalize(raw: dict) -> dict:
    """specs.json shape (nodes as a list, size as {w,h}) → the renderer's shape."""
    spec = dict(raw)
    spec["nodes"] = {n["key"]: {k: v for k, v in n.items() if k != "key"}
                     for n in raw["nodes"]}
    spec["size"] = (raw["size"]["w"], raw["size"]["h"])
    return spec


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Render cloud-architecture diagrams from a specs.json (SVG · PNG · draw.io).")
    ap.add_argument("specs", nargs="?", help="specs.json (default: ./specs.json beside this script)")
    ap.add_argument("out_dir", nargs="?", help="output directory (default: beside specs.json)")
    ap.add_argument("-f", "--format", choices=FORMATS, default="all",
                    help="which format to write (default: all = svg + png + drawio)")
    a = ap.parse_args()

    specs_path = Path(a.specs) if a.specs else HERE / "specs.json"
    out_dir = Path(a.out_dir) if a.out_dir else specs_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    want_svg = a.format in ("all", "svg")
    want_png = a.format in ("all", "png")
    want_drawio = a.format in ("all", "drawio")

    rsvg = shutil.which("rsvg-convert")
    specs = [normalize(raw) for raw in json.loads(specs_path.read_text())]
    for spec in specs:
        outs = []
        svg_path = out_dir / f'{spec["key"]}-architecture.svg'
        if want_svg or (want_png and rsvg):              # PNG is rasterised from the SVG
            svg_path.write_text(A.render(spec))
        if want_svg:
            outs.append(svg_path.name)
        if want_png and rsvg:
            w, h = spec["size"]
            png = svg_path.with_suffix(".png")
            subprocess.run([rsvg, "-w", str(w * 2), "-h", str(h * 2), str(svg_path), "-o", str(png)],
                           check=True)
            outs.append(png.name)
        if want_png and not want_svg and svg_path.exists():
            svg_path.unlink()                            # the SVG was only a transient for the PNG
        if want_drawio:
            outs.append(D.write_drawio(spec, out_dir).name)
        print(f'{spec["key"]}: {len(spec["nodes"])} nodes, {len(spec.get("edges", []))} edges '
              f'-> {", ".join(outs) or "(nothing)"}')
    if want_drawio:
        combined = D.write_drawio_multi(specs, out_dir)
        print(f"+ {combined.name}: {len(specs)} tabs (all planes, one file)")
    if want_png and not rsvg:
        print("rsvg-convert not found — PNG skipped "
              "(brew install librsvg / apt install librsvg2-bin to enable).")


if __name__ == "__main__":
    main()
