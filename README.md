# RemixFlow — Video Remix Workflow

A local-first, traceable workflow console for short-form video remix production.

RemixFlow turns a messy production process into a clear 0–14 step chain: source selection, source understanding, visual fact checking, story design, narration, TTS, audio QC, shot mapping, audio-visual editing, packaging, full-video QC, user approval, and release assets.

## Two modes

- **Public Demo** — the GitHub Pages site uses fictional sample data. It is safe to share publicly and does not access local files.
- **Local Workspace** — run the Python server locally to connect the same interface to a real production workspace. You can edit Markdown/TXT/JSON files, record feedback, preview media, reveal files in Finder, and sync review/release outputs.

## Core principles

1. One current truth source per step.
2. Fix an error where it first appears; downstream stages should not silently patch upstream mistakes.
3. User feedback is written to a project feedback ledger and the relevant step QC file.
4. File existence is not treated as approval; explicit QC gates determine completion.
5. The public site and local workspace share the same UI, but private production data never needs to be published.

## Run locally

```bash
git clone https://github.com/711stoner/video-remix-workflow.git
cd video-remix-workflow
cp .env.example .env.local
# Edit VIDEO_REMIX_ROOT to point to your workspace
./start-local.command
```

Then open `http://127.0.0.1:8788`.

No Python packages are required; the backend uses the standard library.

## Expected workspace structure

The local adapter currently expects a Chinese-language production workspace with folders such as:

```text
02-方法论与规范/
03-二创文案与脚本/
04-下载原视频/
05-剪辑工程与成品/自动剪辑制作工程/
```

This mapping is intentionally isolated in `app.py`, so it can be adapted to other directory conventions.

## Public demo

GitHub Pages serves `docs/index.html`. When no local API is available, the UI automatically switches to Public Demo mode and uses fictional sample content.

## Privacy

- `.env.local`, logs, macOS metadata, and Python cache files are ignored by Git.
- The public demo contains no production media or user feedback.
- The local server only permits file operations inside the configured workspace and the current user's Desktop.

## Repository layout

```text
app.py                 Local standard-library HTTP backend
static/index.html      Local UI
docs/index.html        GitHub Pages public demo
start-local.command    Local launcher
.env.example           Example local configuration
```

## Status

This is an actively evolving production tool. The workflow model is opinionated by design: human review and traceability are prioritized over one-click automation.
