#!/usr/bin/env python3
"""Export an architecture spec to a **draw.io / diagrams.net** file — the same geometry the
SVG renderer produces, but as an *editable* mxGraph document.

Why a dedicated exporter (rather than "import the SVG into draw.io"): draw.io can only embed
an SVG as a flat image. To get a diagram whose boxes you can drag, recolour, relabel and
reconnect, each node must become an mxCell **vertex** and each wire an mxCell **edge**. This
module walks the spec and emits exactly that, **reusing** ``_archviz``'s node geometry,
auto-fitted zone boxes (:func:`_archviz.group_box`) and strictly-orthogonal edge routing
(:func:`_archviz.route_edge`) — so the ``.drawio`` matches the ``.svg`` on first open and the
two backends can never drift.

Fidelity choices:

* **Icons are the exact ``diagrams``-package PNGs, base64-embedded** as ``shape=image``
  vertices (the same bytes the SVG uses). Every key in the ``_ICONS`` vocabulary therefore
  renders identically — including ``snowflake`` / ``entra`` / ``agent`` (Q) / ``tools``
  (Toolkit), which have no clean native draw.io shape — and the file is self-contained (no
  dependency on draw.io's AWS/GCP/Azure shape libraries being installed or matching). Each
  vertex is still fully editable.
* **Edges carry the renderer's computed waypoints** (the polished orthogonal route, with
  perpendicular run-in/out), with exit/entry pinned to the same icon faces the SVG uses.
* **Zones** become rounded background rectangles (emitted first → behind the icons), dashed
  for sub-zones, matching the SVG.

One ``.drawio`` per spec (a single ``<diagram>`` tab), mirroring the per-plane ``.svg``; pass a
list of specs to :func:`write_drawio_multi` for one multi-tab file.
"""
from __future__ import annotations

import html
from pathlib import Path

import _archviz as A

IC = A.IC


def _av(s) -> str:
    """Escape for an XML attribute (draw.io ``value=`` / ``style=`` / ``name=``)."""
    return html.escape(str(s), quote=True)


def _clean_label(label: str, n) -> str:
    """Drop a step number the spec baked into the label text — some specs set both ``n`` and a
    ``"3 …"`` label, which the SVG hides only because its badge is a distinct circle. We show
    the number once (as the circular badge) so the edge label reads cleanly."""
    if n is not None and label:
        for pre in (f"{n} ", f"{n}. ", f"{n}) ", f"{n}: "):
            if label.startswith(pre):
                return label[len(pre):]
    return label


def _label_html(title: str, sub: str) -> str:
    """A node's two-line caption as draw.io HTML — title in ink, sub smaller + grey."""
    t = html.escape(title or "")
    if not sub:
        return t
    return f'{t}<br><font style="font-size:9px;" color="{A.SUB}">{html.escape(sub)}</font>'


def _img_uri(key: str) -> str:
    """The icon as draw.io's embedded-image form ``data:image/png,<base64>``. draw.io style
    strings are ``;``-delimited, so the standard ``data:image/png;base64,…`` URI would have its
    ``;base64`` mis-parsed as a separate style token — draw.io's own embed drops it, using a
    bare comma before the base64. We match that."""
    return A.uri(key).replace(";base64,", ",", 1)


def _node_style(n: dict) -> str:
    """``shape=image`` style for a node, with the caption placed on the same side the SVG
    uses (``below`` default, or ``left``/``right``)."""
    style = (f"shape=image;aspect=fixed;imageAspect=0;image={_img_uri(n['icon'])};"
             f"html=1;fontSize=11;fontStyle=1;fontColor={A.INK};")
    pos = n.get("label", "below")
    if pos == "left":
        return style + "verticalLabelPosition=middle;verticalAlign=middle;labelPosition=left;align=right;spacingRight=6;"
    if pos == "right":
        return style + "verticalLabelPosition=middle;verticalAlign=middle;labelPosition=right;align=left;spacingLeft=6;"
    return style + "verticalLabelPosition=bottom;verticalAlign=top;labelPosition=center;align=center;"


