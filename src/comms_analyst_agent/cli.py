from __future__ import annotations

import argparse

from .pipeline import run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run communications intelligence analyst pipeline.")
    parser.add_argument("--config", required=True, help="Path to JSON monitoring configuration")
    parser.add_argument("--output-dir", default="outputs", help="Root directory for run outputs")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = run_pipeline(config_path=args.config, output_root=args.output_dir)
    print(f"Report generated at: {output_dir}")


if __name__ == "__main__":
    main()
