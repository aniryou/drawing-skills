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

Install the tools each skill needs — commands below (macOS / Linux).

**`uv`** — runs the architecture renderer with the `diagrams` package on demand. *(architecture-skill)*

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh    # official installer (macOS / Linux)
# alternatives:  brew install uv   ·   pipx install uv   ·   winget install astral-sh.uv (Windows)
```

**`rsvg-convert`** — renders the PNG raster. *Optional* — without it, SVG + draw.io still generate (and
macOS `qlmanage -t -s 2200 -o /tmp/out file.svg` rasterizes with no install). *(architecture-skill)*

```bash
brew install librsvg               # macOS
sudo apt install librsvg2-bin      # Debian / Ubuntu
```

**Node.js + `@mermaid-js/mermaid-cli`** — provides the `mmdc` command that `mermaid-check` renders with. *(mermaid-check)*

```bash
brew install node                          # macOS  (or download from https://nodejs.org)
npm install -g @mermaid-js/mermaid-cli     # installs the `mmdc` CLI
```

**Headless Chrome for Puppeteer** — `mmdc` drives a headless browser to rasterize; install one and tell
`mmdc` where it is. *(mermaid-check)*

```bash
npx -y @puppeteer/browsers install chrome-headless-shell@latest --path ~/.cache/puppeteer
# point mmdc at it — add to your shell profile (or ~/.claude/settings.json "env"):
export PUPPETEER_EXECUTABLE_PATH="$(ls -d ~/.cache/puppeteer/chrome-headless-shell/*/chrome-headless-shell-*/chrome-headless-shell | tail -1)"
```

If `mmdc` ever errors with *"Could not find Chrome"*, re-run the two commands above — that's the
self-heal documented in [`mermaid-check/SKILL.md`](mermaid-check/SKILL.md).

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

### Worked example: the `academic-research` ADK sample

The three steps run against Google's
[`academic-research`](https://github.com/google/adk-samples/tree/main/python/agents/academic-research)
ADK agent — a Gemini 2.5 Pro **`academic_coordinator`** root agent with two `AgentTool` sub-agents:
**`academic_websearch_agent`** (grounded by the built-in `google_search` tool) and
**`academic_newresearch_agent`**. The diagrams below mirror the structure in the sample's own
[`academic-research.svg`](https://github.com/google/adk-samples/blob/main/python/agents/academic-research/academic-research.svg)
— a root coordinator linked to its two sub-agents. All artifacts live in [`docs/`](docs/).

**Each step's input is the previous step's output** — one artifact flows through the chain:
`academic-research-draft.mmd` → *mermaid-check* → `academic-research.mmd` → *architecture-skill* →
`academic-research-architecture.svg` / `.png` / `.drawio`.

The **components never change** — all three steps carry the **same 3 nodes and 2 edges**
(`academic_coordinator` → `academic_websearch_agent`, `academic_newresearch_agent`). Only the
*rendering* changes: mermaid-check fixes the layout, architecture-skill swaps in cloud icons.

**Step 1 — a first-pass Mermaid draft**
([`docs/academic-research-draft.mmd`](docs/academic-research-draft.mmd)). A quick `graph TD` sketch — the
kind you get before any cleanup. It *renders*, but it's rough:

![academic-research — rough first-pass Mermaid draft](docs/academic-research-draft.png)

**Step 2 — `mermaid-check` takes the step-1 draft, *looks* at the render, and fixes it.** Input
[`academic-research-draft.mmd`](docs/academic-research-draft.mmd) → output
[`academic-research.mmd`](docs/academic-research.mmd): the **same three agents and two links**, now
rendered cleanly to match the sample's own diagram. It only touched *rendering* — no nodes or edges
added or removed:

- `graph TD` → `flowchart LR` — an agent tree reads left-to-right (root → children), not top-down.
- **Split the run-on single-line labels into two-line, quoted `<br/>` captions** — quoting `<br/>` is
  what keeps them parsing on strict renderers (GitHub, Azure DevOps wiki).
- **Highlighted the root `academic_coordinator`** (green) to match the sample's diagram.

![academic-research — after mermaid-check](docs/academic-research-mermaid.png)

**Step 3 — `architecture-skill` takes the step-2 mermaid and converts it to cloud icons.** It reads
[`academic-research.mmd`](docs/academic-research.mmd), re-authors it at service altitude as
[`academic-research-spec.json`](docs/academic-research-spec.json) (Vertex AI icons for the Gemini
agents, the same root → sub-agent links), then renders
[`.svg`](docs/academic-research-architecture.svg) ·
[`.png`](docs/academic-research-architecture.png) · editable
[`.drawio`](docs/academic-research-architecture.drawio):

![academic-research as a cloud-architecture diagram](docs/academic-research-architecture.png)

The exact commands — note each reads the prior step's file:

```bash
# Step 1 → docs/academic-research-draft.mmd   (the LLM's first-pass draft)

# Step 2 — mermaid-check: take the step-1 draft, render → LOOK → fix → save the cleaned diagram
mmdc -i docs/academic-research-draft.mmd -o /tmp/draft.png -s 2 -b white                        # inspect the draft, then fix it →
mmdc -i docs/academic-research.mmd       -o docs/academic-research-mermaid.png -s 2 -b white    # step-2 output (cleaned)

# Step 3 — architecture-skill: take the step-2 mermaid, re-author it as a spec, render with cloud icons
#          (reads academic-research.mmd → writes academic-research-spec.json → renders svg/png/drawio)
uv run --with diagrams python architecture-skill/generate.py docs/academic-research-spec.json out
```

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