def _side_frac(pt: tuple, n: dict) -> tuple:
    """Where a wire touches a node, as (fx, fy) fractions of its icon box — so draw.io pins
    the edge to the *same* face the SVG used (incl. axis-snapped corner anchors)."""
    fx = min(1.0, max(0.0, (pt[0] - (n["x"] - IC / 2)) / IC))
    fy = min(1.0, max(0.0, (pt[1] - (n["y"] - IC / 2)) / IC))
    return round(fx, 4), round(fy, 4)


def _edge_style(kind: str, src_f: tuple, dst_f: tuple) -> str:
    stroke, width, dash, _m = A.KIND[kind]
    s = ("edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;jettySize=auto;"
         "endArrow=block;endFill=1;startArrow=none;"
         f"strokeColor={stroke};strokeWidth={width};")
    if dash:
        s += f"dashed=1;dashPattern={dash};"
    s += f"exitX={src_f[0]};exitY={src_f[1]};exitDx=0;exitDy=0;"
    s += f"entryX={dst_f[0]};entryY={dst_f[1]};entryDx=0;entryDy=0;"
    fc = stroke if kind == "id" else A.SUB                # blue id labels, grey otherwise
    s += f"fontSize=10;fontColor={fc};labelBackgroundColor=#FFFFFF;"
    return s


def _cell(cid: str, value: str, style: str, x, y, w, h) -> str:
    return (f'        <mxCell id="{cid}" value="{value}" style="{style}" vertex="1" parent="1">\n'
            f'          <mxGeometry x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" as="geometry"/>\n'
            f'        </mxCell>')


def _diagram_body(spec: dict, pfx: str) -> list[str]:
    """The ``<root>`` cells for one spec (ids namespaced by ``pfx`` so several specs can share
    a multi-tab file). Order = title/legend, zones, nodes, edges — so wires sit on top and
    zones behind, as in the SVG."""
    W, H = spec["size"]
    nodes = spec["nodes"]
    icon_boxes = {k: A._icon_box(n) for k, n in nodes.items()}
    out: list[str] = ['        <mxCell id="0"/>',
                      '        <mxCell id="1" parent="0"/>']

    # title + subtitle (free text, top-left — mirrors the SVG header)
    out.append(_cell(f"{pfx}-title", _av(spec["title"]),
                     f"text;html=1;align=left;verticalAlign=middle;fontSize=20;fontColor={A.INK};",
                     20, 14, max(220, len(spec["title"]) * 12), 28))
    if spec.get("subtitle"):
        out.append(_cell(f"{pfx}-sub", _av(spec["subtitle"]),
                         f"text;html=1;align=left;verticalAlign=middle;fontSize=12;fontColor={A.SUB};",
                         20, 44, max(220, len(spec["subtitle"]) * 6.5), 16))

    # edge-type legend (top-right) — only the kinds this diagram uses
    present = {e.get("kind", "req") for e in spec.get("edges", [])}
    lx = W - 374
    for i, (kind, lbl) in enumerate(
            [(k, l) for k, l in (("req", "request"), ("id", "identity / token"),
                                 ("sup", "supporting")) if k in present]):
        stroke, _w, dash, _m = A.KIND[kind]
        ls = f"shape=line;strokeColor={stroke};strokeWidth=2;html=1;"
        if dash:
            ls += f"dashed=1;dashPattern={dash};"
        out.append(_cell(f"{pfx}-legl{i}", "", ls, lx, 30, 26, 8))
        out.append(_cell(f"{pfx}-legt{i}", _av(lbl),
                         f"text;html=1;align=left;verticalAlign=middle;fontSize=11;fontColor={A.SUB};",
                         lx + 32, 27, len(lbl) * 6.5 + 6, 14))
        lx += 36 + 10 + len(lbl) * 6.2

    # zones (behind the icons)
    for i, g in enumerate(spec.get("groups", [])):
        x, y, w, h = A.group_box(g, nodes, W, H)
        dashed = g.get("dashed", False)
        col = "#879196" if dashed else A.INK
        gs = (f"rounded=1;arcSize=4;html=1;fillColor=none;strokeColor={col};"
              f"strokeWidth={1.2 if dashed else 1.6};verticalAlign=top;align=left;"
              f"spacingLeft=10;spacingTop=3;fontSize=12;fontColor={col};")
        if dashed:
            gs += "dashed=1;dashPattern=4 4;"
        out.append(_cell(f"{pfx}-g{i}", _av(g["label"]), gs, x, y, w, h))

    # nodes — the caption is HTML (title + smaller grey sub); draw.io stores HTML labels
    # entity-escaped in the value attribute (it unescapes once, then renders the markup)
    for k, n in nodes.items():
        out.append(_cell(f"{pfx}-n-{k}", _av(_label_html(n.get("title", ""), n.get("sub", ""))),
                         _node_style(n), n["x"] - IC / 2, n["y"] - IC / 2, IC, IC))

    # edges — reuse the renderer's exact routing (accumulate placed_segs in edge order)
    placed_segs: list = []
    for i, e in enumerate(spec.get("edges", [])):
        geo = A.route_edge(e, nodes, icon_boxes, placed_segs)
        pts = geo["pts"]
        placed_segs += [(pts[j], pts[j + 1]) for j in range(len(pts) - 1)]
        s_node, d_node = nodes[e["s"]], nodes[e["d"]]
        style = _edge_style(e.get("kind", "req"),
                            _side_frac(geo["src"], s_node), _side_frac(geo["dst"], d_node))
        label, n = e.get("label", ""), e.get("n")
        clean = _clean_label(label, n)
        eid = f"{pfx}-e{i}"
        waypts = pts[1:-1]                               # interior bends; ends come from exit/entry
        pts_xml = ""
        if waypts:
            inner = "".join(f'<mxPoint x="{px:.0f}" y="{py:.0f}"/>' for px, py in waypts)
            pts_xml = f'<Array as="points">{inner}</Array>'
        out.append(
            f'        <mxCell id="{eid}" value="{_av(clean)}" style="{style}" '
            f'edge="1" parent="1" source="{pfx}-n-{e["s"]}" target="{pfx}-n-{e["d"]}">\n'
            f'          <mxGeometry relative="1" as="geometry">{pts_xml}</mxGeometry>\n'
            f'        </mxCell>')
        if n is not None:                                # step badge: a dark numbered circle, as in the SVG —
            off = -(len(clean) * (A.CHAR_E / 2) + 11) if clean else 0   # sit just left of the centred label
            out.append(
                f'        <mxCell id="{eid}-b" value="{_av(n)}" '
                f'style="ellipse;html=1;fillColor={A.INK};strokeColor=none;fontColor=#FFFFFF;'
                f'fontSize=9;fontStyle=1;" vertex="1" connectable="0" parent="{eid}">\n'
                f'          <mxGeometry x="0" y="0" relative="1" width="18" height="18" as="geometry">\n'
                f'            <mxPoint x="{off:.0f}" y="0" as="offset"/>\n'
                f'          </mxGeometry>\n'
                f'        </mxCell>')
    return out


