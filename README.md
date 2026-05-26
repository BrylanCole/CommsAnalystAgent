# Communications Analyst Agent (MVP)

This repository contains a Python-based communications intelligence analyst agent that monitors public reactions to GitHub launches, announcements, and campaigns, then generates executive-ready reports.

## 1-Minute Quick Start (no coding experience needed)

### Step 1 — Install Python 3.11 (one-time setup)

On Mac, open **Terminal** and run:

```bash
brew install python@3.11
```

> No Homebrew? Install it first from https://brew.sh

### Step 2 — Download the project

Download this repository as a ZIP from GitHub (green **Code** button → **Download ZIP**) and unzip it into your Downloads folder.

### Step 3 — Set up and install (one-time)

```bash
cd ~/Downloads/CommsAnalystAgent-main
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

### Step 4 — Run in chat mode (recommended for teams)

```bash
comms-analyst-chat
```

The agent will:
1. Show a menu of monitoring templates (product launch, crisis, competitor, etc.)
2. Ask you to describe what you want to monitor in plain English
3. Confirm its interpretation before running
4. Generate a report in the `outputs/` folder

**Example prompt:**

```
Track sentiment around GitHub Copilot over the last 72 hours, competitors: OpenAI, GitLab
```

### Step 4b — Run in web dashboard mode (minimal UI)

```bash
comms-analyst-web
```

Open:

```text
http://127.0.0.1:8080
```

Use the prompt box to ask in plain English, then view generated reports from the dashboard list.

### Step 5 — Find your report

```text
outputs/<topic-name>/<timestamp>/report.md   ← open in any text editor
outputs/<topic-name>/<timestamp>/report.json ← structured data
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `python3.11: command not found` | Run `brew install python@3.11` first |
| `comms-analyst-chat: command not found` | Activate venv first: `source .venv/bin/activate`, then `pip install -e .` |
| `cd: no such file or directory` | Check the exact folder name — it may be `CommsAnalystAgent-main` after unzipping |
| `Python 3.9.6` when running `python --version` | Delete `.venv` and recreate: `rm -rf .venv && python3.11 -m venv .venv` |
| No output files generated | Check terminal for error messages; verify internet connection |

---

## What the agent does

- Collects evidence from practical GitHub-hosted sources (Google News RSS search, RSS feeds, Reddit search, Hacker News)
- Normalizes collected items into a shared schema (`title`, `url`, `source`, `author`, `published_at`, `snippet/content`, `channel`, observed engagement)
- Classifies sentiment into: Positive, Neutral, Negative, Mixed, Skeptical, Confused, Excited, Concerned
- Estimates overall trend labels: Strongly positive, Moderately positive, Mixed, Polarized, Negative, Escalating concern
- Detects narratives, praise/criticism/confusion patterns, risks, opportunities, and competitor comparisons
- Generates structured Markdown and JSON outputs for longitudinal tracking

## Architecture overview

- `src/comms_analyst_agent/config.py` – JSON configuration loader and monitoring target model
- `src/comms_analyst_agent/collectors.py` – source adapters and normalization pipeline
- `src/comms_analyst_agent/analysis.py` – sentiment + narrative analysis and trend labeling
- `src/comms_analyst_agent/reporting.py` – Markdown/JSON report generation
- `src/comms_analyst_agent/pipeline.py` – end-to-end orchestration
- `src/comms_analyst_agent/cli.py` – JSON config CLI entry point (`comms-analyst-agent`)
- `src/comms_analyst_agent/chat.py` – chat-prompt CLI entry point (`comms-analyst-chat`)
- `src/comms_analyst_agent/prompt_parser.py` – converts plain-English prompts → MonitoringConfig
- `config/monitoring_target.sample.json` – sample monitoring target configuration
- `config/templates/` – prompt template reference files for common use cases
- `.github/workflows/run-comms-analyst-agent.yml` – manual/scheduled GitHub Actions execution

## Chat mode (prompt-driven)

Run interactively:

```bash
comms-analyst-chat
```

Pass a prompt directly (for scripting or CI):

```bash
comms-analyst-chat --prompt "Track sentiment around OpenAI Sora last 48 hours" --yes
```

## Web dashboard mode (prompt + report browser)

Start the local web app:

```bash
comms-analyst-web --host 127.0.0.1 --port 8080 --output-dir outputs
```

Then open `http://127.0.0.1:8080`, enter your prompt, and run a report.
The dashboard lists recent reports with quick links to `report.md` and `report.json`.

### Prompt examples

```
Track sentiment around GitHub Copilot over the last 72 hours
Monitor OpenAI Sora product launch, competitors: Runway, Pika, Google last 48 hours
Track crisis and backlash around GitHub outage over the last 24 hours
Analyse #AI #MachineLearning coverage last 3 days
Monitor CEO Sam Altman executive announcement last 48 hours
```

### Built-in templates

Select from the interactive menu, or use a template as a starting point for your own prompt:

| Template | Best for |
|---|---|
| Product launch | 0–72 hours after a public launch |
| Executive announcement | CEO/CTO statements, interviews |
| Crisis monitoring | Outages, incidents, backlash |
| Competitor reaction | Comparative coverage analysis |

## Configure monitoring targets (advanced / JSON mode)

Create a JSON file (or copy `config/monitoring_target.sample.json`) with:

- `target_name`
- `launch_name`
- `github_terms`
- `executive_names`
- `hashtags`
- `competitors`
- `time_window_hours`
- `rss_feeds`
- `max_items_per_source`

Run with a config file:

```bash
comms-analyst-agent --config config/monitoring_target.sample.json --output-dir outputs
```

Outputs are written to:

```text
outputs/<target-slug>/<YYYYMMDD_HHMMSS>/report.md
outputs/<target-slug>/<YYYYMMDD_HHMMSS>/report.json
```

## Run via GitHub Actions

Workflow: `.github/workflows/run-comms-analyst-agent.yml`

- **Prompt mode**: trigger manually (`workflow_dispatch`), fill in the **Prompt** field with a plain-English request — no config file needed
- **Config mode**: leave Prompt blank and optionally provide a config path
- Runs automatically every 12 hours (`schedule`)
- Uploads generated reports as workflow artifacts

## Source limitations and extensibility

This MVP avoids proprietary/private APIs. It is designed for sources that typically work in GitHub-hosted environments.

Current source adapters:
- Google News RSS search
- RSS feeds
- Reddit search JSON endpoint
- Hacker News (Algolia API)

Some social networks (X, LinkedIn, Threads, TikTok) usually require official APIs, credentials, and policy-compliant access for reliable coverage. The collector module is adapter-based so those sources can be added later.

## Validation

Run tests with:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```
