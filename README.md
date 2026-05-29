# AI Scientist - 基于 Qwen 的智能科研助手

<p align="center">
  <b>挑战杯 XH-202619</b> |
  基于千问大模型的智能科研系统
</p>

---

## 📖 快速开始

**第一次使用？** 请查看 [快速入门指南](./QUICKSTART.md) 以获得详细的分步说明。

### 🚀 一键启动 (推荐)

#### Windows 用户
```batch
# 1. 设置后端
scripts\setup_backend.bat

# 2. 设置前端
scripts\setup_frontend.bat

# 3. 编辑 .env 文件 (填入你的配置)

# 4. 初始化数据库
python scripts\init_db.py

# 5. 启动开发环境
scripts\run_dev.bat
```

#### Linux/Mac 用户
```bash
# 1. 设置后端
bash scripts/setup_backend.sh

# 2. 设置前端
bash scripts/setup_frontend.sh

# 3. 编辑 .env 文件 (填入你的配置)

# 4. 初始化数据库
python scripts/init_db.py

# 5. 启动开发环境
bash scripts/run_dev.sh
```

启动成功后访问：
- **前端界面**: http://localhost:3000
- **API 文档**: http://localhost:8000/docs

---

## 📋 项目简介

本项目是为**挑战杯 XH-202619**开发的基于 Qwen/千问大模型的 AI Scientist 系统。系统集成了智能文献检索、自动研究报告生成、学术对话等功能，旨在通过 AI 技术提升科研效率。

### ✨ 主要功能

1. **🤖 智能研究报告生成**
   - 基于研究主题自动生成文献综述
   - 支持多种研究类型（文献综述、研究 proposal、实验设计等）
   - 关键词提取和分析

2. **💬 学术对话**
   - 与 AI 进行专业的学术讨论
   - 基于 RAG 的文献检索增强
   - 会话历史记录

3. **📚 文献管理**
   - 支持多种格式上传 (TXT, PDF, DOCX, CSV, MD)
   - 自动向量化和索引
   - 智能语义检索

4. **🔬 科研 Skill 增强层**
   - 文献搜索与引用验证：整合 arXiv、Semantic Scholar、OpenAlex、CrossRef 多源搜索，自动去重并验证引用真实性，拒绝 LLM 自造引用
   - 数据集发现：根据研究问题推荐公开数据集，标注来源、许可和任务类型
   - 科学图表生成：基于真实数据生成统计图表，无数据时不生成伪图
   - 报告质量检查：对生成报告做赛题规范检查，输出评分和修正建议
   > 本项目参考了 Hermes、K-Dense Scientific Skills、PaperQA、OpenScholar、Data-Juicer、MatPlotAgent 等公开项目的能力思想，未直接复制第三方主流程。核心实现为本项目自研适配层，核心推理模型仍为 Qwen/千问，外部 Skill 只作为工具层用于文献搜索、引用校验、数据质量分析、数据集发现、科学图表和报告质量检查。

---

## 🛠️ 技术栈

| 组件 | 技术选型 |
|------|---------|
| **后端框架** | FastAPI |
| **前端框架** | React + Vite |
| **UI 组件库** | Ant Design |
| **数据库** | MySQL / SQLite |
| **ORM** | SQLAlchemy |
| **向量检索** | FAISS |
| **嵌入模型** | Sentence-Transformers |
| **大模型** | 阿里千问 (Qwen) |

---

## 📁 项目结构

```
AISci/
├── backend/              # FastAPI 后端
│   └── app/
│       ├── api/         # API 路由
│       │   ├── research.py
│       │   ├── chat.py
│       │   └── documents.py
│       ├── core/        # 配置和数据库
│       ├── models/      # 数据模型
│       ├── schemas/     # Pydantic 模型
│       ├── services/    # 业务逻辑
│       └── main.py
├── frontend/            # React + Vite 前端
│   └── src/
│       ├── components/  # UI 组件
│       ├── pages/       # 页面组件
│       └── services/    # API 服务
├── data/                # 数据目录
├── storage/             # 存储 (FAISS 索引、上传文件)
├── scripts/             # 自动化脚本
│   ├── setup_backend.bat/sh
│   ├── setup_frontend.bat/sh
│   ├── run_dev.bat/sh
│   └── init_db.py
├── docs/                # 文档
├── tests/               # 测试
├── requirements.txt     # Python 依赖
├── .env.example        # 环境变量模板
├── QUICKSTART.md       # 快速入门
└── README.md
```

---

## ⚙️ 配置说明

### 环境变量 (.env)

复制 `.env.example` 为 `.env` 并填入配置：

