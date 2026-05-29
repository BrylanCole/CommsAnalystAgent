from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from .analysis import analyze_items
from .collectors import CollectionDiagnostics, collect_all
from .config import load_config
from .reporting import build_json_output, build_markdown_report, build_slack_summary, write_outputs


def build_target_slug(target_name: str) -> str:
    normalized = re.sub(r"\s+", "-", target_name.lower().strip())
    sanitized = re.sub(r"[^a-z0-9._-]", "", normalized)
    sanitized = re.sub(r"-{2,}", "-", sanitized).strip("-._")
    return sanitized or "target"


def run_pipeline(config_path: str, output_root: str = "outputs") -> Path:
    config = load_config(config_path)
    diagnostics = CollectionDiagnostics()
    items = collect_all(config, diagnostics=diagnostics)
    analysis = analyze_items(items, config)
    markdown = build_markdown_report(config, analysis, diagnostics=diagnostics)
    json_payload = build_json_output(config, analysis, diagnostics=diagnostics)
    slack_summary = build_slack_summary(config, analysis, diagnostics=diagnostics)

    run_id = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    target_slug = build_target_slug(config.target_name)
    output_dir = Path(output_root) / target_slug / run_id
    write_outputs(output_dir, markdown, json_payload, slack_summary)
    return output_dir
