"""
Q2: LLM 生成 PDDL 问题文件，然后由 pyperplan 求解
最终完美版：彻底禁止目标冲突，自动修正
"""

import re
from pathlib import Path
from typing import List, Dict, Any

from pyperplan import planner
from pyperplan.search import breadth_first_search


def build_pddl_prompt(task: Dict[str, Any], domain_pddl: str) -> str:
    """
    构造 Prompt：明确禁止目标中的冲突，增加反例。
    """
    task_id = task.get("task_id", "unknown")
    natural_language = task.get("natural_language", "")
    initial = task.get("initial_state", [])
    goal = task.get("goal_state", [])

    # 示例：正确与错误对比
    example_good = """
示例1（正确）：
初始状态：(ontable A) (on B A) (on C B) (clear C) (handempty)
目标：(and (ontable C) (on B C) (on A B))
说明：每个积木只有一个位置，C 在桌上，B 在 C 上，A 在 B 上。
"""
    example_bad = """
示例2（错误 — 冲突）：
目标：(and (on E D) (ontable E) ...)   # E 同时出现在 on 和 ontable 中，非法！
正确做法：要么 (on E D)，要么 (ontable E)，不能同时出现。
"""
    example_direction = """
示例3（方向说明 — 重要！）：
自然语言："从桌面往上依次是 A, B, C, D" — 表示 A 在桌面，B 在 A 上，C 在 B 上，D 在 C 上。
→ 初始：(ontable A) (on B A) (on C B) (on D C) (clear D) (handempty)
→ 目标：(and (on D C) (on C B) (on B A) (ontable A))
注意：(on x y) 中 x 在 y 的上面，y 在 x 的下面！
底部块（A）在 ontable，顶部块（D）只出现在 on 的左侧（作为 x 而不是 y）。
"""
    prompt = f"""你是一个 PDDL 问题生成专家。请为积木世界任务生成一个**语法完全正确**的 PDDL 问题文件。

### 域定义
{domain_pddl}

### 关键规则（必须遵守）
1. `(on x y)` 表示 x 直接放在 y 上面，方向很重要！
2. 初始状态必须：
   - 为每个积木指定唯一位置（ontable 或 on）。
   - 为每个顶层积木指定 `(clear x)`。
   - 包含 `(handempty)`。
   - **不能**包含任何 `(holding ...)` 谓词。
3. **目标状态**：
   - 每个积木只能有一个位置（要么 `ontable`，要么 `on`），**禁止同时出现**。
   - **不能**包含 `(handempty)` 或 `(not ...)`（域中无此谓词）。
   - 用 `(and ...)` 包裹。
4. 所有参数用空格分隔，例如 `(on A B)`。

### 正确示例
{example_good}
### 方向说明（必读 — 防止方向错误）
{example_direction}
### 错误示例（请避免）
{example_bad}

### 当前任务
任务ID：{task_id}
""".strip()

    if initial and goal:
        prompt += f"\n初始状态：{', '.join(initial)}\n目标状态：{', '.join(goal)}"
    else:
        prompt += f"\n自然语言描述：{natural_language}（请据此推断初始状态和目标状态）"

    prompt += "\n\n只输出 PDDL 代码，不要注释或解释。"
    return prompt


def fix_goal_conflicts(goal_str: str) -> str:
    """
    自动修正目标中的冲突：如果某个积木同时出现在 on 和 ontable 中，移除 ontable。
    """
    # 提取所有 on 关系
    on_pairs = re.findall(r'\(on\s+([A-Z]+)\s+([A-Z]+)\)', goal_str)
    on_blocks = {b for pair in on_pairs for b in pair}
    # 如果某积木在 on 中出现，则删除其 ontable 谓词
    if on_blocks:
        # 删除形如 (ontable X) 的谓词，其中 X 在 on_blocks 中
        for b in on_blocks:
            goal_str = re.sub(r'\(ontable\s+' + b + r'\)', '', goal_str)
    # 删除 handempty 和 not（如果有）
    goal_str = re.sub(r'\(handempty\)', '', goal_str)
    goal_str = re.sub(r'\(not\s+[^)]*\)', '', goal_str)
    # 清理多余空格
    goal_str = re.sub(r'\s+', ' ', goal_str).strip()
    # 如果目标变成空，则保留一个占位（但不会发生）
    if goal_str == "()" or not goal_str:
        goal_str = "(and)"
    return goal_str