```env
# 应用配置
APP_NAME=AI Scientist
DEBUG=True
VERSION=0.1.0

# 后端服务
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000

# 数据库 (默认使用 SQLite)
DATABASE_URL=sqlite:///./data/aiscientist.db
# 或使用 MySQL
# DATABASE_URL=mysql+pymysql://root:password@localhost:3306/aiscientist

# 千问 API (必需)
QWEN_API_KEY=your_qwen_api_key_here
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-max

# 向量检索
VECTOR_STORE_PATH=./storage/faiss_index
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
CHUNK_SIZE=512
CHUNK_OVERLAP=50

# 文件上传
UPLOAD_DIR=./storage/documents
MAX_UPLOAD_SIZE=52428800
ALLOWED_EXTENSIONS=txt,pdf,docx,md,csv

# CORS
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

### 获取千问 API Key

1. 访问 [阿里云百炼控制台](https://dashscope.console.aliyun.com/)
2. 注册/登录账号
3. 创建 API Key
4. 将 API Key 填入 `.env` 文件

### Qwen Client 使用说明

#### 基本用法

```python
from app.services.qwen_client import QwenClient, qwen_chat, qwen_structured_chat

# 方式1: 直接使用单例便捷函数
response = qwen_chat(
    prompt="你好，请介绍一下你自己",
    system_prompt="你是一个有用的AI助手",
    temperature=0.3
)
print(response)

# 结构化输出
schema = {"summary": "", "keywords": [], "sentiment": ""}
result = qwen_structured_chat(
    prompt="请分析以下文本：...",
    schema_example=schema
)
print(result["summary"])

# 方式2: 创建独立实例
client = QwenClient(
    api_key="your-api-key",
    base_url="https://custom.url",
    model="qwen-plus",
    timeout=120,
    max_retries=3
)

response = client.chat(
    prompt="这是一个测试问题",
    system_prompt="你是一个测试助手",
    temperature=0.7,
    max_tokens=500
)

# 多轮对话
messages = [
    {"role": "system", "content": "你是一个研究助手"},
    {"role": "user", "content": "什么是机器学习？"},
    {"role": "assistant", "content": "机器学习是..."},
    {"role": "user", "content": "深度学习和它有什么关系？"}
]
response = client.chat_with_messages(messages, temperature=0.5)
```

#### 配置说明

在 `.env` 文件中配置：

```env
# 千问 API 配置
QWEN_API_KEY=your_qwen_api_key_here
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-max  # 可选: qwen-max, qwen-plus, qwen-turbo
```

#### 错误处理

```python
from app.services.qwen_client import (
    QwenClient,
    QwenError,
    QwenAPIError,
    QwenTimeoutError
)

client = QwenClient()

try:
    response = client.chat("测试问题")
except QwenTimeoutError:
    print("请求超时，请稍后重试")
except QwenAPIError as e:
    print(f"API 调用失败: {e}")
except QwenError as e:
    print(f"发生错误: {e}")
```

#### 可用模型

- `qwen-max`: 最强模型，适合复杂任务
- `qwen-plus`: 平衡模型，通用场景
- `qwen-turbo`: 最快模型，适合简单任务

---

## 🔍 向量检索 (RAG) 使用说明

### 核心功能

向量存储模块提供以下功能：
- 按项目分区管理向量索引
- 使用 FAISS 进行高效向量检索
- 支持多种 Embedding 模型
- 自动处理 Chunk 向量化和元数据保存

### 基本用法

```python
from app.services.vector_store import (
    get_vector_store,
    add_chunks_to_vector_store,
    search_vector_store,
    SearchResult
)

# 1. 添加 Chunks 到向量索引
added_count = add_chunks_to_vector_store(project_id="your-project-id")
print(f"Added {added_count} chunks")

# 2. 搜索相关 Chunks
results: list[SearchResult] = search_vector_store(
    project_id="your-project-id",
    query="你的搜索查询",
    top_k=5
)

# 遍历结果
for result in results:
    print(f"文档: {result.document_title} (页 {result.start_page}-{result.end_page})")
    print(f"相似度: {result.similarity:.2f}")
    print(f"内容: {result.content[:100]}...\n")
```

### VectorStore 类使用

```python
from app.services.vector_store import VectorStore, SentenceTransformerEmbedding

# 使用默认 Embedding 模型
store = VectorStore()

# 或者使用自定义 Embedding
embedding = SentenceTransformerEmbedding("paraphrase-multilingual-MiniLM-L12-v2")
store = VectorStore(embedding=embedding)

# 添加 Chunks
store.add_chunks(project_id="project-id")

# 搜索
results = store.search(
    project_id="project-id",
    query="搜索文本",
    top_k=10
)

# 获取索引统计
stats = store.get_project_stats("project-id")
print(f"Chunk 数量: {stats['chunk_count']}")

# 删除索引
store.delete_project_index("project-id")
```

### API 接口

向量检索相关的 API 接口（访问 http://localhost:8000/docs 查看完整文档）：

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/v1/vector-search/search/{project_id}` | 向量搜索 |
| POST | `/api/v1/vector-search/index/{project_id}/add-chunks` | 添加 Chunks 到索引 |
| GET | `/api/v1/vector-search/index/{project_id}/stats` | 获取索引统计 |
| DELETE | `/api/v1/vector-search/index/{project_id}` | 删除项目索引 |

### 配置说明

在 `.env` 文件中配置：

```env
# 向量存储路径
VECTOR_STORE_PATH=./storage/faiss_index

# Embedding 模型
# 可选: paraphrase-multilingual-MiniLM-L12-v2, all-MiniLM-L6-v2, all-mpnet-base-v2 等
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
```

