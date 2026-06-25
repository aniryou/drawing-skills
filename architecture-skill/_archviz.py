#!/usr/bin/env python3
"""Shared renderer for the cloud-architecture SVGs (AWS · GCP · Azure).

The visual language is left-to-right, **official cloud-provider icons** from the
``diagrams`` package (base64-embedded so GitHub renders the SVG inline) — drawn from
**any hyperscaler** (AWS, Google Cloud, Azure) plus SaaS / on-prem tooling — joined by
elbow connectors, grouped into rounded zones, with the 3-kind edge legend
(request / identity / supporting). Authoring is declarative so a set of diagrams stays
consistent:

* a node carries a pixel **centre** ``(x, y)`` + an icon key + a 2-line label;
* an **edge references node KEYS** and a side anchor (``l r t b`` or corners ``tl tr bl br``);
  endpoints are computed from the nodes, so no edge coordinates are hand-typed;
* a **group spans a set of node keys** (auto bounding-box + padding) or an explicit bbox;
* edges may carry a **numbered step badge** (the dark circle from the hand-drawn diagrams).

The renderer does its own overlap avoidance so a spec rarely needs hand-tuning:

* **layered draw order** — every text label is painted *after* every icon, so an icon can
  never hide a label;
* **keep-out-aware edge labels** — a label is slid along its wire (and nudged off it) until
  it clears every node's icon+label box, prior labels, **and other edges' wires** (so a
  label never lands on an unrelated connector), instead of blindly sitting at the leg midpoint;
* **label-extent zones** — a group's rounded rect is fitted around each member's *rendered
  text*, not just its icon, so node titles never poke through a zone edge;
* **strictly orthogonal wires** — every leg is horizontal or vertical: an auto-routed elbow
  whose leg would cross an icon is re-jogged (or its elbow flipped) to take the **shortest
  clear** path, and any diagonal a ``via`` waypoint would introduce is split into a right-angle
  L whose bend is steered clear of icons and already-placed wires (no acute angles, ever).

Only the ``diagrams`` package is needed (for the icon PNGs); no Graphviz. The optional
PNG raster uses ``rsvg-convert`` (``brew install librsvg``) or ``qlmanage`` on macOS.
Edit the per-plane specs in ``generate.py`` / ``specs.json`` and re-run; don't hand-edit the SVG.
"""
from __future__ import annotations

import base64
import math
import os
from pathlib import Path

import diagrams

