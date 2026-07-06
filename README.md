# Blocksworld LLM Planner

使用大语言模型（DeepSeek）解决 Blocksworld 积木世界经典规划问题，在 25 个评测任务上取得**满分（55/55）**。

## 两种方案

| | Q1（直接动作序列） | Q2（PDDL + 规划器） |
|---|---|---|
| 路径 | LLM 直接输出 PICKUP/STACK 动作 | LLM 生成 PDDL 问题文件，pyperplan BFS 求解 |
| 重试 | 4 级回退（含 pyperplan 兜底） | 2 次重试 |
| 分数 | 25/25 | 30/30 |

## 快速开始

```powershell
pip install -r requirements.txt

$env:OPENAI_API_KEY="sk-your-key"
$env:LLM_PROVIDER="openai-compatible"
$env:LLM_BASE_URL="https://api.deepseek.com"
$env:LLM_MODEL="deepseek-chat"

# 单任务运行
python run_q1.py --task tasks/public/task_01.json
python run_q2.py --task tasks/public/task_02.json

# 批量评测全部 25 个任务
python evaluate.py --output results.json
```

## 目录结构

```
├── my_planner/           # 学生实现（Q1 + Q2 规划器）
│   ├── q1_llm_prompt_planner.py   # Q1：LLM 直接输出动作
│   └── q2_llm_pddl_planner.py     # Q2：LLM + PDDL 规划器
├── env/                  # Blocksworld 环境（状态、动作解析、验证）
├── pddl/                 # PDDL 领域定义
├── tasks/                # 25 个评测任务
│   ├── public/           # 4 个公开任务（含结构化状态）
│   ├── nl_only/          # 5 个纯自然语言描述
│   ├── hidden/           # 3 个隐藏测试
│   ├── hard/             # 3 个困难测试
│   └── extreme/          # 10 个极限测试（最多 9 块、26 步）
├── run_q1.py             # Q1 单任务运行器
├── run_q2.py             # Q2 单任务运行器
├── evaluate.py           # 批量评估器
├── llm_client.py         # LLM API 封装
└── STUDENT_GUIDE.md      # 完整作业说明
```

## 核心约束

- **不能使用 BFS/DFS/A\* 搜索**——规划必须由 LLM 完成
- **不能按 task_id 硬编码答案**
- 学生只能修改 `my_planner/` 下的两个文件
- 统一使用 `deepseek-chat` 模型

## 许可

MIT License
