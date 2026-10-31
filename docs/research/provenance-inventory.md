# Provenance inventory (draft)

Status: **draft, prepared with AI assistance (Claude Code), not reviewed by the human owners.** Captured
2026-10-25 at `main` `f01a108`. This is an inventory, not a legal opinion: it certifies neither originality
nor license compliance, and it attributes no code to any individual beyond what git records.

## How to read it

- **Origin** is one of: *original* (first appears in this repository, no upstream found), *copied* (byte-equal or near-equal to a named upstream), *modified*, *generated* (produced by a tool from another file), *third-party dependency* (installed or bundled, not in the source tree), *unknown*.
- "Original" means only that no upstream was identified. No similarity scan against other agent-office projects was run, so the NOTICE claim of from-scratch originality stays **unverified**. Resemblance alone would not show copying either.
- **Git record** is the first commit that touched the path (`git log --follow`), the author identity as recorded, and how many of the commits touching it carry a `Co-Authored-By: Claude …` trailer. A missing trailer does not prove the absence of AI assistance. Style is not used to infer authorship.
- Hashes are SHA-256 of the file at `f01a108` (first 16 hex digits; the full value is reproducible with `sha256sum`).

## Source tree

| Path | Origin | Git record (first commit · author · trailer share) | SHA-256 (16) | Open questions |
| --- | --- | --- | --- | --- |
| `vittics_builder/*.py` (49 modules) | original | from `9dc0a2a` 2026-10-03 · Ram Thondapu; 14 modules first added by `thondapu lakshman` in `fc5aded` 2026-10-06 (arena, assessments, browser, federation, hosting, integrations, learning, marketplace, observability, operations_store, routing, security, swarms, workers; pre-rename paths under `orgforge/`) · most later commits carry the Claude trailer | per file | Who is `thondapu lakshman` and what did that person decide? Human design decisions per module are not recorded. |
| `vittics_builder/default_org.yaml` (role prompts, seat names) | original | `9dc0a2a` · Ram Thondapu · 14 of 20 commits | `7c18286dcdd6811f` | Prompts are part of the product; their authorship is recorded only at commit level |
| `vittics_builder/llm.py` `MockProvider` script and names | original | `9dc0a2a` · Ram Thondapu · 14 of 18 | `65d06c6aa930d898` | Synthetic data; contains no real persons' data as far as inspected |
| `vittics_builder/static/index.html`, `sw.js` | original | `9dc0a2a` / `7c5faa4` · Ram · 23 of 26 / 2 of 2 | `1ade3da2f27fcd5c` / `a688659d13702995` | Loads no external scripts, fonts or CDNs (no external `http(s)://` references found) |
| `vittics_builder/static/icon.svg` | original | `7c5faa4` 2026-10-04 · Ram · 2 of 2 | `954c010c6a9603fc` | none |
| `vittics_builder/skills/karpathy-guidelines.md` | **copied** with a new header | `797eb9e` 2026-10-04 · Ram · 2 of 2 | `ee069bce7da70287` | See the upstream comparison below |
| `desktop/src-tauri/icons/*` | **generated** (`npm run icons` = `tauri icon ../vittics_builder/static/icon.svg`, `desktop/package.json`) | `d9daddd` 2026-10-06 · Ram · 1 of 1 | `icon.png` `523abd6899697ec2` | Not regenerated since `d9daddd`; whether they match the current `icon.svg` is **unverified** |
| `desktop/src-tauri/src/main.rs`, `desktop/src/index.html`, `desktop/scripts/*.py` | original | `d9daddd` · Ram · 3 of 3 | `029d802b1f646ec1` (main.rs) | none |
| `Dockerfile`, `compose.yaml`, `deploy/*` | original | `fc5aded` · thondapu lakshman | `01e21cf5a8ae4610` (Dockerfile) | same identity question as above |
| `docs/*`, `README.md`, `CHANGELOG.md` | original | various | — | Several docs make capability claims; see `week1-audit.md` §4 and the Week 1 audit report |
| `tests/*` | original | various | — | none |

## Upstream comparison: `skills/karpathy-guidelines.md`