# ── Official cloud icons from the `diagrams` package — all hyperscalers ────────────
# Keys are short, stable handles you reference from a spec's `node.icon`. The value is
# the (module, class) of an official icon in the `diagrams` PyPI package; the renderer
# imports it and base64-embeds its bundled PNG into the SVG. Three parallel families so
# the same architecture can be drawn on any cloud:
#   • AWS    — bare keys (s3, lambda, rds…), kept stable for back-compat.
#   • GCP    — `gcp_` prefix (gcp_gcs, gcp_functions, gcp_sql…).
#   • Azure  — `az_`  prefix (az_blob, az_functions, az_sql…).
# Cloud-neutral actors / SaaS / on-prem tools have no prefix (user, github, snowflake…).
# Need another service? Find its class — e.g.
#   uv run --with diagrams python -c "import diagrams.gcp.database as m; print(dir(m))"
# — and add one line in the matching block below.
_PARENT = Path(os.path.abspath(os.path.dirname(diagrams.__file__))).parent
_ICONS = {
    # ── Cloud-neutral: actors, SaaS, on-prem / dev tooling ────────────────────────
    "user": ("diagrams.aws.general", "User"),
    "users": ("diagrams.aws.general", "Users"),
    "client": ("diagrams.aws.general", "Client"),
    "snowflake": ("diagrams.saas.analytics", "Snowflake"),
    "github": ("diagrams.onprem.vcs", "Github"),
    "ghactions": ("diagrams.onprem.ci", "GithubActions"),
    "terraform": ("diagrams.onprem.iac", "Terraform"),
    "python": ("diagrams.programming.language", "Python"),

    # ── AWS ───────────────────────────────────────────────────────────────────────
    # compute
    "ec2": ("diagrams.aws.compute", "EC2"),
    "lambda": ("diagrams.aws.compute", "Lambda"),
    "ecs": ("diagrams.aws.compute", "ElasticContainerService"),
    "eks": ("diagrams.aws.compute", "ElasticKubernetesService"),
    "fargate": ("diagrams.aws.compute", "Fargate"),
    "apprunner": ("diagrams.aws.compute", "AppRunner"),
    "ecr": ("diagrams.aws.compute", "EC2ContainerRegistry"),
    # storage / database
    "s3": ("diagrams.aws.storage", "SimpleStorageServiceS3"),
    "db": ("diagrams.aws.database", "Database"),          # cloud-neutral generic DB
    "rds": ("diagrams.aws.database", "RDS"),
    "aurora": ("diagrams.aws.database", "Aurora"),
    "dynamodb": ("diagrams.aws.database", "Dynamodb"),
    "elasticache": ("diagrams.aws.database", "ElastiCache"),
    # network
    "apigw": ("diagrams.aws.network", "APIGateway"),
    "elb": ("diagrams.aws.network", "ElasticLoadBalancing"),
    "alb": ("diagrams.aws.network", "ALB"),
    "cloudfront": ("diagrams.aws.network", "CloudFront"),
    "route53": ("diagrams.aws.network", "Route53"),
    "vpc": ("diagrams.aws.network", "VPC"),
    # integration / messaging
    "sns": ("diagrams.aws.integration", "SimpleNotificationServiceSns"),
    "sqs": ("diagrams.aws.integration", "SimpleQueueServiceSqs"),
    "eventbridge": ("diagrams.aws.integration", "Eventbridge"),
    "stepfunctions": ("diagrams.aws.integration", "StepFunctions"),
    "ses": ("diagrams.aws.engagement", "SimpleEmailServiceSes"),
    # analytics / ML
    "redshift": ("diagrams.aws.analytics", "Redshift"),
    "athena": ("diagrams.aws.analytics", "Athena"),
    "glue": ("diagrams.aws.analytics", "Glue"),
    "kinesis": ("diagrams.aws.analytics", "Kinesis"),
    "emr": ("diagrams.aws.analytics", "EMR"),
    "bedrock": ("diagrams.aws.ml", "Bedrock"),
    "sagemaker": ("diagrams.aws.ml", "Sagemaker"),
    # security / identity
    "iam": ("diagrams.aws.security", "IdentityAndAccessManagementIam"),
    "cognito": ("diagrams.aws.security", "Cognito"),
    "secrets": ("diagrams.aws.security", "SecretsManager"),
    "kms": ("diagrams.aws.security", "KMS"),
    "shield": ("diagrams.aws.security", "Shield"),
    "waf": ("diagrams.aws.security", "WAF"),
    "guardduty": ("diagrams.aws.security", "Guardduty"),
    # management / observability
    "cloudwatch": ("diagrams.aws.management", "Cloudwatch"),
    "cwlogs": ("diagrams.aws.management", "CloudwatchLogs"),
    "alarm": ("diagrams.aws.management", "CloudwatchAlarm"),
    "xray": ("diagrams.aws.devtools", "XRay"),

    # ── Google Cloud (GCP) ────────────────────────────────────────────────────────
    # compute
    "gcp_gce": ("diagrams.gcp.compute", "ComputeEngine"),
    "gcp_functions": ("diagrams.gcp.compute", "Functions"),
    "gcp_run": ("diagrams.gcp.compute", "Run"),
    "gcp_gke": ("diagrams.gcp.compute", "KubernetesEngine"),
    "gcp_appengine": ("diagrams.gcp.compute", "AppEngine"),
    "gcp_gcr": ("diagrams.gcp.devtools", "ContainerRegistry"),
    # storage / database
    "gcp_gcs": ("diagrams.gcp.storage", "GCS"),
    "gcp_sql": ("diagrams.gcp.database", "SQL"),
    "gcp_spanner": ("diagrams.gcp.database", "Spanner"),
    "gcp_firestore": ("diagrams.gcp.database", "Firestore"),
    "gcp_bigtable": ("diagrams.gcp.database", "Bigtable"),
    "gcp_memorystore": ("diagrams.gcp.database", "Memorystore"),
    # network
    "gcp_apigw": ("diagrams.gcp.api", "APIGateway"),
    "gcp_apigee": ("diagrams.gcp.api", "Apigee"),
    "gcp_lb": ("diagrams.gcp.network", "LoadBalancing"),
    "gcp_cdn": ("diagrams.gcp.network", "CDN"),
    "gcp_dns": ("diagrams.gcp.network", "DNS"),
    "gcp_vpc": ("diagrams.gcp.network", "VirtualPrivateCloud"),
    "gcp_armor": ("diagrams.gcp.network", "Armor"),
    # analytics / ML
    "gcp_bigquery": ("diagrams.gcp.analytics", "BigQuery"),
    "gcp_pubsub": ("diagrams.gcp.analytics", "PubSub"),
    "gcp_dataflow": ("diagrams.gcp.analytics", "Dataflow"),
    "gcp_dataproc": ("diagrams.gcp.analytics", "Dataproc"),
    "gcp_vertex": ("diagrams.gcp.ml", "VertexAI"),
    # security / identity
    "gcp_iam": ("diagrams.gcp.security", "Iam"),
    "gcp_secrets": ("diagrams.gcp.security", "SecretManager"),
    "gcp_kms": ("diagrams.gcp.security", "KMS"),
    # ops
    "gcp_monitoring": ("diagrams.gcp.operations", "Monitoring"),
    "gcp_logging": ("diagrams.gcp.operations", "Logging"),
    "gcp_build": ("diagrams.gcp.devtools", "Build"),

    # ── Microsoft Azure ───────────────────────────────────────────────────────────
    # compute
    "az_vm": ("diagrams.azure.compute", "VM"),
    "az_functions": ("diagrams.azure.compute", "FunctionApps"),
    "az_appservice": ("diagrams.azure.compute", "AppServices"),
    "az_aks": ("diagrams.azure.compute", "AKS"),
    "az_containerapps": ("diagrams.azure.compute", "ContainerApps"),
    "az_acr": ("diagrams.azure.compute", "ContainerRegistries"),
    # storage / database
    "az_blob": ("diagrams.azure.storage", "BlobStorage"),
    "az_sql": ("diagrams.azure.database", "SQLDatabases"),
    "az_cosmos": ("diagrams.azure.database", "CosmosDb"),
    "az_redis": ("diagrams.azure.database", "CacheForRedis"),
    "az_datafactory": ("diagrams.azure.analytics", "DataFactories"),
    # network
    "az_apim": ("diagrams.azure.integration", "APIManagement"),
    "az_lb": ("diagrams.azure.network", "LoadBalancers"),
    "az_appgw": ("diagrams.azure.network", "ApplicationGateway"),
    "az_cdn": ("diagrams.azure.network", "CDNProfiles"),
    "az_frontdoor": ("diagrams.azure.network", "FrontDoors"),
    "az_dns": ("diagrams.azure.network", "DNSZones"),
    "az_vnet": ("diagrams.azure.network", "VirtualNetworks"),
    "az_firewall": ("diagrams.azure.network", "Firewall"),
    # integration / messaging
    "az_servicebus": ("diagrams.azure.integration", "ServiceBus"),
    "az_eventhub": ("diagrams.azure.analytics", "EventHubs"),
    "az_eventgrid": ("diagrams.azure.integration", "EventGridTopics"),
    "az_logicapps": ("diagrams.azure.integration", "LogicApps"),
    # analytics / ML
    "az_synapse": ("diagrams.azure.analytics", "SynapseAnalytics"),
    "az_databricks": ("diagrams.azure.analytics", "Databricks"),
    "az_ml": ("diagrams.azure.ml", "MachineLearningServiceWorkspaces"),
    "az_openai": ("diagrams.azure.ml", "AzureOpenAI"),
    "az_cognitive": ("diagrams.azure.ml", "CognitiveServices"),
    # security / identity
    "entra": ("diagrams.azure.identity", "ActiveDirectory"),   # Entra ID (Azure AD)
    "az_ad": ("diagrams.azure.identity", "ActiveDirectory"),   # alias of `entra`
    "az_keyvault": ("diagrams.azure.security", "KeyVaults"),
    "az_defender": ("diagrams.azure.security", "Defender"),
    # observability / devops
    "az_monitor": ("diagrams.azure.monitor", "Monitor"),
    "az_loganalytics": ("diagrams.azure.monitor", "LogAnalyticsWorkspaces"),
    "az_appinsights": ("diagrams.azure.monitor", "ApplicationInsights"),
    "az_devops": ("diagrams.azure.devops", "AzureDevops"),
    "az_pipelines": ("diagrams.azure.devops", "Pipelines"),
}


