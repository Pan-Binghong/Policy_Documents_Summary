# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

政策文档智能摘要工具。用户上传 `.zip` 压缩包，程序解压后解析其中的 PDF/Word/图片文档，通过 DeepSeek LLM 提取 13 个结构化字段，多"支持方向"自动拆分为多行，写入 MySQL，最终导出本次任务的 Excel 报告。

## 常用命令

```bash
# 安装/同步依赖
uv sync

# 启动开发服务器（热重载）
uv run uvicorn app.main:app --reload

# 运行所有测试
uv run pytest

# 运行单个测试文件
uv run pytest tests/test_parser.py -v

# 类型检查
uv run mypy app/

# 代码格式化
uv run ruff format app/ tests/
uv run ruff check app/ tests/ --fix
```

## 架构设计

### 核心数据流

```
.zip 上传
  → ZipExtractor（安全解压）
  → DocumentParser（PDF/Word/图片 → 纯文本）
  → 文本合并
  → LangChain Chain + DeepSeek API
  → PolicyResponse（含 支持方向[] 数组）
  → 行拆分（每个支持方向 → 一行 PolicyRow，前5字段重复补齐）
  → MySQL 写入
  → ExcelExporter（按 task_id 导出）
  → 下载链接
```

### 关键数据模型

**LLM 输出结构**（`PolicyResponse`）：

```python
class SupportItem(BaseModel):
    支持方向: str
    特定方向要求: str
    申报要求: str
    优惠政策: str
    申报材料: str
    申报方式: str
    网站链接: str

class PolicyResponse(BaseModel):
    项目名称: str
    政策依据: str
    归口部门: str
    联系人: str
    申报时间: str
    支持方向列表: list[SupportItem]  # 数组，每项对应 Excel 一行
```

**MySQL 扁平表**（`policy_records`）：存 13 列，前 5 字段在多行间重复。每行关联 `task_id` 标识所属任务。所有字段 NOT NULL，无法提取时存 `"/"`.

### 模块职责

- **`app/core/zip_extractor.py`**：解压 `.zip`，**必须校验每个成员路径**，拒绝包含 `..` 或绝对路径的条目（防路径穿越攻击）。
- **`app/core/parser.py`**：根据扩展名路由解析器。PDF → PyMuPDF，`.docx` → python-docx，图片（`.jpg/.png/.bmp`）→ 调用 `OCR_API_URL`（本地 PaddleOCR HTTP 服务）。
- **`app/core/extractor.py`**：LangChain Chain。使用 `with_structured_output(PolicyResponse)` 获取结构化输出，**JSON 解析失败时最多重试 3 次**，仍失败则抛出异常由上层记录错误。
- **`app/core/reporter.py`**：按 `task_id` 从 MySQL 查询记录，使用 openpyxl 写入 Excel，存至 `outputs/` 目录。Excel 列顺序和列宽在文件顶部常量中定义。
- **`app/models/`**：Pydantic 模型（`PolicyResponse`、`SupportItem`、`PolicyRow`）。
- **`app/api/routes.py`**：FastAPI 路由。上传接口用 `BackgroundTasks` 异步处理，`task_id` 用 UUID 生成，任务状态存 MySQL `tasks` 表。
- **`app/core/config.py`**：`pydantic-settings` 的 `BaseSettings`，所有配置从此处读取，不直接用 `os.environ`。

### LLM 集成

```python
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(
    model=settings.deepseek_model,
    api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_base_url,
)
chain = llm.with_structured_output(PolicyResponse)
```

## 关键约定

- **只支持 `.zip`**，使用 Python 原生 `zipfile`，不依赖任何外部解压工具。
- **空值统一填 `"/"`**：Prompt 中明确要求，代码层面在写入前校验所有字段非空，为空则替换为 `"/"`.
- **多行拆分逻辑**：遍历 `PolicyResponse.支持方向列表`，每个 `SupportItem` 合并前 5 个公共字段生成一个 `PolicyRow`，写为 MySQL 一行。
- **任务状态流转**：`pending → processing → done / error`，状态和错误信息存 `tasks` 表，供前端轮询。
- **已知风险**：多文件合并文本可能超过 DeepSeek 64K token 上限，当前不做分块，超限时将任务置为 `error` 状态并记录日志。
