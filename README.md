# Policy Documents Summary

一个基于 AI 的政策文档智能摘要工具，支持批量解析政策文档、提取关键信息并生成 Excel 汇总报告。

## 功能特性

- **多格式文档解析**：支持 PDF、Word（.docx）、TXT 等常见格式
- **关键信息提取**：自动提取政策名称、发布日期、负责部门、核心条款、适用范围等结构化信息
- **批量处理**：一次性处理多个文档，自动并发调用 LLM
- **Excel 报告输出**：将所有文档的提取结果汇总为结构化的 Excel 表格
- **REST API**：通过 FastAPI 提供 HTTP 接口，支持前端或其他系统集成

## 核心目标

- **输入**: 压缩包（`.zip`）
- **输出**：Excel 文件（`.xlsx`），仅包含本次任务的数据
- **中间存储**: MySQL

### 操作流程
1. 用户上传 `.zip` 压缩包，一个压缩包为一组任务
2. 程序使用 Python 原生 `zipfile` 解压（解压时校验路径，防止路径穿越攻击）
3. 根据文件类型解析为文本：PDF → PyMuPDF，Word → python-docx，图片/扫描件 → 本地 PaddleOCR HTTP 服务
4. 将同一压缩包内所有文件的文本合并，单文件跳过合并
5. 调用 DeepSeek API，传入合并后的文本，输出 JSON。`支持方向` 字段为**数组**，每个元素对应一行记录（其余 12 个字段在多行间重复）
6. 遍历 `支持方向` 数组，将每一行（13 个字段）写入 MySQL 扁平表
7. 将本次任务的所有记录导出为 `.xlsx`，返回下载链接

> ⚠️ **已知风险**：多文件合并后的文本长度可能超过 DeepSeek 64K token 上限，当前暂不处理，遇到时记录错误日志。

## 提取目标

序号	字段名称	提取逻辑/格式要求
1	项目名称	提取文件标题或公告名称
2	政策依据	提取发文字号或引用的核心办法
3	归口部门	发布或主办单位（如：XX局）
4	联系人	姓名：XX，电话：XX，邮箱：XX（若有）
5	申报时间	截止日期或具体时间段
6	支持方向	核心主键。每行仅限一个细分项
7	特定方向要求	仅针对该方向的专属门槛
8	申报要求	基础门槛 + 特定门槛，条目化（1,2,3）
9	优惠政策	奖励金额、扶持比例或具体手段
10	申报材料	精简后的材料清单
11	申报方式	网址、线下地址或办理流程
12	网站链接	官方 URL 入口
13	政策有效期	明确的失效时间，无则填 /

## 重点注意事项

1. 多项多行逻辑, 假设一个政策文件中包含1个以上的"支持方向", 则需要自动拆分为多行记录.
2. 每个输入的压缩包为一组, 假设压缩包中只有一个文件, 文件中不涉及多"支持方向", 则输出的xlsx中, 只有一行该文件的数据.
3. 最终的xlsx中每个单元格都要求有值.不允许留空.

## 技术栈

- **语言**：Python 3.11+
- **AI 框架**：LangChain
- **LLM**：DeepSeek API
- **OCR**: 本地部署的 PaddleOCR HTTP 服务
- **Web 框架**：FastAPI + Uvicorn
- **文档解析**：PyMuPDF（PDF）、python-docx（Word）
- **报告生成**：openpyxl
- **包管理**：uv

## 快速开始

### 安装依赖

```bash
uv sync
```

### 配置环境变量

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
```

```env
# DeepSeek LLM
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_API_BASE=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# PaddleOCR HTTP API
PADDLE_OCR_API_URL=https://your-ocr-service/ocr
PADDLE_OCR_API_KEY=your_ocr_key
PADDLE_OCR_MODEL=paddle-ocr

# MySQL（完整连接串）
DATABASE_URL=mysql+pymysql://user:password@host:port/dbname
```

### 运行 API 服务

```bash
uv run uvicorn app.main:app --reload
```

API 文档访问：http://localhost:8000/docs

### 命令行批量处理

```bash
# 处理单个文件
uv run python -m app.cli process --input docs/policy.pdf

# 批量处理目录下所有文档，输出 Excel
uv run python -m app.cli batch --input-dir ./docs --output report.xlsx
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/upload` | 上传 `.zip` 压缩包，返回 `task_id` |
| GET  | `/api/v1/tasks/{task_id}` | 查询任务状态（pending / processing / done / error）|
| GET  | `/api/v1/tasks/{task_id}/download` | 下载本次任务的 Excel 报告 |

## 项目结构

```
Policy_Documents_Summary/
├── app/
│   ├── main.py          # FastAPI 入口
│   ├── cli.py           # 命令行工具
│   ├── api/             # API 路由
│   ├── core/            # 核心逻辑（解析、提取、报告）
│   └── models/          # Pydantic 数据模型
├── tests/
├── docs/                # 示例文档
├── pyproject.toml
└── .env.example
```