def _data_uri(key: str) -> str:
    mod, cls = _ICONS[key]
    c = getattr(__import__(mod, fromlist=[cls]), cls)
    raw = Path(os.path.join(_PARENT, c._icon_dir, c._icon)).read_bytes()
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


# cache the data-URIs lazily so a spec only pays for the icons it uses
_URI: dict[str, str] = {}


def uri(key: str) -> str:
    if key not in _URI:
        _URI[key] = _data_uri(key)
    return _URI[key]


INK = "#232F3E"   # AWS "squid ink" — node titles + cloud boundary
SUB = "#5F5E5A"   # subtitle / edge labels
IC = 52           # icon edge (px)
TITLE_DY = 16     # node-title baseline below the icon
SUB_DY = 30       # node-sub baseline below the icon
LBL_DROP = 36     # vertical room a 2-line "below" label occupies under an icon
CHAR_T = 6.7      # ~px per title char (12.5px font)
CHAR_S = 5.7      # ~px per sub char (10.5px font)
CHAR_E = 5.4      # ~px per edge-label char (10px font)

KIND = {  # stroke, width, dash, marker-id
    "req": ("#444441", 2.2, "", "ad"),
    "id": ("#185FA5", 1.6, "5 4", "ab"),
    "sup": ("#888780", 1.4, "", "ag"),
}


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ── geometry helpers ──────────────────────────────────────────────────────────
def _overlap(a: tuple, b: tuple, m: float = 0.0) -> bool:
    """True if axis-aligned boxes (x0,y0,x1,y1) overlap (with margin m)."""
    return not (a[2] + m < b[0] or b[2] + m < a[0]
                or a[3] + m < b[1] or b[3] + m < a[1])


