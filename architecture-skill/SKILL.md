---
name: architecture-skill
description: Generate clean cloud-architecture diagrams across all hyperscalers (AWS, Google Cloud, Azure) — official provider service icons, left-to-right, elbow (right-angle) connectors, grouped zones, and a numbered request flow — as self-contained SVGs from a small declarative spec. Use whenever the user wants to create, convert, or redraw an architecture diagram in "AWS style" / "GCP style" / "Azure style" / "cloud icons" / draw.io-style cloud architecture, including multi-cloud diagrams, or turn a dense Mermaid / whiteboard sketch into approachable service-level boxes.
---

# architecture-skill

Produce **cloud-architecture-style** diagrams for **any hyperscaler** — official **AWS**,
**Google Cloud**, and **Azure** service icons (plus SaaS / on-prem tooling) laid out
left-to-right, joined by **elbow (right-angle) connectors**, grouped into rounded **zones**
(a Cloud / VPC / VNet boundary, a dashed sub-zone…), with a **numbered request flow** and a
3-kind edge legend. Mix providers freely in one diagram for **multi-cloud** architectures.
Output is a **self-contained SVG** (icons base64-embedded so GitHub renders it inline) + an
optional PNG raster.

The diagram is **data**: you write a declarative spec (nodes + groups + edges) and the bundled
renderer turns it into SVG — **no Graphviz** (the `diagrams` package is used only for the icon PNGs).
This skill bundles these files:
- `_archviz.py` — the renderer: icon loader (the `_ICONS` vocabulary across AWS / GCP / Azure
  lives here), a **strictly-orthogonal shortest-path elbow router** (no acute angles — diagonals
  from `via` points are auto-split into right-angle Ls steered clear of icons/wires),
  **label-extent zones**, **wire-aware label placement** (labels dodge icons, captions, other
  labels, and other edges' wires) + **caption knockouts**, badges, legend; the grammar lives here.
- `generate.py` — the driver: `uv run --with diagrams python generate.py [specs.json] [out_dir]`.
- `example-spec.json` — two render-valid diagrams to copy: a **minimal** request flow, plus a
  **dense fan-out** showing the two anti-tangle moves (distinct `ss` anchors + outer `via` lanes)
  for edges that fan from / converge on one node — the cases the auto-router can't always untangle.
- `multicloud-example-spec.json` (+ rendered `multicloud-architecture.svg/.png`) — a showcase
  drawing the same serverless web stack on AWS, GCP, and Azure side by side.

## When to use
- "Make an AWS / GCP / Azure architecture diagram of …", "convert this to cloud icons", "draw a
  multi-cloud diagram", "draw this like a cloud architecture diagram", "redraw this
  Mermaid/whiteboard sketch as service boxes".
- Authoring or refreshing architecture docs where every box should be a real cloud service.

## Toolchain (no Graphviz)
- **Render:** `uv run --with diagrams python <generate.py> <specs.json> <out_dir>` (or `pip install
  diagrams` then `python …`). The `diagrams` package ships the official AWS / GCP / Azure icon
  PNGs; the renderer base64-embeds them into one portable SVG.
- **Rasterize to inspect** (the SVG is the deliverable; the PNG is for your eyes + a fallback):
  - macOS, zero-install: `qlmanage -t -s 2200 -o /tmp/out <file>.svg` (pads to a square — the content
    scales to the requested width; crop with `sips` if you need legible halves).
  - portable / for the committed PNG: `rsvg-convert -w 3000 <file>.svg -o <file>.png`
    (`brew install librsvg` or `apt install librsvg2-bin`).

## The loop
1. **Study a reference** if the user has one (an existing cloud diagram, a draw.io export, a system
   diagram). Match its zones, icon choices, and altitude before authoring.
2. **Author the spec** — one object per diagram. Keep it at **service altitude**: one box per service
   named by product (*not* per code-symbol); fine detail goes in the box's one-line `sub` or the
   surrounding prose, **never as extra nodes**. Aim for **10–18 nodes**.
3. **Verify — load the render and hunt text overlaps (mandatory; iterate until zero).** See below.
4. Commit the SVG (+ PNG) and the spec; **never hand-edit the SVG** (re-run the generator).

## Verify — load the render and hunt overlaps (do NOT skip; iterate until clean)
The renderer avoids most collisions on its own: text is drawn **above** every icon, node captions get a
white knockout so wires read as passing *behind* them, edge labels are **placed to dodge nodes, zone
titles, each other, and other edges' wires**, zones are **fitted around the rendered text** (and clamped
to the canvas), and connectors are **strictly orthogonal** — auto-routed elbows take the shortest icon-clear
path and any diagonal a `via` would introduce is split into a right-angle L (no acute angles). But layout
can still defeat it, so you must still eyeball every render and fix the spec until nothing collides.