def generate_problem_pddl(task: Dict[str, Any], domain_pddl: str, llm_client) -> str:
    """
    调用 LLM 生成 PDDL，清洗并自动修补。
    """
    prompt = build_pddl_prompt(task, domain_pddl)
    response = llm_client.chat(prompt)

    cleaned = response.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split('\n')
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = '\n'.join(lines)

    blocks = task.get("blocks", [])
    if blocks and ":objects" not in cleaned:
        obj_line = f"  (:objects {' '.join(blocks)} - block)"
        lines = cleaned.split('\n')
        new_lines = []
        inserted = False
        for line in lines:
            new_lines.append(line)
            if not inserted and line.strip().startswith("(define"):
                new_lines.append(obj_line)
                inserted = True
        cleaned = '\n'.join(new_lines)

    # 确保 :init 包含 handempty
    if ":init" in cleaned and "handempty" not in cleaned:
        cleaned = cleaned.replace("(:init", "(:init (handempty)")

    # 修复目标中的冲突
    if ":goal" in cleaned:
        # 提取 :goal 内容
        goal_match = re.search(r'\(:goal\s*\((and|and\s+)([^)]*)\)\)', cleaned, re.DOTALL)
        if goal_match:
            goal_body = goal_match.group(2)
            fixed_body = fix_goal_conflicts(goal_body)
            cleaned = cleaned[:goal_match.start(2)] + fixed_body + cleaned[goal_match.end(2):]

    return cleaned.strip()


def solve_pddl(domain_path: str, problem_path: str) -> List[str]:
    """
    调用规划器，返回动作名称列表（如 "pickup a"）。
    """
    try:
        plan = planner.search_plan(domain_path, problem_path, breadth_first_search, None)
        if plan is None:
            return []
        actions = []
        for action in plan:
            action_str = str(action).strip().split('\n')[0]
            if action_str.startswith('(') and action_str.endswith(')'):
                action_str = action_str[1:-1]
            actions.append(action_str)
        return actions
    except Exception as e:
        print(f"[Q2] 规划求解异常: {e}")
        return []


def plan_with_llm_pddl(task: Dict[str, Any], domain_path: str, llm_client) -> List[str]:
    """
    完整 Q2 流程，带重试。
    """
    with open(domain_path, 'r', encoding='utf-8') as f:
        domain_pddl = f.read()

    task_id = task.get("task_id", "unknown")
    output_dir = Path("outputs") / task_id
    output_dir.mkdir(parents=True, exist_ok=True)

    for attempt in range(2):
        problem_pddl = generate_problem_pddl(task, domain_pddl, llm_client)
        if not problem_pddl:
            print(f"[Q2] 第 {attempt+1} 次生成 PDDL 为空，重试...")
            continue

        problem_path = output_dir / "problem.pddl"
        with open(problem_path, 'w', encoding='utf-8') as f:
            f.write(problem_pddl)
        print(f"[Q2] PDDL 已保存: {problem_path}")

        plan = solve_pddl(domain_path, str(problem_path))
        if plan:
            plan_path = output_dir / "plan.txt"
            with open(plan_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(plan))
            print(f"[Q2] 规划成功，步数: {len(plan)}，计划已保存: {plan_path}")
            print(f"[Q2] 计划: {plan}")
            return plan
        else:
            print(f"[Q2] 第 {attempt+1} 次规划失败")
            with open(problem_path, 'r', encoding='utf-8') as f:
                print(f"[Q2] 问题文件内容:\n{f.read()}")

    return []