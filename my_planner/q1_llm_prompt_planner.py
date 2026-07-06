"""
Q1: 纯LLM直接输出动作序列
v6: 渐进式 prompt — 5例→7例→推理，3次重试
"""

import re
from typing import List, Dict, Any, Tuple

from env.blocksworld_env import BlocksworldEnv


def _action_rules() -> str:
    return """
动作格式及前提（必须严格遵守）：
- PICKUP(x)  : 前提：ontable(x), clear(x), handempty
- PUTDOWN(x) : 前提：holding(x)
- UNSTACK(x,y): 前提：on(x,y), clear(x), handempty   (x 在 y 上面)
- STACK(x,y)  : 前提：holding(x), clear(y)          (把 x 放到 y 上面)
重要：on(x,y) 表示 x 直接放在 y 上面，方向绝不能反！
规划策略：先拆后建 — 先将需要移动的积木拆下，再按目标顺序堆叠。
"""


def _examples_5() -> list:
    return [
        """
示例1：
初始：ontable(A), on(B,A), clear(B), handempty
目标：on(A,B), ontable(B)
动作序列：
UNSTACK(B,A)
PUTDOWN(B)
PICKUP(A)
STACK(A,B)
""",
        """
示例2（自然语言）：
自然语言：A在桌上，B在A上，C在B上，手空。目标：C在桌上，B在C上，A在B上。
推断初始：ontable(A), on(B,A), on(C,B), clear(C), handempty
目标：ontable(C), on(B,C), on(A,B)
动作序列：
UNSTACK(C,B)
PUTDOWN(C)
UNSTACK(B,A)
STACK(B,C)
PICKUP(A)
STACK(A,B)
""",
        """
示例3（全在桌面建塔）：
初始：ontable(A), ontable(B), ontable(C), clear(A), clear(B), clear(C), handempty
目标：on(A,B), on(B,C), ontable(C)
动作序列：
PICKUP(B)
STACK(B,C)
PICKUP(A)
STACK(A,B)
""",
        """
示例4（5块反转）：
初始：ontable(A), on(B,A), on(C,B), on(D,C), on(E,D), clear(E), handempty
目标：ontable(E), on(D,E), on(C,D), on(B,C), on(A,B)
动作序列：
UNSTACK(E,D)
PUTDOWN(E)
UNSTACK(D,C)
STACK(D,E)
UNSTACK(C,B)
STACK(C,D)
UNSTACK(B,A)
STACK(B,C)
PICKUP(A)
STACK(A,B)
""",
        """
示例5（交换塔顶）：
初始：on(C,B), on(B,A), ontable(A), clear(C), on(F,E), on(E,D), ontable(D), clear(F), handempty
目标：on(B,C), on(C,A), ontable(A), on(E,F), on(F,D), ontable(D)
动作序列：
UNSTACK(C,B)
PUTDOWN(C)
UNSTACK(B,A)
PUTDOWN(B)
PICKUP(C)
STACK(C,A)
PICKUP(B)
STACK(B,C)
UNSTACK(F,E)
PUTDOWN(F)
UNSTACK(E,D)
PUTDOWN(E)
PICKUP(F)
STACK(F,D)
PICKUP(E)
STACK(E,F)
"""
    ]


def _examples_7() -> list:
    return _examples_5() + [
        """
示例6（自然语言 — 合并多塔）：
自然语言：A在桌上，B在A上。C在桌上，D在C上。E在桌上，F在E上。手空。目标从桌面往上：A, B, C, D, E, F（一个大塔）。
推断初始：on(B,A), ontable(A), clear(B), on(D,C), ontable(C), clear(D), on(F,E), ontable(E), clear(F), handempty
目标：on(F,E), on(E,D), on(D,C), on(C,B), on(B,A), ontable(A)
动作序列：
UNSTACK(B,A)
PUTDOWN(B)
UNSTACK(D,C)
PUTDOWN(D)
UNSTACK(F,E)
PUTDOWN(F)
PICKUP(B)
STACK(B,A)
PICKUP(C)
STACK(C,B)
PICKUP(D)
STACK(D,C)
PICKUP(E)
STACK(E,D)
PICKUP(F)
STACK(F,E)
""",
        """
示例7（跨堆交插重组）：
自然语言：G在F上，F在A上，A在桌。E在D上，D在B上，B在桌。C单独在桌。目标：D在G上，G在C上，C在A上，A在桌。F在E上，E在B上，B在桌。
推断初始：on(G,F), on(F,A), ontable(A), clear(G), on(E,D), on(D,B), ontable(B), clear(E), ontable(C), clear(C), handempty
目标：on(D,G), on(G,C), on(C,A), ontable(A), on(F,E), on(E,B), ontable(B)
动作序列：
UNSTACK(G,F)
PUTDOWN(G)
UNSTACK(F,A)
PUTDOWN(F)
UNSTACK(E,D)
PUTDOWN(E)
UNSTACK(D,B)
PUTDOWN(D)
PICKUP(C)
STACK(C,A)
PICKUP(G)
STACK(G,C)
PICKUP(D)
STACK(D,G)
PICKUP(E)
STACK(E,B)
PICKUP(F)
STACK(F,E)
"""
    ]


