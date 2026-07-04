# Blocksworld 学生指南

用大语言模型（LLM）让积木按要求堆好。你只写 **Prompt 和少量胶水代码**，不实现环境，也不写搜索算法。

| 题目 | 做法 | 你要改的文件 |
|:---:|------|------|
| **Q1** | 让 LLM 直接输出动作序列 | `my_planner/q1_llm_prompt_planner.py` |
| **Q2** | 让 LLM 生成 PDDL，再交给规划器求解 | `my_planner/q2_llm_pddl_planner.py` |

两题共用同一套环境和 **25 个任务**，最后用 `evaluate.py` 统一打分。任务分 5 层：

| 层级 | 目录 | 数量 | 状态形式 | 用途 |
|------|------|:---:|------|------|
| 公开 | `tasks/public/` | 4 | 结构化状态 + 自然语言 | 学习、调试 |
| 纯自然语言 | `tasks/nl_only/` | 5 | 仅自然语言 | 测试 NL→状态翻译 |
| 隐藏 | `tasks/hidden/` | 3 | 仅自然语言 | 隐藏测试 |
| 困难 | `tasks/hard/` | 3 | 仅自然语言 | 困难测试 |
| 极限 | `tasks/extreme/` | 10 | 仅自然语言 | 极限测试（最多 9 块、26 步） |

> 只有 4 个公开任务带结构化的 `initial_state`/`goal_state`，其余 **21 个任务评测时只给自然语言**。真正拉开差距的，是 Prompt 能否从自然语言里把状态读对。

---

## 1. 积木世界长什么样

```
 [A]      A 在最上面
 [B]
 [C]
-----     桌面
```

**5 个谓词**描述状态：

| 谓词 | 含义 |
|------|------|
| `ontable(A)` | A 在桌上 |
| `on(A,B)` | A 摞在 B 上 |
| `clear(A)` | A 顶上没东西 |
| `holding(A)` | 手正拿着 A |
| `handempty` | 手是空的 |

**只有 4 个动作**，必须满足前提条件才合法：

| 动作 | 什么时候能用 |
|------|------|
| `PICKUP(x)` | x 在桌上、顶上没东西、手是空的 |
| `PUTDOWN(x)` | 手正拿着 x |
| `UNSTACK(x,y)` | x 摞在 y 上、x 顶上没东西、手是空的 |
| `STACK(x,y)` | 手拿着 x、y 顶上没东西 |

> LLM 最常犯的错就是用了不满足条件的动作 —— 这正是你要在 Prompt 里解决的。

**规则**：不能写 BFS/DFS/A\* 搜索，不能按 `task_id` 硬编码答案，不能改 `env/`、`pddl/`、`tasks/`、`run_*.py`、`evaluate.py`。

---

## 2. 在哪写代码

只动 `my_planner/` 这一个目录：

```
student/
├── my_planner/
│   ├── q1_llm_prompt_planner.py   ← Q1，填 3 个函数
│   ├── q2_llm_pddl_planner.py     ← Q2，填 4 个函数
│   └── prompt_templates/          ← Prompt 草稿（可选）
├── run_q1.py / run_q2.py          教师提供，调试单个任务
├── evaluate.py                    教师提供，一键自测全部任务
└── tasks/                         25 个任务（public 4 / nl_only 5 / hidden 3 / hard 3 / extreme 10）
```

每个任务以字典形式传入：

```python
{
    "blocks": ["A", "B", "C"],
    "natural_language": "把 A 放到 B 上……",   # 所有任务都有
    "initial_state": ["on(C,A)", ...],         # NL-only 任务里是空列表 []
    "goal_state":    ["on(A,B)", ...],         # NL-only 任务里是空列表 []
}
```

> ⚠️ 21 个非公开任务的 `initial_state`/`goal_state` 评测时被清空，只能从 `natural_language` 读出状态。**Prompt 必须同时应付"有结构化状态"和"只有自然语言"两种情况。**

