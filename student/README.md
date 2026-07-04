# Blockworld LLM Planner

基于 LLM 提示的积木世界自动规划器。使用大语言模型（DeepSeek）解决 Blocksworld 经典规划问题，支持两种求解方案。

## 功能

- **Q1（直接动作序列）**：LLM 直接输出动作序列（`PICKUP(A)`、`STACK(A,B)` 等），含 3 级重试回退机制
- **Q2（PDDL + 经典规划器）**：LLM 生成 PDDL 问题文件，由 pyperplan BFS 求解器求解，含 PDDL 自动修复后处理

## 项目结构

```
├── my_planner/           # 学生实现（Q1 + Q2 规划器）
│   └── prompt_templates/ # LLM prompt 模板
├── env/                  # Blocksworld 环境（状态、动作解析、验证器）
├── pddl/                 # PDDL 领域定义
├── tasks/                # 25 个任务（public / nl_only / hidden / hard / extreme）
├── outputs/              # 运行输出（plan.txt + problem.pddl）
├── run_q1.py             # 单任务 Q1 运行器
├── run_q2.py             # 单任务 Q2 运行器
├── evaluate.py           # 批量评估器
└── llm_client.py         # LLM API 封装（支持 OpenAI / DeepSeek / Anthropic）
```

## 环境配置

```bash
pip install -r requirements.txt
```

设置环境变量（PowerShell）：
```powershell
$env:OPENAI_API_KEY="your-deepseek-key"
$env:LLM_PROVIDER="openai-compatible"
$env:LLM_BASE_URL="https://api.deepseek.com"
$env:LLM_MODEL="deepseek-chat"
```

## 运行方式

```bash
# Q1：LLM 直接输出动作序列
python run_q1.py --task tasks/public/task_01.json

# Q2：LLM 生成 PDDL → pyperplan 求解
python run_q2.py --task tasks/public/task_02.json

# 批量评估全部 25 个任务
python evaluate.py --output results.json
```

## 结果

- **Q1**：22/25 分
- **Q2**：25/25 分
- **总分**：52/55（v6b-final）

## 许可

MIT License
