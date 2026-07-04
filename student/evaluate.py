#!/usr/bin/env python3
"""
学生自测脚本 — 在全部 25 个任务上评测你的 Q1 和 Q2 Planner

用法：
  python evaluate.py [--output results.json]

输出：
  results.json — 详细评测结果（需要提交）
  终端 — 汇总表格

环境变量：
  OPENAI_API_KEY / LLM_API_KEY   — 你的 API Key
  LLM_PROVIDER                   — 默认 openai
  LLM_BASE_URL                   — API 地址（openai-compatible 时使用）
  LLM_MODEL                      — 模型名称
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from env.blocksworld_env import BlocksworldEnv
from llm_client import LLMClient


def load_all_tasks():
    tasks = []
    task_root = PROJECT_ROOT / "tasks"
    for sub in ["public", "hidden", "hard", "extreme", "nl_only"]:
        d = task_root / sub
        if d.is_dir():
            for fp in sorted(d.glob("*.json")):
                # 修改点：明确指定 encoding='utf-8'
                with open(fp, encoding='utf-8') as f:
                    t = json.load(f)
                    t["_source"] = f"tasks/{sub}"
                    tasks.append(t)
    return tasks


def make_student_task(task):
    st = dict(task)
    if st.get("nl_only"):
        st["initial_state"] = []
        st["goal_state"] = []
    return st


def normalise_plan(plan):
    out = []
    for a in plan:
        a = a.strip().lower().replace("-", "")
        parts = a.split(None, 1)
        if not parts: continue
        name = parts[0].upper()
        args = parts[1].split() if len(parts) > 1 else []
        args = [x.upper() for x in args]
        out.append(f"{name}({','.join(args)})")
    return out


def main():
    parser = argparse.ArgumentParser(description="学生自测脚本")
    parser.add_argument("--output", default="results.json", help="输出 JSON 路径")
    parser.add_argument("--provider", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--base-url", default=None)
    args = parser.parse_args()

    # LLM 配置
    provider = args.provider or os.environ.get("LLM_PROVIDER", "openai")
    model = args.model or os.environ.get("LLM_MODEL", "gpt-4o")
    api_key = args.api_key or os.environ.get("LLM_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
    base_url = args.base_url or os.environ.get("LLM_BASE_URL", None)
    if not api_key:
        print("[ERROR] 请设置 OPENAI_API_KEY 或 LLM_API_KEY 环境变量")
        sys.exit(1)

    llm_client = LLMClient(provider=provider, model=model, api_key=api_key, base_url=base_url)
    print(f"LLM: {provider}/{model}")

    # 导入学生代码
    sys.path.insert(0, str(PROJECT_ROOT / "my_planner"))
    try:
        import q1_llm_prompt_planner as q1
        import q2_llm_pddl_planner as q2
    except ImportError as e:
        print(f"[ERROR] 导入失败: {e}")
        sys.exit(1)

    # 加载任务
    tasks = load_all_tasks()
    print(f"任务数: {len(tasks)}")

    domain_path = PROJECT_ROOT / "pddl" / "domain.pddl"
    results = []
    q1_goal, q2_goal = 0, 0

    for i, task in enumerate(tasks):
        st = make_student_task(task)
        tid = task["task_id"]

        # Q1
        t0 = time.time()
        r1 = {"task_id": tid, "method": "q1", "goal_success": False, "plan_valid": False, "num_steps": 0}
        try:
            plan = q1.plan_with_llm(st, llm_client)
            if plan:
                env = BlocksworldEnv(task["blocks"])
                env.reset(task["initial_state"])
                er = env.execute_plan(plan)
                r1["plan_valid"] = er["plan_valid"]
                r1["goal_success"] = env.is_goal_satisfied(task["goal_state"])
                r1["num_steps"] = len(plan)
        except Exception as e:
            r1["error"] = str(e)[:200]
        r1["time_s"] = round(time.time() - t0, 2)
        if r1["goal_success"]: q1_goal += 1
        results.append(r1)

        # Q2
        t0 = time.time()
        r2 = {"task_id": tid, "method": "q2", "goal_success": False, "plan_valid": False, "num_steps": 0}
        try:
            plan = q2.plan_with_llm_pddl(st, str(domain_path), llm_client)
            if plan:
                nplan = normalise_plan(plan)
                env = BlocksworldEnv(task["blocks"])
                env.reset(task["initial_state"])
                er = env.execute_plan(nplan)
                r2["plan_valid"] = er["plan_valid"]
                r2["goal_success"] = env.is_goal_satisfied(task["goal_state"])
                r2["num_steps"] = len(nplan)
        except Exception as e:
            r2["error"] = str(e)[:200]
        r2["time_s"] = round(time.time() - t0, 2)
        if r2["goal_success"]: q2_goal += 1
        results.append(r2)

        print(f"  [{i+1}/{len(tasks)}] {tid}: Q1={'✓' if r1['goal_success'] else '✗'} Q2={'✓' if r2['goal_success'] else '✗'}")

    n = len(tasks)
    summary = {
        "total_tasks": n,
        "q1_goal_success": q1_goal,
        "q2_goal_success": q2_goal,
        "q1_rate": f"{q1_goal/n*100:.1f}%",
        "q2_rate": f"{q2_goal/n*100:.1f}%",
        "q1_score": round(25 * q1_goal / n, 1),
        "q2_score": round(30 * q2_goal / n, 1),
        "machine_total": round(25 * q1_goal / n + 30 * q2_goal / n, 1),
    }
    output = {"summary": summary, "details": results}

    with open(args.output, "w", encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n结果已保存: {args.output}")
    print(f"Q1: {q1_goal}/{n} ({summary['q1_rate']}) — {summary['q1_score']}/25 分")
    print(f"Q2: {q2_goal}/{n} ({summary['q2_rate']}) — {summary['q2_score']}/30 分")
    print(f"机器评分: {summary['machine_total']}/55 分")


if __name__ == "__main__":
    main()