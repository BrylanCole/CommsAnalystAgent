from __future__ import annotations

import datetime as dt
from pathlib import Path

from .analysis import analyze_items
from .collectors import collect_all
from .config import load_config
from .reporting import build_json_output, build_markdown_report, write_outputs


def run_pipeline(config_path: str, output_root: str = "outputs") -> Path:
    config = load_config(config_path)
    items = collect_all(config)
    analysis = analyze_items(items, config)
    markdown = build_markdown_report(config, analysis)
    json_payload = build_json_output(config, analysis)

    run_id = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    target_slug = "-".join(config.target_name.lower().split())
    output_dir = Path(output_root) / target_slug / run_id
    write_outputs(output_dir, markdown, json_payload)
    return output_dir