| Item | Finding |
| --- | --- |
| Upstream | `https://github.com/forrestchang/andrej-karpathy-skills`, cloned 2026-10-25 at HEAD `2c606141936f1eeef17fa3043a72095b4765b9c2` (2026-04-20) |
| Matching upstream file | `CLAUDE.md`, last changed in `8462496b34419f20b32778610571ac723e91f94c` (2026-01-27), SHA-256 `694a2d72…` |
| Difference | The bundled file's body equals upstream `CLAUDE.md` minus its first two lines (`# CLAUDE.md` and a blank line). The bundled file adds a Vittics front-matter block (name, title, kinds, departments, source). Upstream `skills/karpathy-guidelines/SKILL.md` is a different variant (own front matter, an extra intro line, no closing "working if" paragraph). |
| Upstream license evidence | README section "License: MIT"; `.claude-plugin/plugin.json` `"license": "MIT"`; `SKILL.md` front matter `license: MIT`. **No LICENSE file and no copyright line exist upstream.** |
| NOTICE wording today | "MIT-licensed according to its README, included unchanged apart from a header naming its source" |
| Assessment | The NOTICE is accurate about the source. It is slightly imprecise: the upstream title line was removed, and the exact upstream revision isn't named. The MIT terms require keeping a copyright and permission notice, and upstream publishes neither text. How to satisfy that is an **open question for a human**, not settled here. |

## Third-party dependencies

| Group | What | How it reaches users | License source | Open questions |
| --- | --- | --- | --- | --- |
| Python runtime deps | PyYAML, anthropic, FastAPI (+Starlette, Pydantic), Uvicorn | Installed from PyPI by `pip`; not vendored | `NOTICE.md` table (not re-verified per package here) | Ranges are unpinned (`pyproject.toml`); the installed set differs by date |
| Python optional | mcp, playwright | Installed on request | `NOTICE.md` | Playwright downloads browser binaries separately |
| **Desktop bundle (Python side)** | CPython and every imported package, frozen by PyInstaller `--onefile` (`desktop/scripts/build_server.py`) | **Distributed inside the installer** | Not listed in `NOTICE.md` | Bundled distributions carry their own notice obligations, including the CPython license and the PyInstaller bootloader terms. Not inventoried. |
| **Desktop bundle (Rust side)** | Tauri 2, tauri-plugin-shell, serde_json and transitive crates (422 `[[package]]` entries in `Cargo.lock`) | Compiled into the installer | Not listed in `NOTICE.md` | Crate license inventory not produced (e.g. `cargo about`/`cargo deny` not run) |
| Desktop build tool | `@tauri-apps/cli` 2.12.1 and 11 platform packages (`package-lock.json`, all "Apache-2.0 OR MIT") | Build time only | `package-lock.json` | none |
| Container image | `python:3.12-slim-bookworm` base, Debian `git`, `chromium`, `ca-certificates` | In the hosted image | Not listed | Image is pinned by tag, not digest |
| CI actions | `actions/checkout@v4`, `setup-python@v5`, `setup-node@v4`, `upload-artifact@v4`, `rustup stable` | CI only | — | Floating tags |

## Proposed NOTICE and README edits (not applied; for human review)

1. **NOTICE, Bundled content.** Name the upstream revision, say exactly what changed, and state the license evidence as observed:
   > `vittics_builder/skills/karpathy-guidelines.md` is the text of `CLAUDE.md` from
   > forrestchang/andrej-karpathy-skills (commit 8462496, January 2026), without its title line and with a
   > Vittics front-matter header naming the source. The upstream project states it is MIT-licensed (README,
   > plugin.json); it publishes no LICENSE file or copyright line.
2. **NOTICE, Third-party dependencies.** Split "installed from PyPI, not bundled" from the desktop installers, which **do** bundle a frozen Python runtime with these packages (PyInstaller) and Rust crates (Tauri). Add one line pointing to a generated per-release license inventory, once one exists.
3. **NOTICE, Provenance paragraph.** Keep the existing credit and claim. Add that commits since 2026-10-04 were largely written with AI assistance (Claude, recorded in commit trailers), so readers of an originality statement know how the code was produced.
4. **README, per-task security review.** Lines 9, 18 and 145 say every task gets a security review. The default `pipeline.review_mode: standard` runs one code review and one QA check per task; a security engineer reviews each task only in `thorough` mode, and small projects get one reviewer. Proposed wording for line 145: "Security engineer (reviews each task in `thorough` review mode)".

## Human contributions required

| Owner | Needed | Status |
| --- | --- | --- |
| Ram / Nikhil | Identity and role of the `thondapu lakshman` commits (`fc5aded`, `e1a61d9`); which human decisions shaped those modules | **Not received** |
| Any owner | Decision on the MIT notice question for the bundled skill file | **Not received** |
| Sai | Review of the desktop-bundle notice gap | **Not received** |