def _icon_box(n: dict, m: float = 7.0) -> tuple:
    """The icon's bounding box (+margin) — the keep-out an edge wire must not cross."""
    cx, cy = n["x"], n["y"]
    return (cx - IC / 2 - m, cy - IC / 2 - m, cx + IC / 2 + m, cy + IC / 2 + m)


def _node_box(n: dict, pad: float = 0.0) -> tuple:
    """Full rendered footprint of a node — icon **plus its text label** — for zone
    fitting and edge-label keep-out."""
    cx, cy = n["x"], n["y"]
    pos = n.get("label", "below")
    tw = max(len(n.get("title", "")) * CHAR_T, len(n.get("sub", "")) * CHAR_S)
    x0, y0, x1, y1 = cx - IC / 2, cy - IC / 2, cx + IC / 2, cy + IC / 2
    if pos == "left":
        x0 = cx - IC / 2 - 8 - tw
        y0, y1 = min(y0, cy - 13), max(y1, cy + 15)
    elif pos == "right":
        x1 = cx + IC / 2 + 8 + tw
        y0, y1 = min(y0, cy - 13), max(y1, cy + 15)
    else:  # below
        x0, x1 = min(x0, cx - tw / 2), max(x1, cx + tw / 2)
        y1 = cy + IC / 2 + LBL_DROP
    return (x0 - pad, y0 - pad, x1 + pad, y1 + pad)


def _anchor(n: dict, side: str) -> tuple:
    x, y, h = n["x"], n["y"], IC / 2
    return {
        "l": (x - h, y), "r": (x + h, y), "t": (x, y - h), "b": (x, y + h),
        "tl": (x - h, y - h), "tr": (x + h, y - h),
        "bl": (x - h, y + h), "br": (x + h, y + h),
        "c": (x, y),
    }[side]


def _auto_sides(s: dict, d: dict) -> tuple:
    dx, dy = d["x"] - s["x"], d["y"] - s["y"]
    if abs(dx) >= abs(dy):
        return ("r", "l") if dx > 0 else ("l", "r")
    return ("b", "t") if dy > 0 else ("t", "b")


def _exit_axis(side: str, dx: float, dy: float) -> str:
    """'h' or 'v' — the axis an edge leaves / enters a node on (corners → dominant axis)."""
    if side in ("l", "r"):
        return "h"
    if side in ("t", "b"):
        return "v"
    return "h" if abs(dx) >= abs(dy) else "v"


def _ortho(x1: float, y1: float, ss: str, x2: float, y2: float, ds: str) -> list:
    """Right-angle (elbow) waypoints between two anchors, honouring their exit axes."""
    dx, dy = x2 - x1, y2 - y1
    so, do = _exit_axis(ss, dx, dy), _exit_axis(ds, -dx, -dy)
    if so == "h" and do == "h":      # H · V · H — leave/enter horizontally, jog at a column
        mx = (x1 + x2) / 2
        return [(mx, y1), (mx, y2)]
    if so == "v" and do == "v":      # V · H · V
        my = (y1 + y2) / 2
        return [(x1, my), (x2, my)]
    if so == "h":                    # H then V (single elbow)
        return [(x2, y1)]
    return [(x1, y2)]                # V then H (single elbow)


def _seg_hits(a: tuple, b: tuple, boxes: list) -> int:
    """How many keep-out boxes an axis-aligned segment a→b crosses (diagonals ignored)."""
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    hits = 0
    for x0, y0, x1, y1 in boxes:
        if abs(ay - by) < 0.5:                       # horizontal leg at y=ay
            if y0 <= ay <= y1 and min(ax, bx) <= x1 and max(ax, bx) >= x0:
                hits += 1
        elif abs(ax - bx) < 0.5:                     # vertical leg at x=ax
            if x0 <= ax <= x1 and min(ay, by) <= y1 and max(ay, by) >= y0:
                hits += 1
    return hits


def _route_hits(p: list, boxes: list) -> int:
    return sum(_seg_hits(p[i], p[i + 1], boxes) for i in range(len(p) - 1))


def _spread(a: float, b: float) -> list:
    """Candidate jog coordinates between/around a..b — midpoint first, then staggered
    inward and a little beyond either end, so a blocked elbow can step around an icon."""
    lo, hi = (a, b) if a <= b else (b, a)
    span = hi - lo
    out = [lo + f * span for f in (0.5, 0.38, 0.62, 0.28, 0.72, 0.16, 0.84)]
    out += [lo - 36, lo - 70, hi + 36, hi + 70]      # detour just outside the pair
    return out


def _leg_axis(a: tuple, b: tuple) -> str:
    return "h" if abs(b[0] - a[0]) >= abs(b[1] - a[1]) else "v"


