---
name: mermaid-check
description: Render a mermaid diagram to an image, visually inspect it for overlaps and parse errors, and fix the source. Use whenever the user shares a mermaid diagram or asks to render, validate, preview, improve, lay out, or debug one (flowchart, sequence, ER, gantt, etc.).
---

# mermaid-check

Render → look → fix loop for mermaid diagrams. The goal: never hand back a diagram
that fails to parse on the target renderer or overlaps itself. Local rendering with
`mermaid-cli` is **lenient** — it accepts things stricter renderers (Azure DevOps
wiki, GitHub, Confluence) reject. So rendering is necessary but not sufficient;
the authoring rules below are what actually prevent the common failures.

## Headless Chrome (set up claude-wide — read this if rendering produces no PNG)

`mmdc` ships **`puppeteer-core`**, which does **not** download a browser — it expects a
headless Chrome on the host. Without one, `mmdc` fails with `Could not find Chrome` (or
exits 0 but writes no file). This is already configured machine-wide:

- A headless Chrome lives in the puppeteer cache: `~/.cache/puppeteer/chrome-headless-shell/`.
- `PUPPETEER_EXECUTABLE_PATH` is set in `~/.claude/settings.json` (`env`), so **every Claude
  session in every repo** gets it. With it set, a bare `mmdc -i doc.md -o out.png` just works —
  **no `--no-sandbox`, no other flags** (on macOS).

**Self-heal — if rendering fails (`Could not find Chrome`, or no PNG appears), run:**
```bash
command -v mmdc >/dev/null || npm i -g @mermaid-js/mermaid-cli          # install the CLI
# install the matching headless browser into the default puppeteer cache:
npx -y @puppeteer/browsers install chrome-headless-shell@latest --path ~/.cache/puppeteer
# then point the env var at the freshly-installed binary (update ~/.claude/settings.json
# env.PUPPETEER_EXECUTABLE_PATH if the version dir differs from what's there).
CHROME=$(ls -d ~/.cache/puppeteer/chrome-headless-shell/*/chrome-headless-shell-*/chrome-headless-shell | tail -1)
PUPPETEER_EXECUTABLE_PATH="$CHROME" mmdc -i /tmp/mermaid_work/probe.mmd -o /tmp/mermaid_work/probe.png  # verify
```
A botched/partial download manifests as a launch crash (missing framework / `ChildProcess
onClose`) — `rm -rf` that version dir under `~/.cache/puppeteer` and reinstall cleanly. Do
**not** symlink the binary to another dir: Chrome resolves its bundled resources relative to
the real executable path and crashes when launched through a symlink. In a locked-down sandbox
where Chrome still won't launch, pass `-p <(echo '{"args":["--no-sandbox"]}')`.

## The loop