### 自定义 Embedding

你可以通过继承 `BaseEmbedding` 来实现自定义 Embedding：

```python
from app.services.vector_store import BaseEmbedding
import numpy as np

class CustomEmbedding(BaseEmbedding):
    def __init__(self):
        self._dimension = 512
    
    def embed(self, texts):
        # 实现你的向量化逻辑
        return np.random.randn(len(texts), self._dimension)
    
    @property
    def dimension(self):
        return self._dimension

# 使用自定义 Embedding
store = VectorStore(embedding=CustomEmbedding())
```

---

## 🤖 智能体 (Agents) 使用说明

### ProblemUnderstandingAgent - 问题理解智能体

问题理解智能体用于分析用户的研究问题，输出结构化的分析结果。

#### 核心功能
- 明确研究问题陈述
- 定义研究领域
- 提取关键词
- 界定研究范围和边界
- 识别约束条件
- 明确期望输出

#### 设计原则
Prompt 强调：
1. **明确研究问题**：将模糊问题转化为具体、可研究的陈述
2. **边界定义**：清晰说明研究范围、不研究内容、适用场景
3. **避免泛化**：避免宽泛描述，要具体、可操作

#### 基本用法

```python
from app.agents import (
    ProblemUnderstandingAgent,
    ProblemUnderstandingRequest,
    ProblemUnderstandingResponse,
    get_problem_understanding_agent
)

# 获取智能体实例
agent = get_problem_understanding_agent()

# 分析研究问题
result: ProblemUnderstandingResponse = agent.analyze(
    research_question="如何利用机器学习提高医学影像诊断的准确率？",
    domain_description="医学影像、人工智能、深度学习"
)

# 查看结果
print("问题陈述:", result.problem_statement)
print("研究领域:", result.research_domain)
print("关键词:", result.keywords)
print("研究边界:", result.scope_boundary)
print("约束条件:", result.constraints)
print("期望输出:", result.expected_output)
```

#### API 接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/v1/agents/problem-understanding` | 问题理解分析 |

**请求示例：**
```bash
curl -X POST http://localhost:8000/api/v1/agents/problem-understanding \
  -H "Content-Type: application/json" \
  -d '{
    "research_question": "如何利用机器学习提高医学影像诊断的准确率？",
    "domain_description": "医学影像、人工智能、深度学习"
  }'
```

**响应示例：**
```json
{
  "success": true,
  "message": "问题分析成功",
  "data": {
    "problem_statement": "如何利用机器学习提高医学影像诊断的准确率，特别是在肿瘤检测方面的应用研究",
    "research_domain": "医学人工智能",
    "keywords": ["机器学习", "医学影像", "肿瘤检测", "诊断准确率"],
    "scope_boundary": "本研究聚焦于利用机器学习算法提高胸部CT影像中肺癌结节检测的准确率，不包括其他疾病或影像模态的研究",
    "constraints": ["需要有标注的医学影像数据", "算法性能需要达到临床可用水平"],
    "expected_output": ["改进的检测算法", "性能评估报告", "开源代码"]
  }
}
```

#### Prompt 模板

智能体使用的 Prompt 模板已包含在代码中，主要强调：
- 明确研究问题陈述
- 清晰的研究边界定义
- 避免泛化描述

---

### LiteratureMiningAgent - 文献挖掘智能体

文献挖掘智能体用于从项目文献中提取关键科学事实。

#### 核心功能
- 调用 FAISS 检索相关文献片段
- 调用 Qwen 提取关键科学事实
- 每条事实绑定来源信息（chunk_id、论文标题、页码）
- 禁止无来源事实
- 生成证据列表和引用映射
- 标注不确定的点

#### 工作流程
1. 接收 project_id 和研究问题
2. 调用 FAISS 检索相关文献片段（默认 top_k=10）
3. 将文献片段格式化后发送给 Qwen
4. 提取关键科学事实、证据、来源论文、引用映射、不确定点
5. 返回结构化结果

#### 基本用法

```python
from app.agents import (
    LiteratureMiningAgent,
    LiteratureMiningRequest,
    LiteratureMiningResponse,
    get_literature_mining_agent
)

# 获取智能体实例
agent = get_literature_mining_agent()

# 挖掘文献
result: LiteratureMiningResponse = agent.mine(
    project_id="your-project-id",
    research_question="机器学习在医学影像中的应用效果如何？",
    top_k=10
)

# 查看结果
print(f"提取了 {len(result.facts)} 个科学事实")
print(f"来源论文: {result.source_papers}")

for fact in result.facts:
    print(f"\n事实: {fact.content}")
    print(f"  来源: {fact.source_paper_title} (页 {fact.source_page})")
    print(f"  Chunk ID: {fact.source_chunk_id}")
```

#### API 接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/v1/agents/problem-understanding` | 问题理解分析 |
| POST | `/api/v1/agents/literature-mining` | 文献挖掘分析 |

**请求示例：**
```bash
curl -X POST http://localhost:8000/api/v1/agents/literature-mining \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "project-123",
    "research_question": "机器学习在医学影像中的应用效果如何？",
    "top_k": 10
  }'
```

