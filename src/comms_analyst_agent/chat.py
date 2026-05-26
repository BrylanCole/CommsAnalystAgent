"""chat.py — interactive chat-prompt entry point for the CommsAnalystAgent.

Usage:
    comms-analyst-chat                     # interactive mode
    comms-analyst-chat --prompt "..."      # non-interactive / CI mode
    comms-analyst-chat --prompt "..." \\
        --output-dir outputs --yes         # skip confirmation
"""

from __future__ import annotations

import sys
from pathlib import Path

from .pipeline import run_pipeline
from .prompt_parser import describe_config, parse_prompt

# ---------------------------------------------------------------------------
# Preset templates team members can pick from the menu
# ---------------------------------------------------------------------------
TEMPLATES: list[dict] = [
    {
        "name": "Product launch",
        "prompt": 'Track sentiment around "{topic}" product launch over the last 72 hours',
    },
    {
        "name": "Executive announcement",
        "prompt": 'Monitor coverage and sentiment for "{topic}" executive announcement over the last 48 hours',
    },
    {
        "name": "Crisis monitoring",
        "prompt": 'Track crisis, backlash, and negative sentiment around "{topic}" over the last 24 hours',
    },
    {
        "name": "Competitor reaction",
        "prompt": 'Analyse public reaction comparing "{topic}" vs competitors over the last 72 hours',
    },
    {
        "name": "Custom — type your own",
        "prompt": None,
    },
]

_SEPARATOR = "─" * 60


def _print_templates() -> None:
    print("\nChoose a monitoring template:\n")
    for i, t in enumerate(TEMPLATES, start=1):
        print(f"  [{i}] {t['name']}")
    print()


def _ask_template() -> str | None:
    """Return either a pre-filled prompt string or None (user chose custom)."""
    _print_templates()
    while True:
        raw = input("Enter template number (or press Enter to type your own): ").strip()
        if raw == "":
            return None
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(TEMPLATES):
                template = TEMPLATES[idx]
                if template["prompt"] is None:
                    return None
                topic = input("  What topic/product/name should I monitor? ").strip()
                if not topic:
                    print("  (topic cannot be empty, please try again)")
                    continue
                return template["prompt"].replace("{topic}", topic)
        except ValueError:
            pass
        print("  Please enter a number from the list above.")


def _ask_prompt() -> str:
    """Prompt the user to type their monitoring request."""
    print("\nDescribe what you want to monitor in plain English.")
    print('Examples:')
    print('  "Track sentiment around GitHub Copilot over the last 48 hours"')
    print('  "Monitor OpenAI Sora launch reactions, competitors: Runway, Pika"')
    print('  "Watch #AI #MachineLearning coverage last 3 days"\n')
    while True:
        raw = input("Your request: ").strip()
        if raw:
            return raw
        print("  (please enter a monitoring request)")


def _confirm_config(config_description: str) -> bool:
    """Show the interpreted config and ask for confirmation."""
    print(f"\n{_SEPARATOR}")
    print("Here is what I understood from your request:\n")
    print(config_description)
    print(_SEPARATOR)
    while True:
        answer = input("\nLooks good? Run the analysis now? [y/n]: ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("  Please type y or n.")


def _maybe_refine(prompt: str) -> str:
    """Allow the user to edit/refine their prompt before running."""
    print("\nYou can refine your request or press Enter to keep it as-is.")
    refined = input(f"  [{prompt}]: ").strip()
    return refined if refined else prompt


def run_chat(
    prompt: str | None = None,
    output_dir: str = "outputs",
    yes: bool = False,
) -> Path:
    """Run the interactive chat flow.

    Parameters
    ----------
    prompt:
        Pre-supplied prompt (skips interactive input when provided).
    output_dir:
        Root directory for generated report output.
    yes:
        If True, skip the confirmation step (useful for CI / non-interactive runs).

    Returns
    -------
    Path
        The directory that reports were written to.
    """
    print(f"\n{'═' * 60}")
    print("  Communications Intelligence Agent — Chat Mode")
    print(f"{'═' * 60}")

    # ── 1. Get prompt ──────────────────────────────────────────────────────
    if prompt:
        print(f"\nPrompt received: {prompt}\n")
    else:
        choice = _ask_template()
        if choice is not None:
            prompt = choice
        else:
            prompt = _ask_prompt()

    # ── 2. Parse prompt → config ───────────────────────────────────────────
    config = parse_prompt(prompt)
    description = describe_config(config)

    # ── 3. Confirm (unless --yes) ──────────────────────────────────────────
    if not yes:
        confirmed = _confirm_config(description)
        if not confirmed:
            prompt = _maybe_refine(prompt)
            config = parse_prompt(prompt)
            description = describe_config(config)
            print(f"\nUpdated interpretation:\n{description}\n")

    print("\n⏳  Collecting and analysing data — this may take a minute...\n")

    # ── 4. Run existing pipeline ───────────────────────────────────────────
    import tempfile, json, os
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        import dataclasses
        json.dump(dataclasses.asdict(config), tmp, indent=2)
        tmp_path = tmp.name

    try:
        output_path = run_pipeline(config_path=tmp_path, output_root=output_dir)
    finally:
        os.unlink(tmp_path)

    print(f"\n✅  Done!  Reports saved to:\n    {output_path}\n")
    print(f"    report.md  → open in any text editor or Markdown viewer")
    print(f"    report.json → structured data for further processing\n")
    return output_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Chat-driven communications intelligence analyst agent."
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Supply a monitoring request directly (skips interactive input).",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Root directory for run outputs (default: outputs).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation step (useful for scripting and CI).",
    )
    args = parser.parse_args()

    try:
        run_chat(
            prompt=args.prompt,
            output_dir=args.output_dir,
            yes=args.yes,
        )
    except KeyboardInterrupt:
        print("\n\n(Interrupted — no report generated.)\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