---

## 3. Q1：让 LLM 直接输出动作

填这 3 个函数（签名已给好，别改）：

```python
def build_prompt(task) -> str:           # 拼出发给 LLM 的 Prompt
def parse_llm_output(response) -> list:  # 从回复里抽出动作序列
def plan_with_llm(task, llm_client):     # 串起来：build → llm_client.chat() → parse
```

调用 LLM 只需一行：`response = llm_client.chat(prompt)`。

**写好 Prompt 的关键**：
1. 把每个动作的前提条件写进 Prompt（默认模板没写，LLM 会乱用）。
2. 给一个"输入 → 正确输出"的示例（few-shot）。
3. 要求一行一个动作、**只输出动作**，不要解释或 markdown。

---

## 4. Q2：让 LLM 写 PDDL，规划器来解

```
任务 →【你的 Prompt】→ LLM 生成 problem.pddl →【规划器】→ 动作序列
```

LLM 只负责把题目"翻译"成 PDDL，正确性交给规划器保证。填这 4 个函数：

```python
def build_pddl_prompt(task, domain_pddl) -> str:          # 生成 problem.pddl 的 Prompt
def generate_problem_pddl(task, domain_pddl, llm_client):  # 调 LLM 并清洗输出
def solve_pddl(domain_path, problem_path) -> list:         # 用 pyperplan 求解
def plan_with_llm_pddl(task, domain_path, llm_client):     # 串起全流程
```

一个合法的 `problem.pddl`：

```lisp
(define (problem task_02)
  (:domain blocksworld)
  (:objects A B C - block)
  (:init (on C A) (ontable A) (ontable B) (clear C) (clear B) (handempty))
  (:goal (and (on A B) (on B C) (ontable C))))
```

注意：参数用**空格**分隔（`(on A B)` ✅，`(on A,B)` ❌）；所有积木都要写进 `:objects`；域名固定 `blocksworld`。

调用规划器（先 `pip install pyperplan`）：

```python
from pyperplan import planner
from pyperplan.search import breadth_first_search
plan = planner.search_plan(domain_path, problem_path, breadth_first_search, None)
# 每个元素 str() 后取第一行，如 "pickup d"
```

---

## 5. 怎么跑

> 为保证公平，统一使用 **`deepseek-chat`** 模型，接口已固定，你只需提供自己的 API Key。
> 到 <https://platform.deepseek.com/api_keys> 注册并创建 Key，填到 `OPENAI_API_KEY`，其余三行勿改。

```bash
export OPENAI_API_KEY="你的deepseek-key"          # 只需改这一行
export LLM_PROVIDER="openai-compatible"           # 固定
export LLM_BASE_URL="https://api.deepseek.com"    # 固定
export LLM_MODEL="deepseek-chat"                  # 固定
```

> 💰 跑完全部 25 个任务（Q1+Q2）花费 **不到 1 元**，新账号免费额度通常够用。请勿改用其它模型，以保证公平评测。

在 `student/` 目录下：

```bash
# 调试单个任务
python run_q1.py --task tasks/public/task_01.json
python run_q2.py --task tasks/public/task_02.json

# 一键自测全部 25 个任务，生成 results.json（提交用）
python evaluate.py --output results.json
```

**节奏**：先用公开任务跑通流程 → 改 Prompt 提高通过率 → 最后攻克"只有自然语言"的隐藏任务。

---

## 6. 卡住了？对照常见原因

| 现象 | 多半因为 | 怎么办 |
|------|------|------|
| `Plan valid: False` | LLM 用了不满足条件的动作 | Prompt 写清前提条件，要求逐步自检 |
| `plan` 是空列表 | `parse_llm_output` 没解析出来 | 回复可能裹了 markdown/编号，调整解析逻辑 |
| 计划有效但目标没达成 | LLM 方向搞反了 | Prompt 里把目标状态讲清楚 |
| Q2 `planning failed` | 生成的 PDDL 语法错 | 打开 `outputs/<task>/problem.pddl` 看 LLM 写了啥 |
| Q2 `no plan found` | 状态翻译有逻辑错（常见 `on` 反了） | 强调 `on(x,y)` = x 在 y 上面 |
| 隐藏/NL-only 全挂 | Prompt 没处理"只有自然语言" | 加一个 自然语言 → 谓词/PDDL 的示例 |