**响应示例：**
```json
{
  "success": true,
  "message": "文献挖掘成功，提取 3 个科学事实",
  "data": {
    "facts": [
      {
        "fact_id": "fact_001",
        "content": "卷积神经网络在医学影像分类任务中表现优异，准确率可达 95% 以上",
        "source_chunk_id": "chunk_abc123",
        "source_paper_title": "医学影像深度学习综述",
        "source_page": 15
      }
    ],
    "evidence": [
      {
        "evidence_id": "ev_001",
        "fact_id": "fact_001",
        "text": "我们的实验结果表明，CNN 模型在胸部 X 光片分类中达到了 96.2% 的准确率...",
        "source_chunk_id": "chunk_abc123"
      }
    ],
    "source_papers": ["医学影像深度学习综述", "机器学习在医疗诊断中的应用"],
    "citation_map": [
      {
        "paper_title": "医学影像深度学习综述",
        "fact_ids": ["fact_001"],
        "chunk_ids": ["chunk_abc123"]
      }
    ],
    "uncertain_points": ["不同数据集的性能差异较大，需要更多验证"]
  }
}
```

#### Prompt 模板

智能体使用的 Prompt 模板主要强调：
- 每条事实必须绑定来源信息（chunk_id、论文标题、页码）
- 禁止编造无来源的事实
- 仅基于提供的文献片段进行分析
- 标注不确定或有争议的观点
- 保持事实的客观性，避免主观推断

---

### KnowledgeGapAgent - 知识缺口智能体

知识缺口智能体用于从文献事实中识别知识缺口、矛盾和研究机会。

#### 核心功能
- 分析已知事实，构建知识图谱
- 识别知识缺口（每个缺口都说明依据和可能价值）
- 发现文献之间的矛盾和不一致
- 识别不同事实之间可能的潜在联系
- 提出有前景的研究机会

#### 工作流程
1. 接收 LiteratureMiningAgent 输出的 facts 和 uncertain_points
2. 格式化输入并调用 Qwen
3. 分析知识缺口、矛盾、可能联系和研究机会
4. 返回结构化结果

#### 基本用法

```python
from app.agents import (
    KnowledgeGapAgent,
    KnowledgeGapRequest,
    KnowledgeGapResponse,
    get_knowledge_gap_agent
)

# 获取智能体实例
agent = get_knowledge_gap_agent()

# 分析知识缺口（需要先运行 LiteratureMiningAgent）
result: KnowledgeGapResponse = agent.analyze(
    facts=literature_mining_result.facts,
    uncertain_points=literature_mining_result.uncertain_points
)

# 查看结果
print(f"发现 {len(result.knowledge_gaps)} 个知识缺口")
print(f"发现 {len(result.research_opportunities)} 个研究机会")

for gap in result.knowledge_gaps:
    print(f"\n知识缺口: {gap.description}")
    print(f"  依据: {gap.basis}")
    print(f"  研究价值: {gap.potential_value}")

for opportunity in result.research_opportunities:
    print(f"\n研究机会: {opportunity.title}")
    print(f"  描述: {opportunity.description}")
    print(f"  预期影响: {opportunity.expected_impact}")
    print(f"  可行性: {opportunity.feasibility}")
```

#### API 接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/v1/agents/problem-understanding` | 问题理解分析 |
| POST | `/api/v1/agents/literature-mining` | 文献挖掘分析 |
| POST | `/api/v1/agents/knowledge-gap` | 知识缺口分析 |

**请求示例：**
```bash
curl -X POST http://localhost:8000/api/v1/agents/knowledge-gap \
  -H "Content-Type: application/json" \
  -d '{
    "facts": [
      {
        "fact_id": "fact_001",
        "content": "卷积神经网络在医学影像分类中表现优异",
        "source_chunk_id": "chunk_123",
        "source_paper_title": "深度学习医学影像综述",
        "source_page": 10
      },
      {
        "fact_id": "fact_002",
        "content": "Transformer 模型在序列数据处理中有优势",
        "source_chunk_id": "chunk_456",
        "source_paper_title": "NLP 技术进展",
        "source_page": 20
      }
    ],
    "uncertain_points": [
      "不同模型在医学影像任务中的对比研究不足"
    ]
  }'
```

**响应示例：**
```json
{
  "success": true,
  "message": "知识缺口分析成功，发现 2 个知识缺口",
  "data": {
    "known_facts": [
      {
        "fact_id": "fact_001",
        "content": "卷积神经网络在医学影像分类中表现优异",
        "source_paper_title": "深度学习医学影像综述"
      },
      {
        "fact_id": "fact_002",
        "content": "Transformer 模型在序列数据处理中有优势",
        "source_paper_title": "NLP 技术进展"
      }
    ],
    "knowledge_gaps": [
      {
        "gap_id": "gap_001",
        "description": "缺乏 CNN 与 Transformer 在医学影像任务的直接对比研究",
        "basis": ["fact_001", "fact_002"],
        "potential_value": "帮助研究者选择更合适的模型架构，提升任务性能"
      }
    ],
    "contradictions": [],
    "possible_connections": [
      {
        "connection_id": "connect_001",
        "fact_ids": ["fact_001", "fact_002"],
        "description": "可以探索将 Transformer 思想应用于医学影像任务",
        "confidence": 0.7
      }
    ],
    "research_opportunities": [
      {
        "opportunity_id": "opp_001",
        "title": "混合 CNN-Transformer 模型在医学影像中的应用",
        "description": "结合 CNN 的空间特征提取能力和 Transformer 的长距离依赖建模能力",
        "related_gap_ids": ["gap_001"],
        "expected_impact": "显著提升医学影像分析性能",
        "feasibility": 0.8
      }
    ]
  }
}
```

