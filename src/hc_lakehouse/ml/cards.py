"""Model card generation (research / decision-support disclaimer required)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hc_lakehouse.ml.splits import DISCLAIMER
from hc_lakehouse.utils.config import REPO_ROOT
from hc_lakehouse.utils.logging import get_logger

logger = get_logger(__name__)


def render_model_card(
    *,
    model_name: str,
    version: str,
    intended_use: str,
    features: list[str],
    metrics: dict[str, Any],
    fairness: list[dict[str, Any]],
    training_notes: str,
) -> str:
    """Return markdown model card text."""
    fair_lines = ["| slice | value | n | accuracy | auc |", "|---|---|---:|---:|---:|"]
    for row in fairness[:40]:
        fair_lines.append(
            f"| {row.get('slice_column')} | {row.get('slice_value')} | {row.get('n')} | "
            f"{row.get('accuracy')} | {row.get('auc')} |"
        )
    return "\n".join(
        [
            f"# Model card: {model_name}",
            "",
            f"- **Version:** {version}",
            f"- **Generated:** {datetime.now(timezone.utc).isoformat()}",
            "",
            "## Critical disclaimer",
            "",
            DISCLAIMER,
            "",
            "## Intended use",
            "",
            intended_use,
            "",
            "## Features",
            "",
            ", ".join(f"`{f}`" for f in features),
            "",
            "## Overall metrics",
            "",
            "```json",
            str(metrics),
            "```",
            "",
            "## Fairness / subgroup performance",
            "",
            *fair_lines,
            "",
            "## Training notes",
            "",
            training_notes,
            "",
            "## Out of scope",
            "",
            "- Not for diagnosis, triage, or autonomous clinical decision-making.",
            "- Not validated as a medical device.",
            "",
        ]
    )


def write_model_card(
    content: str,
    model_name: str,
    *,
    output_dir: Path | None = None,
) -> Path:
    out = output_dir or (REPO_ROOT / "docs" / "model_cards")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{model_name}.md"
    path.write_text(content, encoding="utf-8")
    # Mirror under artifacts for CI/demo
    art = REPO_ROOT / "artifacts" / "model_cards"
    art.mkdir(parents=True, exist_ok=True)
    (art / f"{model_name}.md").write_text(content, encoding="utf-8")
    logger.info("model_card_written", extra={"path": str(path)})
    return path
