"""Offline rubric judge calibration harness.

Runs golden rubric cases through the live grader and compares each criterion
verdict against human labels, reporting precision/recall/cohen's kappa.

Only makes live API calls when RUN_JUDGE_EVAL=1 (slow/eval mode). Otherwise it
prints a short skip message and exits 0.

Usage:
    RUN_JUDGE_EVAL=1 uv run python scripts/eval_judge.py
    RUN_JUDGE_EVAL=1 uv run python scripts/eval_judge.py --cases tests/eval/golden_rubric_cases.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agents.calibration import cohen_kappa, precision_recall
from src.agents.middleware.rubric import grade_with_rubric


async def _grade_case(case: dict) -> list[dict]:
    result = await grade_with_rubric(
        content=case["content"],
        rubric=case["rubric"],
        evidence=case.get("evidence", ""),
        max_iterations=1,
    )
    evaluations = result.get("evaluations", [])
    if not evaluations:
        return []
    return evaluations[-1].get("criteria", [])


async def _run(cases: list[dict]) -> int:
    y_true: list[bool] = []
    y_pred: list[bool] = []
    mismatches: list[dict] = []
    total_criteria = 0

    for case in cases:
        predicted = await _grade_case(case)
        for expected in case["criteria"]:
            total_criteria += 1
            match = next(
                (c for c in predicted if c["name"] == expected["name"]), None
            )
            actual = bool(match["passed"]) if match else False
            y_true.append(bool(expected["passed"]))
            y_pred.append(actual)
            if actual != bool(expected["passed"]):
                mismatches.append(
                    {
                        "case": case["id"],
                        "criterion": expected["name"],
                        "expected": expected["passed"],
                        "predicted": actual,
                    }
                )

    precision, recall = precision_recall(y_true, y_pred)
    kappa = cohen_kappa(y_true, y_pred)
    report = {
        "criteria_graded": total_criteria,
        "mismatches": mismatches,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "cohen_kappa": round(kappa, 3),
    }
    print(json.dumps(report, indent=2))
    return 0 if not mismatches else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Rubric judge calibration harness")
    parser.add_argument(
        "--cases", default="tests/eval/golden_rubric_cases.json"
    )
    args = parser.parse_args()

    if os.environ.get("RUN_JUDGE_EVAL") != "1":
        print("RUN_JUDGE_EVAL != 1; skipping live judge eval (no API calls).")
        return 0

    cases_path = Path(args.cases)
    data = json.loads(cases_path.read_text())
    return asyncio.run(_run(data["cases"]))


if __name__ == "__main__":
    raise SystemExit(main())