#### Prompt 模板

智能体使用的 Prompt 模板主要强调：
- 每个知识缺口都必须说明依据（引用相关事实ID）
- 每个知识缺口都需要说明可能的研究价值
- 识别文献之间的矛盾和不一致
- 发现不同事实之间可能的潜在联系
- 提出有前景的研究机会

---

### HypothesisGenerationAgent - 假设生成智能体

假设生成智能体用于基于研究问题、事实、知识缺口和约束条件生成科学假设。

#### 核心功能
- 使用归纳推理：从现有事实中总结规律，提出可验证的假设
- 使用演绎推理：基于现有理论或知识缺口，推导出新的假设
- 生成 3-5 条科学假设
- 每条假设包含：hypothesis、rationale、novelty、testability、required_data、possible_method、risk
- 避免空泛套话，要求假设具体、明确
- 自动保存生成的假设到数据库

#### 工作流程
1. 接收研究问题、事实、知识缺口和约束条件
2. 使用归纳推理和演绎推理生成假设
3. 验证并标准化结果
4. 保存到 Hypothesis 表
5. 返回结构化结果

#### 基本用法

```python
from app.agents import get_hypothesis_generation_agent
from app.services.hypothesis_service import get_hypothesis_service

# 获取智能体实例
agent = get_hypothesis_generation_agent()

# 准备数据
research_question = "机器学习在医学影像中的应用效果如何？"
facts = [
    {"content": "卷积神经网络在医学影像分类中表现优异", "source_paper_title": "深度学习医学影像综述"}
]
knowledge_gaps = [
    {"description": "缺乏 CNN 与 Transformer 的对比研究", "potential_value": "帮助选择更合适的模型"}
]
constraints = ["计算资源有限", "需要在 3 个月内完成"]

# 生成假设
result = agent.generate(
    research_question=research_question,
    facts=facts,
    knowledge_gaps=knowledge_gaps,
    constraints=constraints,
    project_id="your-project-id"
)

# 查看结果
print(f"生成了 {len(result.hypotheses)} 条假设")
for idx, hypo in enumerate(result.hypotheses, 1):
    print(f"\n假设 {idx}: {hypo.hypothesis}")
    print(f"理由: {hypo.rationale}")
    print(f"创新点: {hypo.novelty}")
    print(f"可测试性: {hypo.testability}")
```

#### API 接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/v1/agents/problem-understanding` | 问题理解分析 |
| POST | `/api/v1/agents/literature-mining` | 文献挖掘分析 |
| POST | `/api/v1/agents/knowledge-gap` | 知识缺口分析 |
| POST | `/api/v1/agents/hypothesis-generation` | 假设生成 |
| GET | `/api/v1/agents/hypotheses/{project_id}` | 获取项目假设列表 |

**请求示例：**
```bash
curl -X POST http://localhost:8000/api/v1/agents/hypothesis-generation \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "project-123",
    "research_question": "机器学习在医学影像中的应用效果如何？",
    "facts": [
      {
        "content": "卷积神经网络在医学影像分类中表现优异",
        "source_paper_title": "深度学习医学影像综述"
      }
    ],
    "knowledge_gaps": [
      {
        "description": "缺乏 CNN 与 Transformer 的对比研究",
        "potential_value": "帮助选择更合适的模型"
      }
    ],
    "constraints": ["计算资源有限", "需要在 3 个月内完成"]
  }'
```

**响应示例：**
```json
{
  "success": true,
  "message": "假设生成成功，生成 3 条假设",
  "data": {
    "hypotheses": [
      {
        "hypothesis": "混合 CNN-Transformer 模型在医学影像任务中优于单一模型",
        "rationale": "基于归纳推理：CNN 提取空间特征，Transformer 处理长距离依赖，两者结合可以互补",
        "novelty": "首次系统对比三种模型架构在特定医学影像任务上的性能",
        "testability": "可以通过构建三个模型，在相同数据集上进行训练和测试，对比准确率、召回率等指标",
        "required_data": "公开医学影像数据集（如 ChestX-ray14），标注数据",
        "possible_method": "实现三个模型：纯 CNN、纯 Transformer、混合模型，进行对比实验",
        "risk": "混合模型可能计算复杂度高，训练时间长，可能存在过拟合风险"
      }
    ],
    "summary": "生成了 3 条科学假设，涵盖模型架构、数据增强和迁移学习三个方向"
  }
}
```

#### Prompt 模板

