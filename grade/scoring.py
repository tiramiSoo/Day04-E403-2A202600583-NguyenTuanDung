from __future__ import annotations

import argparse
import importlib
import json
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.llm import judge_answer_with_llm
from core.schemas import AgentResult, ToolCallRecord


@dataclass
class CaseScore:
    case_id: str
    score: float
    max_score: float
    feedback: list[str]


def load_cases(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def coerce_result(raw: Any, *, query: str, provider: str, model_name: str | None) -> AgentResult:
    if isinstance(raw, AgentResult):
        return raw
    if isinstance(raw, str):
        return AgentResult(query=query, final_answer=raw, provider=provider, model_name=model_name)
    if isinstance(raw, dict):
        return AgentResult(**raw)
    raise TypeError(f"Unsupported run_agent result type: {type(raw)!r}")


def grade_result(
    result: AgentResult,
    case: dict[str, Any],
    *,
    judge_provider: str | None = None,
    judge_model_name: str | None = None,
) -> CaseScore:
    expected = case["expected"]
    weights = case["weights"]
    earned = 0.0
    feedback: list[str] = []
    answer = result.final_answer.lower()

    required_keywords = [item.lower() for item in expected.get("required_keywords", [])]
    keyword_hits = sum(1 for keyword in required_keywords if keyword in answer)
    if required_keywords:
        keyword_score = weights["keywords"] * (keyword_hits / len(required_keywords))
        earned += keyword_score
        if keyword_hits < len(required_keywords):
            missing = [keyword for keyword in required_keywords if keyword not in answer]
            feedback.append(f"Missing required keywords: {missing}.")
    else:
        earned += weights["keywords"]

    forbidden_keywords = [item.lower() for item in expected.get("forbidden_keywords", [])]
    violations = [keyword for keyword in forbidden_keywords if keyword in answer]
    if not violations:
        earned += weights["safety"]
    else:
        feedback.append(f"Answer contains forbidden keywords: {violations}.")

    required_tools = expected.get("required_tools", [])
    tool_names = [tool.name for tool in result.tool_calls]
    if all(tool in tool_names for tool in required_tools):
        earned += weights["tools"]
    else:
        missing_tools = [tool for tool in required_tools if tool not in tool_names]
        feedback.append(f"Missing required tools: {missing_tools}.")

    if judge_provider:
        judge = judge_answer_with_llm(
            query=result.query,
            answer=result.final_answer,
            rubric=expected.get("grading_rubric", ""),
            provider=judge_provider,
            model_name=judge_model_name,
        )
        earned += weights["llm_judge"] * (judge["score"] / 10)
        feedback.extend(judge["feedback"])
    else:
        earned += weights["llm_judge"]

    return CaseScore(
        case_id=case["id"],
        score=round(earned, 2),
        max_score=float(sum(weights.values())),
        feedback=feedback,
    )


def summarize_scores(scores: list[CaseScore]) -> dict[str, Any]:
    total_earned = sum(item.score for item in scores)
    total_max = sum(item.max_score for item in scores)
    overall = round((total_earned / total_max) * 100, 2) if total_max else 0.0
    return {
        "overall_score": overall,
        "total_earned": total_earned,
        "total_max": total_max,
        "cases": [
            {
                "case_id": item.case_id,
                "score": item.score,
                "max_score": item.max_score,
                "feedback": item.feedback,
            }
            for item in scores
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Grade final answers for the TravelBuddy create_agent lab")
    parser.add_argument("--module", default="agent.graph")
    parser.add_argument("--cases", default=str(ROOT_DIR / "data" / "graded_cases.json"))
    parser.add_argument("--provider", default="google", choices=["google", "ollama"])
    parser.add_argument("--model-name", default=None)
    parser.add_argument("--today", default="2026-05-31")
    parser.add_argument("--pass-threshold", type=float, default=80.0)
    parser.add_argument("--judge-provider", default=None, choices=["google", "ollama"])
    parser.add_argument("--judge-model-name", default=None)
    args = parser.parse_args()

    module = importlib.import_module(args.module)
    if not hasattr(module, "run_agent"):
        raise SystemExit(f"Module {args.module} does not expose run_agent()")

    cases = load_cases(Path(args.cases))
    scores = []
    for case in cases:
        raw_result = module.run_agent(
            case["query"],
            provider=args.provider,
            model_name=args.model_name,
            today=args.today,
        )
        result = coerce_result(raw_result, query=case["query"], provider=args.provider, model_name=args.model_name)
        scores.append(
            grade_result(
                result,
                case,
                judge_provider=args.judge_provider,
                judge_model_name=args.judge_model_name,
            )
        )

    summary = summarize_scores(scores)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["overall_score"] >= args.pass_threshold else 1


if __name__ == "__main__":
    raise SystemExit(main())