def build_prompt(task: Dict[str, Any], variant: int = 0) -> str:
    """精简 prompt。variant=0: 5例, variant=1: 7例。"""
    examples = _examples_5() if variant == 0 else _examples_7()

    prompt = f"""你是一个积木世界规划器。

动作规则：
{_action_rules()}

以下示例展示了如何根据状态或自然语言输出动作序列：

{''.join(examples)}

请先推断初始状态和目标状态（用谓词列表表示），然后输出动作序列。
on(x,y) 中 x 在上面、y 在下面，方向绝不能反！
无关节木不要移动（如任务说"不要移动D"，就不要操作D）。
最多输出 30 步。

输出格式：
初始状态：<谓词列表>
目标状态：<谓词列表>
动作序列：
<动作1>
<动作2>
...

当前任务：
任务ID：{task.get('task_id', 'unknown')}
"""
    natural_language = task.get("natural_language", "")
    initial = task.get("initial_state", [])
    goal = task.get("goal_state", [])

    if initial and goal:
        prompt += f"初始状态：{', '.join(initial)}\n目标状态：{', '.join(goal)}\n"
    else:
        prompt += f"自然语言描述：{natural_language}\n"

    prompt += "请输出（先状态，后动作）：\n"
    return prompt


def build_prompt_reasoning(task: Dict[str, Any], error_msg: str = "") -> str:
    """推理 prompt — 要求逐步推理跟踪状态。"""
    prompt = f"""你是一个积木世界规划器。你需要逐步推理，跟踪每一步执行后的状态。

动作规则：
{_action_rules()}

你必须按照以下格式输出：
1. 初始状态推断：<谓词列表>
2. 目标状态推断：<谓词列表>
3. 推理过程（逐步跟踪状态）：每步写"当前状态 → 执行动作 → 新状态"
4. 最终动作序列：（每行一个动作）

重要：on(x,y) 中 x 在上面、y 在下面。最多 30 步。无关节木不移动。

当前任务：
任务ID：{task.get('task_id', 'unknown')}
"""
    natural_language = task.get("natural_language", "")
    initial = task.get("initial_state", [])
    goal = task.get("goal_state", [])

    if initial and goal:
        prompt += f"初始状态：{', '.join(initial)}\n目标状态：{', '.join(goal)}\n"
    else:
        prompt += f"自然语言描述：{natural_language}\n"

    if error_msg:
        prompt += f"""
你之前的计划有误：
{error_msg}

请仔细检查状态变化，重新输出。
"""

    prompt += "请输出（先推理，后动作序列）：\n"
    return prompt