def _path_len(pts: list) -> float:
    """Manhattan length of an axis-aligned polyline (shortest-route tie-break)."""
    return sum(abs(pts[i + 1][0] - pts[i][0]) + abs(pts[i + 1][1] - pts[i][1])
               for i in range(len(pts) - 1))


def _seg_overlap(a: tuple, b: tuple, c: tuple, d: tuple, tol: float = 9.0) -> float:
    """Co-linear overlap length of two axis-aligned segments a–b and c–d — how far they
    run shoulder-to-shoulder in the *same* lane (0 if perpendicular or in different lanes).
    Drives parallel wires into separate lanes; perpendicular crossings score 0."""
    ah, ch = abs(a[1] - b[1]) < 0.5, abs(c[1] - d[1]) < 0.5     # horizontal?
    av, cv = abs(a[0] - b[0]) < 0.5, abs(c[0] - d[0]) < 0.5     # vertical?
    if ah and ch and abs(a[1] - c[1]) <= tol:                  # both horizontal, shared y-lane
        ov = min(max(a[0], b[0]), max(c[0], d[0])) - max(min(a[0], b[0]), min(c[0], d[0]))
        return max(0.0, ov)
    if av and cv and abs(a[0] - c[0]) <= tol:                  # both vertical, shared x-lane
        ov = min(max(a[1], b[1]), max(c[1], d[1])) - max(min(a[1], b[1]), min(c[1], d[1]))
        return max(0.0, ov)
    return 0.0


def _placed_overlap(a: tuple, b: tuple, placed: list) -> float:
    """How far segment a–b runs co-linear (shoulder-to-shoulder) with any already-placed
    wire; overlaps under ~14px are ignored as incidental shared corners."""
    tot = 0.0
    for c, d in placed:
        o = _seg_overlap(a, b, c, d)
        if o > 14.0:
            tot += o
    return tot


def _route(x1: float, y1: float, ss: str, x2: float, y2: float, ds: str,
           obstacles: list) -> list:
    """Elbow waypoints that avoid the icon ``obstacles``: keep the simple route when it is
    clear, else search staggered jogs / a flipped elbow / a 2-bend detour and pick the
    route with, in order: fewest icon crossings, cleanest entry axes, **shortest length**,
    fewest bends — so a clear edge always takes the most direct orthogonal path."""
    base = _ortho(x1, y1, ss, x2, y2, ds)
    if _route_hits([(x1, y1), *base, (x2, y2)], obstacles) == 0:
        return base
    dx, dy = x2 - x1, y2 - y1
    so, do = _exit_axis(ss, dx, dy), _exit_axis(ds, -dx, -dy)
    cands = [base]
    if so == "h" and do == "h":
        cands += [[(mx, y1), (mx, y2)] for mx in _spread(x1, x2)]
    elif so == "v" and do == "v":
        cands += [[(x1, my), (x2, my)] for my in _spread(y1, y2)]
    else:                                            # single elbow — try both corners
        cands += [[(x2, y1)], [(x1, y2)]]
    # universal 2-bend escapes — used only when they cut obstacle hits (scored below)
    cands += [[(mx, y1), (mx, y2)] for mx in _spread(x1, x2)]
    cands += [[(x1, my), (x2, my)] for my in _spread(y1, y2)]

    def score(mids: list) -> tuple:
        pts = [(x1, y1), *mids, (x2, y2)]
        hits = _route_hits(pts, obstacles)
        axis_pen = (_leg_axis(pts[0], pts[1]) != so) + (_leg_axis(pts[-2], pts[-1]) != do)
        return (hits, axis_pen, _path_len(pts), len(mids))   # clear → clean axes → shortest → few bends

    return min(cands, key=score)


def _simplify(pts: list) -> list:
    """Drop exact-duplicate points and merge co-linear runs (a–b–c on one line → a–c)."""
    out: list = []
    for p in pts:
        if out and abs(out[-1][0] - p[0]) < 0.5 and abs(out[-1][1] - p[1]) < 0.5:
            continue
        out.append(p)
    i = 1
    while i < len(out) - 1:
        a, b, c = out[i - 1], out[i], out[i + 1]
        if (abs(a[0] - b[0]) < 0.5 and abs(b[0] - c[0]) < 0.5) or \
           (abs(a[1] - b[1]) < 0.5 and abs(b[1] - c[1]) < 0.5):
            out.pop(i)
        else:
            i += 1
    return out