**Each pass:** render → rasterize (`qlmanage -t -s 2200 -o /tmp/x <file>.svg`, or `rsvg-convert -w 3000`)
→ **Read the PNG** → list every overlap → fix the spec → re-render. For dense diagrams, also re-raster
a region (`sips -c <h> <w> --cropOffset <top> <left> in.png --out half.png`) and Read each half so small
text is legible. Repeat until a pass finds **no overlaps**.

**The renderer already handles these — don't hand-tune them:** icons over text · an edge label landing on
a node/icon/another wire · two edge labels stacking · a label hoisted onto a zone title · a wire slicing a
node caption · a node label spilling out of its zone · a zone title clipped by its border or the canvas ·
an elbow crossing an icon · a diagonal/acute-angle wire · a `via` waypoint that introduces a slanted leg.

**When you DO still see an overlap, it's almost always one of these — fix in the spec:**
- **A label crammed onto a node** — it's too long for the gap between its two nodes, so there's no clear
  spot. **Fix:** shorten the label (push detail into the node `sub` or prose), or widen the node spacing.
- **A node caption sliced by a zone border, or a node straddling a zone edge** — the node sits where a
  zone boundary falls, often because a long zone *title* or a wide member `sub` stretched the zone toward
  it. **Fix:** shorten the zone title or that member's `sub`, or move the node clear of the border.
- **An elbow still crossing an icon, or a wire shadowing a zone border** — the auto-router found no clear
  orthogonal path. **Fix:** add a `via` waypoint to route it by hand, or re-anchor (`ss`/`ds`) to a
  clearer side. Anti-parallel call+response pairs read best **merged into one `A ⇄ B` edge**
  (e.g. `ConverseStream ⇄ deltas`).
- **Two labels still colliding** — both pinned near one point (e.g. both `via`-routed through one
  corridor). **Fix:** shorten or re-route one, or give it an explicit `lp` (label point).