> 调试技巧：在 `plan_with_llm` / `plan_with_llm_pddl` 里加 `print(response[:500])` 看原始输出；Q2 的 PDDL 在 `outputs/` 下可直接打开检查。

---

## 7. 提交

**自测生成结果**（环境变量见第 5 节）：

```bash
python evaluate.py --output results.json
```

**打包为 `学号_姓名.zip`**：

```
学号_姓名.zip
├── my_planner/
│   ├── q1_llm_prompt_planner.py
│   ├── q2_llm_pddl_planner.py
│   └── prompt_templates/{q1_prompt.txt, q2_pddl_prompt.txt}
├── results.json        # 由 evaluate.py 生成，勿手改
└── 实验报告.pdf
```

**实验报告**建议含：Q1/Q2 的 Prompt 设计思路、25 任务结果表、2–3 个失败案例分析、Q1 vs Q2 对比、总结。

> ⚠️ `results.json` 必须由 `evaluate.py` 生成；教师会用同一模型（`deepseek-chat`）复评验证。发现硬编码答案或造假，按学术不端处理。

| 评分模块 | 分值 |
|------|:---:|
| Q1 Prompt 规划 | 25 |
| Q2 LLM+PDDL | 30 |
| 接口规范（不改教师代码、不硬编码） | 15 |
| 实验分析（对比 + 失败诊断） | 20 |
| 报告质量 | 10 |
| **小计** | **100** |
| 🌟 附加题：LeWM 世界模型评估（见第 8 节） | **+10** |

> 附加题为加分项，满分 10 分，可叠加在 100 分之上（总分上限按课程规定封顶），不做不影响主项目满分。

---

## 8. 🌟 附加题（10 分）：用世界模型做规划

本项目里 LLM 在"符号层"上规划（谓词 / PDDL）。附加题换一个视角：**直接在像素/状态空间里用"世界模型"（World Model）做规划**，体会学习型规划与符号规划的差别。

**任务**：部署 LeWorldModel（LeWM）环境，加载老师提供的预训练权重，在 **TwoRoom** 任务上**跑通评估流程**（世界模型 MPC 规划 + 成功率指标）。**无需训练**，有 GPU 用 GPU，没 GPU 用 CPU 也能跑通。

- 代码与步骤见附加题压缩包 **`lewm_challenge.zip`**，解压后读其中的 **`LEWM_GUIDE.md`**。
- 权重与数据集由老师单独提供：**`tworoom_student_data.zip`**，按 `LEWM_GUIDE.md` 解压到仓库内 `data/` 即可。

**通过标准**：终端打印出 `success_rate`，并在 `data/tworoom/` 下生成结果文件与可视化视频 `env_*.mp4`。

**提交**（并入实验报告或单独附页）：运行截图（含 `success_rate`）、结果文件 `tworoom(_cpu)_results.txt`、任意一个 `env_*.mp4`，以及一段简短说明（部署步骤、遇到的问题及解决，并对比"世界模型 + MPC"与"LLM + 符号规划"两种思路）。

---

## 9. 常见问题

**能用网页版 ChatGPT 调 Prompt 吗？** 可以，但最终代码必须走 `llm_client.chat()`，并在 `deepseek-chat` 上验证。

**Q1 和 Q2 哪个更稳？** 通常 Q2，因为规划器保证正确性；Q1 全靠 Prompt。报告里要分析这个差异。

**能让 LLM 做思维链（CoT）吗？** 可以，但要保证最终只输出动作（Q1）或纯 PDDL（Q2），其余文字由解析函数过滤。