def _orthogonalize(pts: list, so: str, do: str, obstacles: list, placed: list = ()) -> list:
    """Guarantee every segment is axis-aligned: replace each diagonal a→b with an L (one
    inserted corner). Pick the corner that (1) crosses fewer icon keep-outs and (2) runs
    less alongside an already-placed wire; tie-broken toward the source exit axis ``so``
    (first leg) / dest entry axis ``do`` (last leg). A no-op for already-orthogonal routes
    — the safety net that kills acute-angle wires when a ``via`` waypoint isn't aligned
    with its anchor, while steering the inserted bend clear of parallel wires."""
    if len(pts) < 2:
        return pts
    out = [pts[0]]
    n = len(pts)
    for i in range(1, n):
        a, b = out[-1], pts[i]
        if abs(a[0] - b[0]) < 0.5 or abs(a[1] - b[1]) < 0.5:
            out.append(b)                            # already orthogonal / zero-length
            continue
        c_v, c_h = (a[0], b[1]), (b[0], a[1])        # vertical-first vs horizontal-first corner
        kv = (_seg_hits(a, c_v, obstacles) + _seg_hits(c_v, b, obstacles),
              _placed_overlap(a, c_v, placed) + _placed_overlap(c_v, b, placed))
        kh = (_seg_hits(a, c_h, obstacles) + _seg_hits(c_h, b, obstacles),
              _placed_overlap(a, c_h, placed) + _placed_overlap(c_h, b, placed))
        if i == 1:
            pref_v = so == "v"                       # leave on the source axis
        elif i == n - 1:
            pref_v = do == "h"                       # enter on dest axis (h ⇒ last leg horiz ⇒ c_v)
        else:
            pref_v = abs(out[-2][1] - a[1]) < 0.5    # previous leg horizontal ⇒ now go vertical
        corner = c_v if (kv < kh or (kv == kh and pref_v)) else c_h
        out += [corner, b]
    return _simplify(out)


def _point_at(pts: list, frac: float) -> tuple:
    """Point at ``frac`` of the polyline's arc length; 3rd value = leg is horizontal."""
    segs = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    lens = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in segs]
    total = sum(lens) or 1.0
    target, acc = frac * total, 0.0
    for (a, b), L in zip(segs, lens):
        if L == 0:
            continue
        if acc + L >= target:
            t = (target - acc) / L
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t,
                    abs(b[0] - a[0]) >= abs(b[1] - a[1]))
        acc += L
    a, b = segs[-1]
    return (b[0], b[1], abs(b[0] - a[0]) >= abs(b[1] - a[1]))


def _ov_area(a: tuple, b: tuple) -> float:
    """Overlap area of two axis-aligned boxes (0 if disjoint)."""
    w = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    h = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    return w * h


def _seg_box(a: tuple, b: tuple, t: float = 4.0) -> tuple:
    """A thin keep-out box hugging an axis-aligned wire segment — so an edge label can be
    kept from landing on top of an *unrelated* wire (which would read as labelling it)."""
    return (min(a[0], b[0]) - t, min(a[1], b[1]) - t, max(a[0], b[0]) + t, max(a[1], b[1]) + t)


def _place_label(pts: list, half_w: float, badge: bool, keepouts: list) -> tuple:
    """Position an edge label (text box + its left badge): slide it along the wire and
    nudge it off the wire, scoring each spot by how much it overlaps any keep-out (node
    icon+caption boxes, already-placed labels, and other edges' wires). Pick the
    least-overlapping spot, tie-broken toward the wire and the arc midpoint."""
    bl = 22 if badge else 0                          # badge juts left of the text box
    best, best_score = None, None
    for fr in (0.5, 0.46, 0.54, 0.4, 0.6, 0.34, 0.66, 0.27, 0.73):
        px, py, horiz = _point_at(pts, fr)
        for off in (0, -15, 15, -26, 26, -38, 38, -52, 52):
            cx, cy = (px, py + off) if horiz else (px + off, py)
            box = (cx - half_w - bl, cy - 11, cx + half_w, cy + 5)
            area = sum(_ov_area(box, k) for k in keepouts)
            score = area + abs(off) * 2.0 + abs(fr - 0.5) * 120   # hug the wire unless it collides
            if best_score is None or score < best_score:
                best, best_score = (cx, cy), score
            if area == 0 and off == 0 and abs(fr - 0.5) < 1e-6:
                return cx, cy                        # dead-centre and clear — done
    return best