Diagrams are usually embedded as ` ```mermaid ` fenced blocks inside `.md` files —
**handle the markdown file directly, don't hand-extract the block.** `mmdc` accepts a
markdown file as input, finds *every* mermaid block, and renders each one — so one
command validates and previews the whole doc.

1. Render straight from the markdown file (use PNG so you can Read the result):
   ```bash
   mkdir -p /tmp/mermaid_work
   mmdc -i path/to/doc.md -o /tmp/mermaid_work/out.png -s 2 -b white
   ```
   - Prefer the globally-installed `mmdc` (it's set up with headless Chrome — see the
     section above). Avoid `npx -y @mermaid-js/mermaid-cli@latest` as the default: the
     fetch fails silently in a restricted sandbox (exits 0, no output). Fall back to it
     only if `mmdc` isn't installed.
   - Output is one image per diagram: `out-1.png`, `out-2.png`, … plus an `out.md`
     copy with the blocks swapped for image refs (ignore the `.md`).
   - mmdc prints `Found N mermaid charts` and a ✅/❌ per chart; a parse error prints
     the offending line/column. If it prints nothing and writes no PNG, the browser is
     missing — see the **Headless Chrome** self-heal block above.
   - In Claude's sandboxed Bash, launching Chrome may require the Bash call's
     `dangerouslyDisableSandbox: true`; the render itself needs no network.
2. **Read each `out-N.png`** with the Read tool and inspect: overlapping nodes, edges
   crossing through unrelated nodes, colliding labels, illegible text, runaway width.
   - For dense diagrams, re-render at `-s 3` and inspect in halves (crop with `sips`)
     so labels stay legible.
3. **Fix the fenced block in place in the source `.md`** — edit between the
   ` ```mermaid ` / ` ``` ` fences and preserve all surrounding markdown. Don't replace
   the block with an image; the doc renders the mermaid itself.
4. Re-render and confirm visually before returning. Apply the authoring rules below to
   every block, not just the one that errored.

**Raw snippet (no file).** If the user pastes a bare diagram, write it to
`/tmp/mermaid_work/diagram.mmd` and render that instead (`-i diagram.mmd`); same loop.

## Authoring rules (prevent the common failures)

These are the bugs that pass local rendering but break strict renderers or look bad:

- **Quote any label containing `<br/>`** — both nodes AND edges:
  - Node: `A["line1<br/>line2"]`
  - Edge: `A -->|"line1<br/>line2"| B`  ← unquoted `<br/>` in an edge label is the
    single most common parse error ("Expecting … got 'NEWLINE'"). `mmdc` tolerates it;
    Azure DevOps does not.
- **Never put a literal newline inside `[...]`, `(...)`, `{...}`, or `|...|`.** Source
  line-wrapping silently injects one and breaks parsing. Use `<br/>`.
- **Keep each edge on one logical line** — `src -->|"label"| dst` must not wrap across
  source lines (the destination ending up on the next line is a parse error).
- **Escape angle brackets in text** as `&lt;` / `&gt;` (e.g. `&lt;schema&gt;`).

## Layout rules (prevent overlaps)

- **Group parallel flows into `subgraph`s** with short titles; set `direction TB`/`LR`
  inside each to control internal flow.
- **Pull convergence nodes out of subgraphs.** A node that is the shared target of edges
  from several branches should live *outside* the branch subgraphs, near the point where
  they meet — otherwise edges sweep back across the whole canvas and cross things.
- **Order subgraphs so cross-subgraph edges are short.** If A in subgraph 1 points to B
  in another, declare that subgraph adjacent so the edge is a short hop, not a long
  crossing edge through a third subgraph.
- Prefer `TD` for tall hierarchies, `LR` for wide pipelines. Offer the other orientation
  if the chosen one is awkwardly shaped.

## Density — when the whole diagram is unreadable (not just overlapping)

If a rendered diagram is illegible *everywhere* — tiny text, a forest of boxes, edges
crossing the whole canvas — the cause is **too much**, not bad spacing. **Do not reach for
`%%{init: {'flowchart': {'nodeSpacing': …, 'rankSpacing': …}}}%%` first.** Spacing
directives only help a graph that is already close to good: on an overcrowded graph,
*shrinking* spacing packs it tighter and *growing* it just yields a huge canvas where
everything is still cramped relative to its labels. Fix the cause, in this order:

1. **Cut node detail.** Each node should carry a name + one short qualifier — not 4–6 lines.
   Long specifics (file names, exact values, caveats) belong in the surrounding prose, not
   inside the box. Bloated labels are the #1 reason boxes don't fit, and moving detail to
   prose shrinks *every* node at once.
2. **Merge or drop nodes.** Fold trivially-coupled nodes; cut anything the prose already
   carries. A single flowchart past ~20–25 nodes is usually trying to be two diagrams.
3. **Split at the natural seam.** When one picture holds two phases (e.g. build/assembly vs.
   a per-request loop), make two diagrams and share the seam node across both, styled
   identically. Two ~15-node diagrams read far better than one 30-node diagram — especially
   in a narrow markdown column. Keep one continuous step-numbering across them so the prose
   walkthrough still threads through both.
4. **Only then** reorder subgraphs (above) and, if still slightly tight, nudge spacing.

Re-render and read the PNG: every label legible at `-s 2`, no box swamped by its own text.
A spacing tweak that leaves the text tiny means you skipped steps 1–3.

## Matching the target renderer — and why a clean local render proves little

Local `mmdc` is **lenient**, and the leniency runs deep: `@latest` *and* `@10.9.1` both
render `A -->|unquoted<br/>label| B` without complaint, yet older renderers (Azure DevOps
wiki, ~mermaid 8.x/9.x) reject it with `Expecting … got 'NEWLINE'`. **So "it rendered
locally" does not prove it works on the target.** The authoring rules above are the real
safeguard — apply them unconditionally; treat the local render as an overlap/layout check,
not a syntax guarantee.

If you know the target's mermaid version you can pin to it
(`npx @mermaid-js/mermaid-cli@<version> …`) to reproduce its strictness — but very old
versions may fail to install on modern Node, so don't depend on it. When the version is
unknown, the rules win.

## Cleanup

Temp files live under `/tmp/mermaid_work/`. Mention the path so the user can grab the
PNG/SVG, or remove them when done.
