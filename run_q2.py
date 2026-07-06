#!/usr/bin/env python3
"""
Q2 Runner — Teacher-Provided

Runs the LLM + PDDL Planner on a single task and prints the result.

Usage:
    python run_q2.py --task tasks/public/task_02.json

Environment variables (optional):
    OPENAI_API_KEY       OpenAI API key
    ANTHROPIC_API_KEY    Anthropic API key
    LLM_PROVIDER         "openai" (default), "anthropic", or "openai-compatible"
    LLM_MODEL            Model name (default: gpt-4o / claude-sonnet-4-6)
    LLM_BASE_URL         Base URL for openai-compatible providers
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from env.blocksworld_env import BlocksworldEnv
from llm_client import LLMClient


def load_task(task_path: str) -> dict:
    """Load a task JSON file."""
    with open(task_path, "r") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Run Q2: LLM + PDDL Planner")
    parser.add_argument(
        "--task", type=str, required=True,
        help="Path to task JSON file, e.g. tasks/public/task_02.json"
    )
    parser.add_argument(
        "--domain", type=str, default=None,
        help="Path to domain.pddl (default: pddl/domain.pddl)"
    )
    parser.add_argument(
        "--output-dir", type=str, default=None,
        help="Directory to save generated problem.pddl (default: outputs/<task_id>/)"
    )
    parser.add_argument(
        "--provider", type=str, default=None,
        help="LLM provider (overrides LLM_PROVIDER env var)"
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="Model name (overrides LLM_MODEL env var)"
    )
    parser.add_argument(
        "--api-key", type=str, default=None,
        help="API key (overrides env vars)"
    )
    parser.add_argument(
        "--base-url", type=str, default=None,
        help="Base URL for openai-compatible providers"
    )
    args = parser.parse_args()

    # ── Load task ────────────────────────────────────────────────────
    task_path = Path(args.task)
    if not task_path.exists():
        print(f"[ERROR] Task file not found: {task_path}")
        sys.exit(1)

    task = load_task(str(task_path))
    print(f"Task: {task['task_id']}")
    print(f"Method: LLM + PDDL Planner (Q2)")
    print(f"Blocks: {', '.join(task['blocks'])}")

    # ── Domain path ──────────────────────────────────────────────────
    domain_path = args.domain or str(PROJECT_ROOT / "pddl" / "domain.pddl")
    if not Path(domain_path).exists():
        print(f"[ERROR] Domain file not found: {domain_path}")
        sys.exit(1)
    print(f"Domain: {domain_path}")

    # ── Output directory ────────────────────────────────────────────
    output_dir = Path(args.output_dir or PROJECT_ROOT / "outputs" / task["task_id"])
    output_dir.mkdir(parents=True, exist_ok=True)
    problem_path = output_dir / "problem.pddl"
    print(f"Output: {output_dir}/")
    print()

    # ── Resolve LLM config ──────────────────────────────────────────
    provider = args.provider or os.environ.get("LLM_PROVIDER", "openai")
    model = args.model or os.environ.get("LLM_MODEL", None)
    api_key = args.api_key or None
    base_url = args.base_url or os.environ.get("LLM_BASE_URL", None)

    try:
        llm_client = LLMClient(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
        )
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    # ── Import student planner ──────────────────────────────────────
    sys.path.insert(0, str(PROJECT_ROOT / "my_planner"))
    try:
        from q2_llm_pddl_planner import plan_with_llm_pddl
    except ImportError as e:
        print(f"[ERROR] Failed to import student planner: {e}")
        print("Make sure my_planner/q2_llm_pddl_planner.py exists and "
              "implements plan_with_llm_pddl().")
        sys.exit(1)

    # ── Plan ────────────────────────────────────────────────────────
    # For NL-only tasks, hide structured states from the student
    student_task = dict(task)
    if task.get("nl_only"):
        student_task["initial_state"] = []
        student_task["goal_state"] = []

    print("Generating PDDL problem via LLM and solving ...")
    try:
        plan = plan_with_llm_pddl(student_task, domain_path, llm_client)
    except Exception as e:
        print(f"[ERROR] LLM+PDDL planning failed: {e}")
        sys.exit(1)

    if not plan:
        print("[ERROR] Planner returned an empty plan.")
        sys.exit(1)

    # ── Print plan ──────────────────────────────────────────────────
    print("\nPlanner plan:")
    for i, action in enumerate(plan, 1):
        print(f"  {i}. {action}")

    # ── Normalise action format (lowercase, remove dashes) ──────────
    # PDDL planners typically output lowercase, e.g. "unstack c a"
    # Convert to uppercase BlocksworldEnv format: "UNSTACK(C,A)"
    normalised_plan = _normalise_plan(plan)
    if normalised_plan != plan:
        print("\nNormalised plan:")
        for i, action in enumerate(normalised_plan, 1):
            print(f"  {i}. {action}")

    # ── Validate in environment ─────────────────────────────────────
    env = BlocksworldEnv(task["blocks"])
    env.reset(task["initial_state"])

    result = env.execute_plan(normalised_plan)
    goal_success = env.is_goal_satisfied(task["goal_state"])

    print(f"\nPlan valid: {result['plan_valid']}")
    print(f"Goal achieved: {goal_success}")
    print(f"Number of steps: {len(normalised_plan)}")

    if result["failed_step"] is not None:
        print(f"Failed at step {result['failed_step']}: "
              f"{result['failed_action']}")

    # ── Render final state ──────────────────────────────────────────
    print("\nFinal state:")
    print(env.render())

    # ── Exit code ───────────────────────────────────────────────────
    if not (result["plan_valid"] and goal_success):
        sys.exit(1)


def _normalise_plan(plan: list) -> list:
    """
    Convert planner output (e.g. lowercase, dashed) to canonical form.

    e.g. "unstack c a" → "UNSTACK(C,A)"
         "pick-up a"   → "PICKUP(A)"
    """
    import re

    normalised = []
    for action in plan:
        action = action.strip().lower()
        # Remove dashes: "pick-up" → "pickup"
        action_clean = action.replace("-", "")
        # Split into name + args: "unstack c a" → ("unstack", "c a")
        parts = action_clean.split(None, 1)
        if len(parts) == 0:
            continue
        name = parts[0].upper()
        args_raw = parts[1] if len(parts) > 1 else ""
        args_list = [a.strip().upper() for a in args_raw.split() if a.strip()]
        normalised.append(f"{name}({','.join(args_list)})")
    return normalised


if __name__ == "__main__":
    main()