def parse_llm_output(response: str, blocks: List[str] = None) -> List[str]:
    if blocks is None:
        blocks = []
    valid_actions = {"PICKUP", "PUTDOWN", "UNSTACK", "STACK"}
    actions = []

    action_part = response
    for marker in ["最终动作序列：", "动作序列：", "动作："]:
        if marker in response:
            parts = response.split(marker, 1)
            action_part = parts[1].strip()
            break

    lines = action_part.split('\n')
    pattern = re.compile(r'^([A-Z]+)\(([A-Z,]*)\)$')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        line = re.sub(r'^\d+[\.\s]+', '', line)
        line = re.sub(r'^[\-\*\s]+', '', line)
        match = pattern.match(line)
        if match:
            name = match.group(1)
            args_str = match.group(2)
            args = [a.strip() for a in args_str.split(',') if a.strip()]
            if name in valid_actions and (not blocks or all(a in blocks for a in args)):
                if name in {"UNSTACK", "STACK"} and len(args) != 2:
                    continue
                if name in {"PICKUP", "PUTDOWN"} and len(args) != 1:
                    continue
                actions.append(f"{name}({','.join(args)})")
        else:
            line2 = re.sub(r'\s+', '', line)
            match2 = pattern.match(line2)
            if match2:
                name = match2.group(1)
                args_str = match2.group(2)
                args = [a.strip() for a in args_str.split(',') if a.strip()]
                if name in valid_actions and (not blocks or all(a in blocks for a in args)):
                    if name in {"UNSTACK", "STACK"} and len(args) != 2:
                        continue
                    if name in {"PICKUP", "PUTDOWN"} and len(args) != 1:
                        continue
                    actions.append(f"{name}({','.join(args)})")

        if len(actions) >= 40:
            break

    return actions


def simulate_plan(plan: List[str], task: Dict[str, Any]) -> Tuple[bool, str]:
    blocks = task.get("blocks", [])
    initial = task.get("initial_state", [])
    goal = task.get("goal_state", [])

    env = BlocksworldEnv(blocks)
    env.reset(initial)

    result = env.execute_plan(plan)
    if not result["plan_valid"]:
        step = result["failed_step"]
        action = result["failed_action"]
        state = result["final_state"]
        return False, (
            f"第 {step + 1} 步 {action} 执行失败（前提不满足）。"
            f"失败时的状态：{', '.join(state)}"
        )

    if not env.is_goal_satisfied(goal):
        achieved = [g for g in goal if g in env.state]
        missing = [g for g in goal if g not in env.state]
        return False, (
            f"计划执行完毕但未达成目标。"
            f"已达成：{', '.join(achieved) if achieved else '无'}。"
            f"缺失：{', '.join(missing)}。"
        )

    return True, ""


def _pddl_fallback(task: Dict[str, Any], llm_client) -> List[str]:
    """尝试 4：PDDL + pyperplan 求解。Q2 同款 prompt，仅安全 post-processing。"""
    import tempfile
    from pathlib import Path as _Path
    from pyperplan import planner
    from pyperplan.search import breadth_first_search

    domain_path = _Path(__file__).resolve().parent.parent / "pddl" / "domain.pddl"
    with open(domain_path, 'r', encoding='utf-8') as f:
        domain_pddl = f.read()

    natural_language = task.get("natural_language", "")
    initial = task.get("initial_state", [])
    goal = task.get("goal_state", [])
    blocks = task.get("blocks", [])
    task_id = task.get("task_id", "unknown")

    # Q2 同款 robust prompt
    example_good = """
示例1（正确）：
初始状态：(ontable A) (on B A) (on C B) (clear C) (handempty)
目标：(and (ontable C) (on B C) (on A B))
说明：每个积木只有一个位置。
"""
    example_direction = """
示例2（方向说明 — 重要！）：
自然语言："从桌面往上依次是 A, B, C, D" — A 在桌面，B 在 A 上，C 在 B 上，D 在 C 上。
→ 初始：(ontable A) (on B A) (on C B) (on D C) (clear D) (handempty)
→ 目标：(and (on D C) (on C B) (on B A) (ontable A))
(on x y) 中 x 在上面、y 在下面。底部块在 ontable，顶部块只出现在 on 的左侧（作为 x）。
"""
    pddl_prompt = f"""你是一个 PDDL 问题生成专家。请为积木世界任务生成一个语法正确的 PDDL 问题文件。

### 域定义
{domain_pddl}

### 关键规则
1. (on x y) 表示 x 直接放在 y 上面，方向很重要！
2. 初始状态必须包含 handempty，不能包含 holding。
3. 目标状态每个积木只能有一个位置（ontable 或 on），禁止同时出现。不能包含 handempty 或 not。
4. 所有参数用空格分隔，例如 (on A B)。

### 正确示例
{example_good}
### 方向说明
{example_direction}

### 当前任务
任务ID：{task_id}
""".strip()

    if initial and goal:
        pddl_prompt += f"\n初始状态：{', '.join(initial)}\n目标状态：{', '.join(goal)}"
    else:
        pddl_prompt += f"\n自然语言描述：{natural_language}（请据此推断初始状态和目标状态）"

    pddl_prompt += "\n\n只输出 PDDL 代码。"

    response = llm_client.chat(pddl_prompt)
    problem_pddl = response.strip()

    # ── 安全 post-processing（不做 regex 修改内容）──
    if problem_pddl.startswith("```"):
        lines = problem_pddl.split('\n')
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        problem_pddl = '\n'.join(lines)

    # 注入 :objects
    if blocks and ":objects" not in problem_pddl:
        obj_line = f"  (:objects {' '.join(blocks)} - block)"
        lines = problem_pddl.split('\n')
        new_lines = []
        inserted = False
        for line in lines:
            new_lines.append(line)
            if not inserted and line.strip().startswith("(define"):
                new_lines.append(obj_line)
                inserted = True
        problem_pddl = '\n'.join(new_lines)

    # 确保 :init 包含 handempty
    if ":init" in problem_pddl and "handempty" not in problem_pddl:
        problem_pddl = problem_pddl.replace("(:init", "(:init (handempty)")

    # ── pyperplan 求解 ──
    tmp_dir = _Path(tempfile.gettempdir()) / "q1_pddl"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    problem_path = tmp_dir / f"{task_id}.pddl"
    with open(problem_path, 'w', encoding='utf-8') as f:
        f.write(problem_pddl)

    try:
        raw_plan = planner.search_plan(
            str(domain_path), str(problem_path), breadth_first_search, None
        )
        if raw_plan is None:
            return []

        actions = []
        for action in raw_plan:
            action_str = str(action).strip().split('\n')[0]
            if action_str.startswith('(') and action_str.endswith(')'):
                action_str = action_str[1:-1]
            actions.append(action_str)

        normalised = []
        for a in actions:
            a = a.strip().lower().replace("-", "")
            parts = a.split(None, 1)
            if not parts:
                continue
            name = parts[0].upper()
            args = parts[1].split() if len(parts) > 1 else []
            args = [x.upper() for x in args]
            normalised.append(f"{name}({','.join(args)})")
        return normalised
    except Exception:
        return []