智能体使用的 Prompt 模板主要强调：
- 使用归纳推理和演绎推理
- 每条假设包含 7 个必要字段
- 避免空泛套话
- 假设必须具体、明确、可检验

---

### HypothesisReviewAgent - 假设评审智能体

假设评审智能体用于对候选假设进行多维度评审和排序。

#### 核心功能
- 从 5 个维度对假设进行 0-10 分评分：
  1. scientific_value (科学价值)：对推动领域发展的重要性
  2. novelty (创新性)：与现有研究的区别和创新点
  3. testability (可测试性)：通过实验/分析验证的可行性
  4. data_availability (数据可用性)：验证所需数据的可获得性
  5. cost_risk (成本风险)：验证的成本、时间和风险程度
- 每条评分给出具体理由
- 指出低分原因（如果评分<6分）
- 给出修改建议
- 按综合得分从高到低排序输出

#### 评分标准
- 9-10 分：优秀，非常突出
- 7-8 分：良好，有较好表现
- 5-6 分：一般，有明显不足
- 0-4 分：较差，存在严重问题

#### 基本用法

```python
from app.agents import (
    HypothesisReviewAgent,
    HypothesisCandidate,
    get_hypothesis_review_agent
)

# 获取智能体实例
agent = get_hypothesis_review_agent()

# 准备候选假设
hypotheses = [
    HypothesisCandidate(
        hypothesis="混合 CNN-Transformer 模型在医学影像任务中优于单一模型",
        rationale="CNN 提取空间特征，Transformer 处理长距离依赖",
        novelty="首次系统对比三种模型架构",
        testability="可以通过对比实验验证",
        required_data="公开医学影像数据集",
        possible_method="实现三个模型进行对比",
        risk="混合模型可能计算复杂度高"
    ),
    HypothesisCandidate(
        hypothesis="数据增强技术可以显著提升小数据集上的模型性能",
        rationale="数据增强在图像任务中有效，医学影像数据通常较少",
        testability="可以通过对比有/无数据增强的性能验证",
        required_data="医学影像数据集",
        possible_method="设计多种数据增强策略"
    )
]

# 评审假设
result = agent.review(hypotheses=hypotheses)

# 查看结果
print(f"评审完成，共 {len(result.reviews)} 条假设")
print(f"总体评价: {result.summary}")

for review in result.reviews:
    print(f"\n假设索引: {review.hypothesis_index}")
    print(f"综合得分: {review.overall_score}")
    print(f"科学价值: {review.scores.scientific_value.score} - {review.scores.scientific_value.reason}")
    print(f"创新性: {review.scores.novelty.score} - {review.scores.novelty.reason}")
    print(f"可测试性: {review.scores.testability.score} - {review.scores.testability.reason}")
    print(f"数据可用性: {review.scores.data_availability.score} - {review.scores.data_availability.reason}")
    print(f"成本风险: {review.scores.cost_risk.score} - {review.scores.cost_risk.reason}")
    print(f"修改建议: {review.suggestions}")
    print(f"优势: {review.strengths}")
    print(f"劣势: {review.weaknesses}")
```

#### API 接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/v1/agents/problem-understanding` | 问题理解分析 |
| POST | `/api/v1/agents/literature-mining` | 文献挖掘分析 |
| POST | `/api/v1/agents/knowledge-gap` | 知识缺口分析 |
| POST | `/api/v1/agents/hypothesis-generation` | 假设生成 |
| GET | `/api/v1/agents/hypotheses/{project_id}` | 获取项目假设列表 |
| POST | `/api/v1/agents/hypothesis-review` | 假设评审 |

**请求示例：**
```bash
curl -X POST http://localhost:8000/api/v1/agents/hypothesis-review \
  -H "Content-Type: application/json" \
  -d '{
    "hypotheses": [
      {
        "hypothesis": "混合 CNN-Transformer 模型在医学影像任务中优于单一模型",
        "rationale": "CNN 提取空间特征，Transformer 处理长距离依赖，两者结合可以互补",
        "novelty": "首次系统对比三种模型架构在特定医学影像任务上的性能",
        "testability": "可以通过构建三个模型，在相同数据集上进行训练和测试，对比准确率、召回率等指标",
        "required_data": "公开医学影像数据集（如 ChestX-ray14），标注数据",
        "possible_method": "实现三个模型：纯 CNN、纯 Transformer、混合模型，进行对比实验",
        "risk": "混合模型可能计算复杂度高，训练时间长，可能存在过拟合风险"
      },
      {
        "hypothesis": "数据增强技术可以显著提升小数据集上的模型性能",
        "rationale": "现有研究表明数据增强在图像任务中有效，医学影像数据通常较少",
        "novelty": "专门针对医学影像设计数据增强策略",
        "testability": "可以通过对比有/无数据增强的模型性能验证",
        "required_data": "医学影像数据集，包含训练、验证、测试集",
        "possible_method": "设计多种数据增强策略（旋转、翻转、缩放等），进行 ablation study",
        "risk": "过度增强可能导致数据失真，引入噪声"
      }
    ]
  }'
```