def render(spec: dict) -> str:
    W, H = spec["size"]
    nodes = spec["nodes"]
    icon_boxes = {k: _icon_box(n) for k, n in nodes.items()}
    label_boxes = {k: _node_box(n, pad=3) for k, n in nodes.items()}

    out = [
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" '
        'font-family="Helvetica, Arial, sans-serif" role="img" aria-labelledby="t d">',
        f'<title id="t">{esc(spec["title"])}</title>',
        f'<desc id="d">{esc(spec.get("desc", spec["title"]))}</desc>',
        "<defs>",
    ]
    for stroke, _w, _dash, mid in KIND.values():
        out.append(
            f'<marker id="{mid}" markerUnits="userSpaceOnUse" markerWidth="11" '
            f'markerHeight="9" refX="9" refY="4" orient="auto">'
            f'<path d="M0,0 L10,4 L0,8 Z" fill="{stroke}"/></marker>'
        )
    out.append("</defs>")
    out.append(f'<rect x="8" y="8" width="{W - 16}" height="{H - 16}" rx="16" '
               'fill="#FFFFFF" stroke="#D3D1C7" stroke-width="1.5"/>')
    out.append(f'<text x="28" y="40" font-size="20" font-weight="500" fill="{INK}">'
               f'{esc(spec["title"])}</text>')
    if spec.get("subtitle"):
        out.append(f'<text x="28" y="60" font-size="12" fill="{SUB}">'
                   f'{esc(spec["subtitle"])}</text>')

    # edge-type legend (top right)
    leg = [("req", "request"), ("id", "identity / token"), ("sup", "supporting")]
    lx = W - 374
    for kind, lbl in leg:
        stroke, _w, dash, _m = KIND[kind]
        da = f' stroke-dasharray="{dash}"' if dash else ""
        out.append(f'<line x1="{lx}" y1="36" x2="{lx + 26}" y2="36" stroke="{stroke}" '
                   f'stroke-width="2"{da}/>')
        out.append(f'<text x="{lx + 32}" y="40" font-size="11" fill="{SUB}">{lbl}</text>')
        lx += 36 + 10 + len(lbl) * 6.2

    # ── PASS 1: groups (behind everything), fitted to each member's rendered text ──
    zone_titles = []                                     # title boxes — keep edge labels off them
    for g in spec.get("groups", []):
        if "bbox" in g:
            x, y, w, h = g["bbox"]
        else:
            boxes = [_node_box(nodes[k]) for k in g["nodes"]]
            pad = g.get("pad", 26)
            x0 = min(b[0] for b in boxes) - pad
            y0 = min(b[1] for b in boxes) - pad - 16     # extra band for the group label
            x1 = max(b[2] for b in boxes) + pad
            y1 = max(b[3] for b in boxes) + pad
            x1 = max(x1, x0 + len(g["label"]) * 6.9 + 28)   # never clip the zone title
            x0, y0 = max(x0, 16), max(y0, 70)               # stay inside the frame + header
            x1, y1 = min(x1, W - 16), min(y1, H - 16)
            x, y, w, h = x0, y0, x1 - x0, y1 - y0
        dashed = g.get("dashed", False)
        da = ' stroke-dasharray="4 4"' if dashed else ""
        col = "#879196" if dashed else INK
        out.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="12" '
                   f'fill="none" stroke="{col}" stroke-width="{1.2 if dashed else 1.6}"{da}/>')
        out.append(f'<text x="{x + 14:.0f}" y="{y + 22:.0f}" font-size="12.5" fill="{col}">'
                   f'{esc(g["label"])}</text>')
        zone_titles.append((x + 12, y + 10, x + 16 + len(g["label"]) * 6.9, y + 26))

    # ── resolve each edge's geometry once (anchors + waypoints + label position) ──
    edges = []
    placed = []                                          # boxes of labels already placed
    placed_segs = []                                     # wires already routed — for lane separation
    node_ko = list(label_boxes.values()) + zone_titles
    for e in spec.get("edges", []):
        s, d = nodes[e["s"]], nodes[e["d"]]
        ss, ds = e.get("ss"), e.get("ds")
        if not ss or not ds:
            asd, bsd = _auto_sides(s, d)
            ss, ds = ss or asd, ds or bsd
        x1, y1 = _anchor(s, ss)
        x2, y2 = _anchor(d, ds)
        dxe, dye = x2 - x1, y2 - y1
        so, do = _exit_axis(ss, dxe, dye), _exit_axis(ds, -dxe, -dye)
        obst = [bx for k, bx in icon_boxes.items() if k not in (e["s"], e["d"])]
        via = e.get("via")
        if via:                                          # honour hand-routed waypoints
            mids = via
        else:                                            # most direct orthogonal path around icons
            mids = _route(x1, y1, ss, x2, y2, ds, obst)
        pts = [(x1, y1), *mids, (x2, y2)]
        # never emit an acute-angle leg; steer inserted bends clear of icons + placed wires
        pts = _orthogonalize(pts, so, do, obst, placed_segs)
        pts = [p for i, p in enumerate(pts) if i == 0
               or (round(p[0]), round(p[1])) != (round(pts[i - 1][0]), round(pts[i - 1][1]))]
        cur_segs = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        kind = e.get("kind", "req")
        label, n = e.get("label", ""), e.get("n")
        lx = ly = None
        if label or n is not None:
            half_w = (len(label) * CHAR_E + 8) / 2 if label else 9
            bl = 22 if n is not None else 0
            if e.get("lp"):
                lx, ly = e["lp"]
            else:                                        # avoid nodes, prior labels, and other wires
                wire_ko = [_seg_box(a, b) for a, b in placed_segs]   # current edge's wire not added yet
                lx, ly = _place_label(pts, half_w, n is not None, node_ko + placed + wire_ko)
            placed.append((lx - half_w - bl, ly - 11, lx + half_w, ly + 5))
        placed_segs += cur_segs                          # add after labelling so a label never dodges its own wire
        edges.append((kind, pts, label, n, lx, ly))

    # ── PASS 2: edge polylines (under the icons) ──
    for kind, pts, *_ in edges:
        stroke, wdt, dash, mid = KIND[kind]
        da = f' stroke-dasharray="{dash}"' if dash else ""
        path = " ".join(f"{px:.0f},{py:.0f}" for px, py in pts)
        out.append(f'<polyline points="{path}" fill="none" stroke="{stroke}" '
                   f'stroke-width="{wdt}"{da} marker-end="url(#{mid})"/>')

    # ── PASS 3: node icons ──
    for n in nodes.values():
        cx, cy = n["x"], n["y"]
        out.append(f'<image x="{cx - IC / 2:.0f}" y="{cy - IC / 2:.0f}" width="{IC}" '
                   f'height="{IC}" xlink:href="{uri(n["icon"])}"/>')

    # ── PASS 4: edge labels + numbered badges (on top of icons) ──
    for kind, pts, label, n, lx, ly in edges:
        if not (label or n is not None):
            continue
        stroke = KIND[kind][0]
        tx = lx
        if label:
            wpx = len(label) * CHAR_E + 8
            col = stroke if kind == "id" else SUB
            out.append(f'<rect x="{lx - wpx / 2:.0f}" y="{ly - 11:.0f}" width="{wpx:.0f}" '
                       'height="15" fill="#FFFFFF" fill-opacity="0.95"/>')
            out.append(f'<text x="{lx:.0f}" y="{ly:.0f}" font-size="10" text-anchor="middle" '
                       f'fill="{col}">{esc(label)}</text>')
            tx = lx - wpx / 2
        if n is not None:
            bx, by = tx - 11, ly - 4
            out.append(f'<circle cx="{bx:.0f}" cy="{by:.0f}" r="9" fill="{INK}"/>')
            out.append(f'<text x="{bx:.0f}" y="{by + 3.3:.0f}" font-size="10" '
                       f'font-weight="600" text-anchor="middle" fill="#FFFFFF">{n}</text>')

    # ── PASS 5: node text labels (above everything; a white knockout band lets wires
    #            read as passing *behind* the caption instead of slicing the glyphs) ──
    for n in nodes.values():
        cx, cy = n["x"], n["y"]
        title, sub, pos = n.get("title", ""), n.get("sub", ""), n.get("label", "below")
        tw = max(len(title) * CHAR_T, len(sub) * CHAR_S) + 6
        if pos in ("left", "right"):
            end = "end" if pos == "left" else "start"
            tx = cx - IC / 2 - 8 if pos == "left" else cx + IC / 2 + 8
            kx = tx - tw if pos == "left" else tx
            kb = (cy + 12 if sub else cy - 3) + 3
            out.append(f'<rect x="{kx:.0f}" y="{cy - 14:.0f}" width="{tw:.0f}" '
                       f'height="{kb - (cy - 14):.0f}" fill="#FFFFFF" fill-opacity="0.95"/>')
            out.append(f'<text x="{tx:.0f}" y="{cy - 3:.0f}" font-size="12.5" font-weight="500" '
                       f'text-anchor="{end}" fill="{INK}">{esc(title)}</text>')
            if sub:
                out.append(f'<text x="{tx:.0f}" y="{cy + 12:.0f}" font-size="10.5" '
                           f'text-anchor="{end}" fill="{SUB}">{esc(sub)}</text>')
        else:
            yt = cy + IC / 2 + TITLE_DY
            kb = (cy + IC / 2 + SUB_DY if sub else yt) + 3
            out.append(f'<rect x="{cx - tw / 2:.0f}" y="{yt - 11:.0f}" width="{tw:.0f}" '
                       f'height="{kb - (yt - 11):.0f}" fill="#FFFFFF" fill-opacity="0.95"/>')
            out.append(f'<text x="{cx:.0f}" y="{yt:.0f}" font-size="12.5" '
                       f'font-weight="500" text-anchor="middle" fill="{INK}">{esc(title)}</text>')
            if sub:
                out.append(f'<text x="{cx:.0f}" y="{cy + IC / 2 + SUB_DY:.0f}" font-size="10.5" '
                           f'text-anchor="middle" fill="{SUB}">{esc(sub)}</text>')

    out.append("</svg>")
    return "\n".join(out)


def write(spec: dict, out_dir: Path) -> Path:
    svg_path = out_dir / f'{spec["key"]}-architecture.svg'
    svg_path.write_text(render(spec))
    return svg_path
