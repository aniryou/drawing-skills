# drawing-skills

A small collection of **diagram / drawing skills** for [Claude Code](https://claude.com/claude-code) —
each a self-contained folder with a `SKILL.md` (and any helper scripts) that Claude loads on demand.

| Skill | What it does |
| --- | --- |
| [`architecture-skill`](architecture-skill/) | Generate clean **cloud-architecture diagrams across all hyperscalers** (AWS · Google Cloud · Azure) — official provider icons, left-to-right, elbow connectors, grouped zones, numbered request flow — as a self-contained **SVG**, a **PNG**, or an editable **draw.io** file from a tiny declarative spec. |
| [`mermaid-check`](mermaid-check/) | Render → look → fix loop for **Mermaid** diagrams: rasterize, visually inspect for overlaps / parse errors, and fix the source so it survives strict renderers (GitHub, Azure DevOps wiki, Confluence). |

## How to install and use

### Install

Claude Code discovers skills under `~/.claude/skills/`. Symlink each one so edits in this repo take
effect immediately:

```bash
ln -s "$(pwd)/architecture-skill" ~/.claude/skills/architecture-skill
ln -s "$(pwd)/mermaid-check"       ~/.claude/skills/mermaid-check
```

(or copy the folders if you prefer a snapshot over a live link).

### Prerequisites

- **architecture-skill** — [`uv`](https://docs.astral.sh/uv/) (runs the renderer with the `diagrams`
  package on demand: `uv run --with diagrams python generate.py`). Optional `rsvg-convert`
  (`brew install librsvg`) for PNG rasters; macOS `qlmanage` works with no install.
- **mermaid-check** — `@mermaid-js/mermaid-cli` (`mmdc`) plus a headless Chrome for Puppeteer; see the
  self-heal block in [`mermaid-check/SKILL.md`](mermaid-check/SKILL.md).

### The workflow: sketch → check → render

The two skills chain into one pipeline that takes a plain-English idea to a polished, cloud-icon
diagram (as **draw.io** or **PNG**) in three steps. Talk to Claude Code in natural language — each
skill triggers on its description — or invoke one explicitly with `/<skill-name>`.

1. **Prompt the LLM to draft a Mermaid diagram.** Describe the system and let Claude lay it out as
   Mermaid — the fastest way to get the structure down.
   > "Draw a Mermaid flowchart of our order-triage pipeline: client → API Gateway → Lambda →
   > DynamoDB, with an SNS fan-out."

2. **Use `mermaid-check` to improve it.** It renders the diagram, *looks* at the image, and fixes the
   source until it parses on strict renderers and has no overlaps or illegible labels — so you carry
   forward a clean, validated layout instead of a first draft.
   > "Use mermaid-check to render and fix that diagram."

3. **Use `architecture-skill` to render it with cloud logos.** It re-authors the validated Mermaid as a
   service-level spec and renders it with **official AWS / GCP / Azure icons** — to an editable
   **draw.io** file, a **PNG**, or an SVG. Name the format you want (or get all three).
   > "Use architecture-skill to convert that to draw.io with AWS icons."

   Equivalently, via the slash command or the CLI — pick the output with `-f drawio | png | svg`
   (omit for all):
   ```bash
   /architecture-skill convert the mermaid to drawio
   # or directly:
   uv run --with diagrams python ~/.claude/skills/architecture-skill/generate.py specs.json out -f drawio
   ```

Step 1 gets *structure* down fast, step 2 makes it *correct*, step 3 makes it *presentation-grade*
with real cloud iconography. You can also jump straight to step 3 if you already have a spec or just
describe the architecture in words — Mermaid is the on-ramp, not a requirement.

> **Mermaid → cloud icons is a re-authoring, not a transpile.** `architecture-skill` reads the Mermaid
> to understand the system, then rewrites it at *service altitude* (one box per real cloud service, not
> one per Mermaid node) so the result is an idiomatic cloud diagram rather than a 1:1 shape copy.

## architecture-skill at a glance

The same serverless web stack drawn on all three clouds — one declarative spec, official icons,
zero hand-drawn assets:

![Multi-cloud architecture — AWS, GCP, Azure](architecture-skill/multicloud-architecture.png)

Icons are not bundled image files — each is a `(module, class)` reference into the
[`diagrams`](https://pypi.org/project/diagrams/) package, base64-embedded into the output at render
time. That's why supporting a new cloud or service is a one-line addition to the `_ICONS` table in
[`architecture-skill/_archviz.py`](architecture-skill/_archviz.py), and why the output is fully
self-contained (the SVG renders inline on GitHub; the `.drawio` carries its own icons, so it needs no
draw.io shape libraries). The vocabulary ships **43 AWS · 30 GCP · 37 Azure** service icons plus
cloud-neutral actors / SaaS / tooling, in three parallel families (`s3` / `gcp_gcs` / `az_blob`, …).

## Regenerating the architecture example

```bash
cd architecture-skill
uv run --with diagrams python generate.py multicloud-example-spec.json .   # → .svg + .png + .drawio
```

Output is reproducible: the same spec yields a byte-identical SVG. Edit the spec, re-run — **never
hand-edit the SVG** (the `.drawio` you may tweak by hand, but a regenerate overwrites it).