**响应示例：**
```json
{
  "success": true,
  "message": "假设评审完成，评审了 2 条假设",
  "data": {
    "reviews": [
      {
        "hypothesis_index": 1,
        "hypothesis": "数据增强技术可以显著提升小数据集上的模型性能",
        "scores": {
          "scientific_value": {
            "score": 6,
            "reason": "该问题研究较多，但针对医学影像的系统性研究仍有价值",
            "low_score_reason": null
          },
          "novelty": {
            "score": 5,
            "reason": "数据增强概念较成熟，需要更具体的创新点",
            "low_score_reason": "创新性不足，建议提出更有针对性的增强策略"
          },
          "testability": {
            "score": 9,
            "reason": "实验设计非常简单，易于快速验证",
            "low_score_reason": null
          },
          "data_availability": {
            "score": 8,
            "reason": "公开医学影像数据集充足，易于获取",
            "low_score_reason": null
          },
          "cost_risk": {
            "score": 8,
            "reason": "实验成本低，周期短，风险可控",
            "low_score_reason": null
          }
        },
        "overall_score": 7.2,
        "suggestions": "1. 建议聚焦于医学影像特定的增强策略；2. 增加消融实验分析不同增强方法的效果；3. 可以与第一个假设结合，探索数据增强对混合模型的影响",
        "strengths": ["可测试性强", "数据易获取", "成本低风险小"],
        "weaknesses": ["创新性一般"]
      },
      {
        "hypothesis_index": 0,
        "hypothesis": "混合 CNN-Transformer 模型在医学影像任务中优于单一模型",
        "scores": {
          "scientific_value": {
            "score": 8,
            "reason": "该假设针对医学影像领域核心问题，若验证成功将显著推动模型架构发展",
            "low_score_reason": null
          },
          "novelty": {
            "score": 9,
            "reason": "首次系统对比三种架构在特定任务上的性能，创新点明确",
            "low_score_reason": null
          },
          "testability": {
            "score": 7,
            "reason": "实验设计清晰，可以通过对照实验验证，但需要较大计算资源",
            "low_score_reason": null
          },
          "data_availability": {
            "score": 6,
            "reason": "公开数据集可用，但特定医学影像数据获取可能受限",
            "low_score_reason": "可能需要机构合作获取数据"
          },
          "cost_risk": {
            "score": 5,
            "reason": "实验成本较高，训练时间较长，存在模型不收敛风险",
            "low_score_reason": "计算资源消耗大，周期可能超预期"
          }
        },
        "overall_score": 7.0,
        "suggestions": "1. 建议先进行小规模预实验验证可行性；2. 考虑使用预训练模型降低计算成本；3. 设计更高效的混合架构；4. 提前规划数据获取方案",
        "strengths": ["创新性强", "科学价值高", "实验设计清晰"],
        "weaknesses": ["成本风险较高", "数据获取可能受限"]
      }
    ],
    "summary": "共评审 2 条假设，建议优先考虑第二条假设进行快速验证，同时投入资源完善第一条假设的实验设计。两条假设可以结合开展研究。"
  }
}
```

#### Prompt 模板

智能体使用的 Prompt 模板主要强调：
- 评分理由必须具体，结合假设内容分析
- 指出低分原因（如果评分<6分）
- 给出可操作的修改建议
- 识别每条假设的优势和劣势
- 按综合得分从高到低排序

---

## 🖥️ 手动启动 (不使用脚本)

### 后端启动

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

pip install -r ../requirements.txt
cd ..
python scripts/init_db.py
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端启动

```bash
cd frontend
npm install
npm run dev
```

---

## 📊 API 文档

启动后端后访问：
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 主要接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/v1/research/generate` | 生成研究报告 |
| POST | `/api/v1/chat/message` | 发送聊天消息 |
| POST | `/api/v1/documents/upload` | 上传文档 |
| GET | `/api/v1/documents/list` | 获取文档列表 |
| POST | `/api/v1/vector-search/search/{project_id}` | 向量搜索 |
| POST | `/api/v1/vector-search/index/{project_id}/add-chunks` | 添加 Chunks 到索引 |
| GET | `/api/v1/vector-search/index/{project_id}/stats` | 获取索引统计 |
| POST | `/api/v1/agents/problem-understanding` | 问题理解分析 |
| POST | `/api/v1/agents/literature-mining` | 文献挖掘分析 |
| POST | `/api/v1/agents/knowledge-gap` | 知识缺口分析 |
| POST | `/api/v1/agents/hypothesis-generation` | 假设生成 |
| GET | `/api/v1/agents/hypotheses/{project_id}` | 获取项目假设列表 |
| POST | `/api/v1/agents/hypothesis-review` | 假设评审 |

---

## 🗺️ 开发路线图

### Phase 1: MVP 核心功能 ✅
- [x] 项目基础架构
- [x] FastAPI 后端
- [x] React 前端
- [x] 数据库模型
- [x] 千问 API 集成
- [x] FAISS 向量检索
- [x] 研究报告生成
- [x] 学术对话
- [x] 文献上传
- [x] 自动化脚本
- [x] ProblemUnderstandingAgent 智能体
- [x] LiteratureMiningAgent 智能体
- [x] KnowledgeGapAgent 智能体
- [x] HypothesisGenerationAgent 智能体

### Phase 2: 功能增强
- [ ] 用户认证系统
- [ ] 项目管理
- [ ] 研究报告导出 (PDF/Word)
- [ ] 文献元数据提取
- [ ] 多轮对话优化
- [ ] 更多智能体 (文献综述生成、实验设计等)

### Phase 3: 高级特性
- [ ] 文献引用网络分析
- [ ] 研究趋势可视化
- [ ] 实验数据可视化
- [ ] 多语言支持
- [ ] 模型微调支持

### Phase 4: 生产就绪
- [ ] 性能优化
- [ ] 缓存机制
- [ ] 完整测试
- [ ] CI/CD 流程
- [ ] Docker 容器化
- [ ] 部署文档

---

## 🧪 如何验证文献库到报告引用链路

使用端到端验收脚本 `scripts/test_literature_to_report.py` 验证完整的 **arXiv / BibTeX / PDF 文献库 → Pipeline → 报告 References** 链路。

### 运行方式

```bash
# 1. 进入 backend 目录
cd backend