def plan_with_llm(task: Dict[str, Any], llm_client) -> List[str]:
    blocks = task.get("blocks", [])
    all_candidates = []

    def try_attempt(actions):
        if actions:
            all_candidates.append(actions)
            ok, err = simulate_plan(actions, task)
            return ok, err
        return False, "无法解析动作序列。"

    # ── 尝试 1：精简 prompt（7 例，全模式）───────────
    p1 = build_prompt(task, variant=1)
    a1 = parse_llm_output(llm_client.chat(p1), blocks)
    ok1, err1 = try_attempt(a1)
    if ok1:
        return a1

    # ── 尝试 2：精简 prompt（5 例，核心模式）─────────
    p2 = build_prompt(task, variant=0)
    a2 = parse_llm_output(llm_client.chat(p2), blocks)
    ok2, err2 = try_attempt(a2)
    if ok2:
        return a2

    # ── 尝试 3：推理 prompt + 错误反馈 ──────────────────
    p3 = build_prompt_reasoning(task, err2 or err1)
    a3 = parse_llm_output(llm_client.chat(p3), blocks)
    try_attempt(a3)

    # ── 尝试 4：PDDL + pyperplan 回退 ──────────────────
    a4 = _pddl_fallback(task, llm_client)
    try_attempt(a4)

    # ── 返回最佳候选 ────────────────────────────────────
    if all_candidates:
        for cand in all_candidates:
            env = BlocksworldEnv(blocks)
            env.reset(task.get("initial_state", []))
            result = env.execute_plan(cand)
            if result["plan_valid"] and env.is_goal_satisfied(task.get("goal_state", [])):
                return cand
        best_actions = None
        best_valid = -1
        for cand in all_candidates:
            env = BlocksworldEnv(blocks)
            env.reset(task.get("initial_state", []))
            result = env.execute_plan(cand)
            valid_count = result["failed_step"] if result["failed_step"] is not None else len(cand)
            if valid_count > best_valid:
                best_valid = valid_count
                best_actions = cand
        return best_actions or all_candidates[0]

    return []
