# 智能保险顾问 Agentic Service

基于 FastAPI、LangChain、LangGraph、PostgreSQL 和 Milvus 构建的保险智能顾问服务。
服务支持意图识别、多轮会话、保险条款 RAG 检索，以及面向保险咨询场景的 Agent 工作流。

## 核心能力

- 意图路由：识别寒暄、保险咨询与推荐、理赔、人工转接和无法判断的意图。
- 多轮对话：使用 PostgreSQL 保存 LangGraph 会话状态。
- 会话管理：支持创建、查询、重命名和删除会话。
- 保险产品查询：支持按分类查询产品，以及按分类和保费筛选候选产品。
- 条款 RAG：使用百炼 Embedding、Milvus 和 PostgreSQL 存储父子文档块。
- SSE 流式响应：对话文本增量和条款来源均可通过 Server-Sent Events 返回。
- 中断修复：检测尚未得到工具结果的工具调用，并写入错误状态，避免下次对话延续异常状态。

## 技术栈

- Python 3.12+
- FastAPI / Uvicorn
- LangChain / LangGraph
- PostgreSQL / Asyncpg / SQLAlchemy
- LangGraph PostgreSQL Checkpointer
- Milvus / langchain-milvus
- 百炼 DashScope Embedding
- MinerU（保险条款 PDF 解析）
- DeepSeek（聊天与意图识别模型）

## 项目结构

```text
app/
├── agents/
│   ├── intent_router.py      # 用户意图识别
│   ├── orchestrator.py       # 主 Agent 路由工作流
│   ├── insurance_advisor.py  # 保险咨询与推荐 Agent
│   ├── chitchat.py           # 闲聊 Agent
│   ├── tools.py              # 产品、条款和方案工具
│   └── schemas.py            # Agent 状态与意图结构
├── modules/
│   ├── chat/                 # SSE 对话接口
│   ├── chat_thread/          # 会话管理
│   ├── product/              # 保险产品接口
│   └── insurance_plan/       # 保险方案接口
├── rag/
│   ├── pipeline.py           # 条款解析、切分和入库
│   ├── retriever.py          # Milvus 检索及父块回查
│   └── repository.py         # 父文档块数据库操作
├── infra/
│   ├── database.py           # PostgreSQL 异步数据库
│   └── checkpointer.py       # LangGraph 状态持久化
├── core/
│   └── config.py             # 环境变量与应用配置
└── main.py                   # FastAPI 应用入口

scripts/
└── ingest_rag.py             # 构建保险条款 RAG 知识库
```

## 环境要求

启动前需要准备：

- Python 3.12 或更高版本
- uv
- PostgreSQL
- 可访问的 Milvus 服务
- DeepSeek API Key
- 百炼 DashScope API Key
- MinerU Token
- 已放置保险条款 PDF 的 `data/raw/kb` 目录

## 环境变量

项目从根目录的 `.env` 文件读取配置。

```env
APP_NAME=Insurance Agent
APP_HOST=127.0.0.1
APP_PORT=8001
APP_DEBUG=true
LOGGING_LEVEL=INFO

DB_HOST=localhost
DB_PORT=5432
DB_NAME=insurance
DB_USER=insurance
DB_PASSWORD=insurance

DEEPSEEK_API_KEY=your_deepseek_api_key
CHAT_MODEL=deepseek-chat

DASHSCOPE_API_KEY=your_dashscope_api_key
MINERU_TOKEN=your_mineru_token
MILVUS_HOST=127.0.0.1
MILVUS_PORT=19530
```

> 不要提交真实 API Key 或数据库密码。

## 安装与启动

### 1. 安装依赖

```powershell
uv sync
```

### 2. 准备基础服务

确保 PostgreSQL 和 Milvus 已启动，并确认 `.env` 中的地址与端口可以访问。

### 3. 构建 RAG 知识库

在首次启动或保险条款发生变化后执行：

```powershell
uv run python scripts/ingest_rag.py
```

脚本会：

1. 初始化百炼 `text-embedding-v4` Embedding。
2. 初始化 Milvus `insurance_collection` 集合，支持 dense 和 sparse 向量。
3. 查询数据库中的全部有效保险产品。
4. 对每个产品解析条款 PDF，并切分为父块和子块。
5. 将父块存入 PostgreSQL，将子块存入 Milvus。
6. 对同一产品删除旧知识块后重新写入。

### 4. 启动 API 服务

```powershell
uv run python -m app.main
```

默认地址：

- API：`http://127.0.0.1:8001`
- 健康检查：`GET http://127.0.0.1:8001/health`
- Swagger 文档：`http://127.0.0.1:8001/docs`

## API 概览

除对话接口外，接口需要通过请求头传递用户 ID：

```text
x-user-id: 1
```

### 健康检查

```http
GET /health
```

### 保险产品

```http
GET /api/v1/products
GET /api/v1/products?category=critical_illness
GET /api/v1/products/candidates?categories=critical_illness&premium_min=500&limit_per_category=5
```

支持的产品分类与 Agent 工具说明一致：

- `medical`
- `critical_illness`
- `life`
- `accident`

### 会话管理

```http
POST   /api/v1/chat-threads
GET    /api/v1/chat-threads
PATCH  /api/v1/chat-threads/{thread_id}
DELETE /api/v1/chat-threads/{thread_id}
GET    /api/v1/chat-threads/{thread_id}/messages
```

创建会话示例：

```json
{
  "title": "保险咨询"
}
```

### 流式对话

```http
POST /api/v1/chat
Content-Type: application/json
```

请求示例：

```json
{
  "thread_id": "00000000-0000-0000-0000-000000000000",
  "message": "这款重疾险的等待期是多少？"
}
```

响应使用 SSE，可能包含以下事件：

```text
event: message
data: 增量文本

event: additional_info
data: {"ref-001":{"product_id":1,"clause_name":"条款.pdf","section_path":["第一章"],"content":"条款内容"}}

event: done
data: [DONE]
```

- `message`：Agent 回复的文本增量。
- `additional_info`：条款检索来源及引用内容。
- `done`：对话流结束标识。

## Agent 工作流

主编排器首先进入意图路由节点，根据用户消息和上一轮工作流选择分支：

```text
START
  -> route
     -> chitchat
     -> recommendation_plan
     -> claim
     -> human_handoff
     -> fallback
  -> END
```

当前工作流状态：

- `chitchat`：已接入规则寒暄和闲聊 Agent。
- `recommendation_plan`：已接入保险咨询与条款 Agent。
- `claim`：当前为占位实现，尚未接入完整理赔流程。
- `human_handoff`：当前为占位实现，尚未接入人工客服系统。
- `fallback`：用于无法判断用户意图或模型识别失败的场景。

## RAG 检索机制

条款文档处理流程：

```text
保险条款 PDF
  -> MinerU 解析
  -> 大模型优化 Markdown
  -> Markdown 标题切分父块
  -> RecursiveCharacterTextSplitter 切分子块
  -> 子块写入 Milvus
  -> 父块写入 PostgreSQL
```

子块检索时会返回对应的父块：

1. 用户问题经过 Embedding 转为向量。
2. Milvus 按产品 ID 和问题检索相似子块。
3. 根据子块中的 `parent_id` 查询 PostgreSQL。
4. 返回父块的完整章节内容及来源信息。

条款回答要求使用检索结果，并以 `[ref-001]` 等引用标记标注事实来源。