def _diagram(spec: dict) -> str:
    W, H = spec["size"]
    body = "\n".join(_diagram_body(spec, spec["key"]))
    return (
        f'  <diagram name="{_av(spec["title"])}" id="{_av(spec["key"])}">\n'
        f'    <mxGraphModel dx="{W:.0f}" dy="{H:.0f}" grid="1" gridSize="10" guides="1" '
        f'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
        f'pageWidth="{W:.0f}" pageHeight="{H:.0f}" math="0" shadow="0">\n'
        f'      <root>\n{body}\n      </root>\n'
        f'    </mxGraphModel>\n'
        f'  </diagram>')


def to_drawio(spec: dict) -> str:
    """One spec → a complete single-tab ``.drawio`` document."""
    return ('<mxfile host="app.diagrams.net" type="device">\n'
            + _diagram(spec) + '\n</mxfile>\n')


def write_drawio(spec: dict, out_dir: Path) -> Path:
    """Write ``<key>-architecture.drawio`` (one tab), parity with the per-plane ``.svg``."""
    p = Path(out_dir) / f'{spec["key"]}-architecture.drawio'
    p.write_text(to_drawio(spec))
    return p


def write_drawio_multi(specs: list[dict], out_dir: Path, name: str = "architecture") -> Path:
    """Write one multi-tab ``<name>.drawio`` with every spec as its own diagram tab."""
    p = Path(out_dir) / f"{name}.drawio"
    p.write_text('<mxfile host="app.diagrams.net" type="device">\n'
                 + "\n".join(_diagram(s) for s in specs) + '\n</mxfile>\n')
    return p