- **Several edges leave one node and you can't tell which is which** — N edges fan from a single node,
  the router exits them from the same side, long edges tangle with short ones, and the step-badges stack
  in one column. **Fix:** give each edge a *distinct* source anchor (`ss` = `r`/`t`/`b`/a corner) so the
  origins separate right at the node boundary, and route the long edges on **dedicated outer lanes** via
  `via` waypoints (e.g. a high lane *above* the row into the target's top, a low lane *below* it into the
  target's bottom) so they don't co-run with the short hops — each badge then sits on its own wire near
  the source.

## Grammar (authoritative source: `_archviz.py`)
A spec is one object: `{key, title, subtitle, desc, size:{w,h}, nodes[], groups[], edges[], notes}`.
- **node** `{key, x, y, icon, title, sub, label}` — `(x,y)` is the icon **centre** in px; `icon` is one
  ICON key (below). `label` = `"below"` (default) or `"left"`/`"right"` — use left/right only for a node
  a vertical edge passes through (e.g. an identity box on the top band) so its text clears the arrows.
- **group** `{label, dashed, nodes:[keys], pad}` — a rounded zone auto-fitted around those nodes (+pad).
  `dashed:false` = the main cloud/zone boundary; `dashed:true` = a sub-zone.
- **edge** `{s, d, kind, label, n, ss, ds, via}` — `s/d` are node keys. `kind` ∈ `req` (thick dark =
  request/data path) · `id` (blue dashed = identity/token/secret) · `sup` (thin grey = supporting,
  incl. telemetry). `label` is a short verb phrase; `n` is a step-badge string (`"1"`, `"8a"`) or null.
  `ss`/`ds` are source/dest anchor sides (`l r t b` or corners `tl tr bl br`) or null to auto-pick.
  **Edges auto-route as elbows** (H·V·H, V·H·V, or a single L-bend); set `via` = `[[x,y],…]` only for a
  manually-routed edge (e.g. an identity edge that runs along the very top of the canvas).

## Icon vocabulary (AWS · GCP · Azure)
Keys are short handles you put in a node's `icon`. **Three parallel families** so the same architecture
draws on any cloud: **AWS = bare keys**, **GCP = `gcp_` prefix**, **Azure = `az_` prefix**.
Cloud-neutral actors / SaaS / tooling have no prefix. (Authoritative list: `_ICONS` in `_archviz.py`.)

- **Neutral:** `user · users · client · snowflake · github · ghactions · terraform · python`
- **AWS:** `ec2 · lambda · ecs · eks · fargate · apprunner · ecr · s3 · db · rds · aurora · dynamodb ·
  elasticache · apigw · elb · alb · cloudfront · route53 · vpc · sns · sqs · eventbridge · stepfunctions ·
  ses · redshift · athena · glue · kinesis · emr · bedrock · sagemaker · iam · cognito · secrets · kms ·
  shield · waf · guardduty · cloudwatch · cwlogs · alarm · xray`
- **GCP:** `gcp_gce · gcp_functions · gcp_run · gcp_gke · gcp_appengine · gcp_gcr · gcp_gcs · gcp_sql ·
  gcp_spanner · gcp_firestore · gcp_bigtable · gcp_memorystore · gcp_apigw · gcp_apigee · gcp_lb ·
  gcp_cdn · gcp_dns · gcp_vpc · gcp_armor · gcp_bigquery · gcp_pubsub · gcp_dataflow · gcp_dataproc ·
  gcp_vertex · gcp_iam · gcp_secrets · gcp_kms · gcp_monitoring · gcp_logging · gcp_build`
- **Azure:** `az_vm · az_functions · az_appservice · az_aks · az_containerapps · az_acr · az_blob ·
  az_sql · az_cosmos · az_redis · az_datafactory · az_apim · az_lb · az_appgw · az_cdn · az_frontdoor ·
  az_dns · az_vnet · az_firewall · az_servicebus · az_eventhub · az_eventgrid · az_logicapps ·
  az_synapse · az_databricks · az_ml · az_openai · az_cognitive · entra (= az_ad) · az_keyvault ·
  az_defender · az_monitor · az_loganalytics · az_appinsights · az_devops · az_pipelines`

**Need another service?** Find the class and add one line to `_ICONS`. The icon sets live under
`diagrams.aws.*`, `diagrams.gcp.*`, `diagrams.azure.*` (also `diagrams.saas.*`, `diagrams.onprem.*`):
```bash
uv run --with diagrams python -c "import diagrams.gcp.database as m; print([c for c in dir(m) if c[0].isupper()])"
```
then add e.g. `"gcp_alloydb": ("diagrams.gcp.database", "AlloyDB")`. Keep the prefix convention
(`gcp_`/`az_`, bare for AWS) so specs stay readable.

## Layout (consistent, overlap-free)
- **Strict left-to-right.** Sources on the left, destinations on the right.
- **Column x-grid** (reuse so diagrams in a set align): `70 · 210 · 430 · 690 · 950 · 1250`; add mid
  columns (`560, 820, 1090…`) as needed. **Row y-grid:** `150` (top identity band) · `330` (main flow)
  · `480` · `610` · `700`.
- Keep nodes **≥130px apart horizontally, ≥140px vertically** (each reserves ~52px icon + ~34px label).
- **Number the primary (thick `req`) path** `1,2,3…`; use `a/b/c` for a parallel fan-out (`8a/8b/8c`).
- **Group by trust / responsibility** (or **by cloud** in a multi-cloud diagram — one zone per provider).
  Pull a shared-target node *out* of the branch zones so its edges are short; order zones so cross-zone
  edges are short hops.
- Three-stage flows read well as three zones (e.g. *Source → Routing → Destination*).

## Using it in a repo (vendor for self-containment)
So the repo regenerates its diagrams without depending on this skill:
```bash
mkdir -p <repo>/docs/architecture
cp ~/.claude/skills/architecture-skill/{_archviz.py,generate.py} <repo>/docs/architecture/
cp ~/.claude/skills/architecture-skill/example-spec.json <repo>/docs/architecture/specs.json  # then edit
cd <repo> && uv run --with diagrams python docs/architecture/generate.py
```
Reference each SVG from markdown: `![<Title>](<key>-architecture.svg)`. Commit the `.svg` (+ `.png`),
`specs.json`, and the two `.py` files. Record in the repo's CLAUDE.md that the diagrams come from this
skill's renderer via `specs.json` + `generate.py` — edit the spec, re-run, never hand-edit the SVG.

## Cleanup
Inspection rasters go under `/tmp`; mention the path or remove them. Commit only the SVG/PNG, the spec,
and the two `.py` files.