# 2. 使用 Mock LLM 模式运行（无需 QWEN_API_KEY，不调用真实 API）
$env:PYTHONPATH = "."
python ../scripts/test_literature_to_report.py

# 3. 如需使用真实 arXiv 搜索（需网络）
$env:REAL_ARXIV = "1"
python ../scripts/test_literature_to_report.py
```

### 验收流程

| 步骤 | 说明 |
|------|------|
| 创建项目 | 在内存 SQLite 中创建测试项目 |
| arXiv 检索 | 搜索 "multimodal medical diagnosis transformer"，导入前 2 篇元数据 |
| BibTeX 导入 | 导入一条测试 BibTeX 条目（Swin Transformer） |
| 运行 Pipeline | 使用 Mock LLM 完成全部 8 个阶段 |
| 生成报告 | 生成包含 References 的研究报告 |

### 验证项

| 检查项 | 预期结果 |
|--------|----------|
| References 不为空 | 至少 1 条引用 |
| `compliance_check.references_verified > 0` | 引用通过文献库验证 |
| `markdown_content` 包含 "References" | 报告正文含参考文献章节 |
| Evidence-grounded Literature Facts 不为空 | 基于文献的事实摘要 |
| `compliance_check` 结构完整 | 16 项合规检查全量 |

### 输出示例

```
[OK] 测试项目创建: abc123...
[OK] arXiv 检索: 2 篇导入成功
[OK] BibTeX 导入: 1 篇导入成功
[INFO] 项目文献总数: 3 篇

--- 开始运行 Pipeline ---
Pipeline 状态: completed
报告 ID: def456...

[PASS] References 不为空 (3 条引用)
[PASS] compliance_check.references_verified = 3 (>0)
[PASS] markdown_content 包含 References
[PASS] Evidence-grounded Literature Facts 不为空
[PASS] compliance_check 结构完整

  >>> 最终结果: PASS ✓ <<<
```

### 注意事项

- **默认使用 Mock LLM**：脚本不依赖 `QWEN_API_KEY`，使用预设响应模拟各 Agent 输出
- **不强制下载 PDF**：仅导入文献元数据，不触发 PDF 下载
- **不依赖 Google Scholar**：所有文献均通过 arXiv API 或本地 BibTeX 导入
- **arXiv 搜索降级**：如果网络不可用，arXiv 搜索步骤将跳过并提示，后续验证仍可进行

---

## 🔧 开发指南

### 后端开发

后端采用分层架构：
- `api/` - API 路由层，处理 HTTP 请求
- `services/` - 业务逻辑层，核心功能实现
- `models/` - 数据模型层，数据库表定义
- `schemas/` - Pydantic 模式，请求/响应验证

### 前端开发

前端采用组件化开发：
- `pages/` - 页面组件
- `components/` - 可复用组件
- `services/` - API 调用封装

### 代码规范

- Python: 遵循 PEP 8
- JavaScript/React: 使用 ESLint
- 提交信息: 使用清晰的描述

---

## ❓ 常见问题

### Q: 提示 "未找到 Python"
A: 请安装 Python 3.10 / 3.11 / 3.12（暂不建议 3.13），并确保添加到 PATH

### Q: 提示 "未找到 Node.js"
A: 请从 https://nodejs.org/ 下载并安装 Node.js 18+

### Q: MySQL 连接失败
A: 
1. 确认 MySQL 服务正在运行
2. 检查用户名和密码
3. 确认数据库已创建
4. 或改用 SQLite (注释掉 MySQL 配置，取消 SQLite 注释)

### Q: 千问 API 调用失败
A: 
1. 确认 API Key 正确
2. 确认账户有足够额度
3. 检查网络连接

更多问题请查看 [快速入门指南](./QUICKSTART.md)

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

本项目仅供挑战杯参赛使用。

---

## 📞 联系方式

如有问题，请联系项目维护者。

---

<p align="center">
  <b>挑战杯 XH-202619</b><br>
  基于国产开源大模型的 AI Scientist 的研发与应用
</p>
