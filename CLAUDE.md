# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Blocksworld student assignment: use LLM prompting to solve block-stacking puzzles. Two approaches:
- **Q1** — LLM directly outputs action sequences
- **Q2** — LLM generates PDDL problem files, solved by a classical planner (pyperplan)

25 tasks across 5 tiers (public → nl_only → hidden → hard → extreme). Only 4 public tasks include structured `initial_state`/`goal_state`; the other 21 only provide natural language descriptions at evaluation time.

## Immutable vs. Editable Files

| Teacher-provided (DO NOT EDIT) | Student workspace (EDIT ONLY THESE) |
|---|---|
| `env/` — Blocksworld environment | `my_planner/q1_llm_prompt_planner.py` |
| `pddl/domain.pddl` — PDDL domain | `my_planner/q2_llm_pddl_planner.py` |
| `llm_client.py` — LLM API wrapper | `my_planner/prompt_templates/*.txt` (note: currently unused, actual prompts are inline in `.py` files) |
| `run_q1.py`, `run_q2.py` — single-task runners | |
| `evaluate.py` — batch evaluator | |
| `tasks/` — all 25 task JSONs | |

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Set env vars (Bash / Git Bash)
export OPENAI_API_KEY="your-deepseek-key"
export LLM_PROVIDER="openai-compatible"
export LLM_BASE_URL="https://api.deepseek.com"
export LLM_MODEL="deepseek-chat"
```

```powershell
# Set env vars (PowerShell)
$env:OPENAI_API_KEY="your-deepseek-key"
$env:LLM_PROVIDER="openai-compatible"
$env:LLM_BASE_URL="https://api.deepseek.com"
$env:LLM_MODEL="deepseek-chat"
```

```bash
# Run single task
python run_q1.py --task tasks/public/task_01.json
python run_q2.py --task tasks/public/task_02.json

# Evaluate all 25 tasks → generates results.json
python evaluate.py --output results.json
```

API key priority: `--api-key` > `LLM_API_KEY` > `OPENAI_API_KEY`. `evaluate.py` checks `LLM_API_KEY` first, then falls back to `OPENAI_API_KEY`.

## Architecture

### Blocksworld Domain (4 actions, 5 predicates)

**Predicates**: `ontable(x)`, `on(x,y)`, `clear(x)`, `holding(x)`, `handempty`

**Actions** (each has preconditions enforced by `env/validator.py`):
- `PICKUP(x)` — requires `ontable(x)`, `clear(x)`, `handempty`
- `PUTDOWN(x)` — requires `holding(x)`
- `UNSTACK(x,y)` — requires `on(x,y)`, `clear(x)`, `handempty`
- `STACK(x,y)` — requires `holding(x)`, `clear(y)`

### Key Modules

- **`env/blocksworld_env.py`** — State as `Set[str]` of predicates. `execute_plan()` runs actions sequentially until failure. `is_goal_satisfied()` checks subset. `render()` produces ASCII visualization.
- **`env/action_parser.py`** — Regex parses action strings like `"UNSTACK(C,A)"` → `("UNSTACK", ["C", "A"])`. Expects uppercase action names, comma-separated args.
- **`env/validator.py`** — Checks preconditions against current state. Also exports `get_action_preconditions()` and `get_action_effects()` for reference.
- **`llm_client.py`** — `LLMClient(provider, model, api_key, base_url).chat(prompt)` returns text. Supports `openai`, `anthropic`, `openai-compatible`.

### Task JSON Format

```json
{
  "task_id": "task_01",
  "blocks": ["A", "B"],
  "nl_only": false,           // true for non-public tasks → states cleared at eval
  "natural_language": "...",   // always present; only input for NL-only tasks
  "initial_state": ["ontable(A)", ...],
  "goal_state": ["on(A,B)", ...]
}
```

When `nl_only: true`, `run_q1.py`/`run_q2.py`/`evaluate.py` clear `initial_state` and `goal_state` to `[]` before passing to student code. The planner must extract state from `natural_language` alone.

### Q1 Flow (`q1_llm_prompt_planner.py`)

```
task → build_prompt(task) → llm_client.chat(prompt) → parse_llm_output(response) → action list
```

Three functions to implement: `build_prompt`, `parse_llm_output`, `plan_with_llm`. Output must be one action per line like `PICKUP(A)`.

`plan_with_llm` has **3-level retry fallback** when parsing fails:
1. Full prompt (with rules + examples + states)
2. Simple prompt (natural language only, "output actions one per line")
3. Force prompt (prepends "只输出动作序列" to the full prompt)

### Q2 Flow (`q2_llm_pddl_planner.py`)

```
task → build_pddl_prompt(task, domain_pddl) → llm_client.chat() → generate_problem_pddl() → pyperplan BFS solver → action list
```

Four functions to implement. Generated PDDL must use **space-separated** args: `(on A B)` not `(on A,B)`. Problem file saved to `outputs/<task_id>/problem.pddl` for debugging.

`plan_with_llm_pddl` runs **2 attempts**: if first attempt yields no valid plan, regenerates PDDL and retries. On failure, prints the problem.pddl content for debugging.

`generate_problem_pddl` applies **PDDL auto-repair** post-processing:
- Strips markdown code fences (`` ``` ``)
- Auto-inserts missing `(:objects ... - block)` line after `(define ...)`
- Ensures `:init` contains `(handempty)`
- `fix_goal_conflicts()`: removes `ontable(X)` if X already appears in an `on(X Y)` predicate, strips `(handempty)` and `(not ...)` from goal

### PDDL Planner (`solve_pddl`)

Uses `pyperplan.planner.search_plan(domain_path, problem_path, breadth_first_search, None)`. Returns list of lowercase action strings like `"pickup a"` — the runner normalizes these to `"PICKUP(A)"` format before validation.

## Constraints

- No BFS/DFS/A* search algorithms — LLM must do the planning
- No hardcoded answers by `task_id`
- Must use `deepseek-chat` model for fair evaluation
- Q1 must output only actions (parse function filters noise); Q2 must output only valid PDDL

## Scoring

`evaluate.py` assigns machine scores out of 55:
- Q1: max **25** points (1 point per task × 25 tasks)
- Q2: max **30** points (1.2 points per task × 25 tasks)
- Results saved to `results.json` with `summary` and `details` arrays per task.
