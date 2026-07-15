# Knowledge 数据模块（知识库内部存储模型，长期稳定版 v1）

> 本文档描述的是当前知识库能力背后的内部存储模型。
> 对外产品语义、数据库表名与代码目录均已统一为 `knowledge`。

本文件定义 SOIT 知识库（Knowledge）相关的**长期稳定数据模型**，目标是：

- 强制 `tenant_id + workspace_id` 双层隔离
- 支持文档多来源（上传/爬虫/API）
- 支持多版本文档与增量重建
- 支持多索引（不同 embedding / 不同 provider / 不同检索策略）
- 数据库只存 **摘要与元数据**；大文本/解析产物走对象存储；向量走向量库
- 为审计/可观测/计费预留字段，尽量减少后续 schema 变更

> 表命名按要求使用：`knowledge`, `knowledge_documents`, `knowledge_chunks`, `knowledge_indexes`

---

## 0. 统一约定

### 0.1 主键与时间字段
- `id`: 推荐 ULID（字符串或 128bit），便于按时间排序
- `created_at`, `updated_at`: `timestamptz`
- `deleted_at`: 软删除（可选，建议保留）
- `created_by`, `updated_by`: `user_id`（可空，系统任务为空）

### 0.2 隔离字段（强制）
- 除极少 tenant 级全局表外，业务表一律包含：
  - `tenant_id` (NOT NULL)
  - `workspace_id` (NOT NULL)

### 0.3 JSON 字段策略
- `*_json` 仅存**可演进配置/元数据**，避免频繁加列
- 关键查询字段必须独立成列（例如 status / type / version 等）

### 0.4 状态机（推荐枚举）
- Document pipeline：`uploaded -> parsed -> chunked -> indexed`（失败：`failed`）
- Index pipeline：`draft -> building -> ready`（失败：`failed`，停用：`disabled`）

---

## 1. knowledge（知识库）

### 1.1 设计要点
- 一个 workspace 内，knowledge 名称唯一
- knowledge 维护默认的 chunk/retrieval 策略，但允许 index 覆盖
- 支持“逻辑删除”、标签、描述、统计信息（便于展示/计费/配额）

### 1.2 字段（建议）
- 基础
  - `id` PK
  - `tenant_id`, `workspace_id` (NOT NULL)
  - `name` (NOT NULL)
  - `type` (NOT NULL) 例：`document | qa | code | graph`
  - `description` (NULL)
  - `status` (NOT NULL) 例：`active | archived | disabled`
  - `visibility` (NOT NULL) 例：`private | workspace | tenant`
- 配置（可演进）
  - `settings_json`：知识库通用配置（解析器/语言/过滤规则等）
  - `chunking_json`：默认分块策略（size/overlap/separators）
  - `retrieval_json`：默认检索策略（top_k/rerank/filters）
- 绑定与默认策略
  - `default_embedding_model_ref`：如 `model:openai:text-embedding-3-large`
  - `default_reranker_ref`（可空）
  - `default_index_id`（可空，指向 knowledge_indexes.id）
- 统计（冗余字段，便于列表展示）
  - `doc_count` (NOT NULL default 0)
  - `chunk_count` (NOT NULL default 0)
  - `last_ingested_at` (NULL)
  - `last_indexed_at` (NULL)
- 审计
  - `tags`（text[] 或 json）
  - `created_by`, `updated_by`, `created_at`, `updated_at`, `deleted_at`

### 1.3 关键约束与索引
- UNIQUE：`(tenant_id, workspace_id, name)`
- INDEX：
  - `(tenant_id, workspace_id, status)`
  - `(tenant_id, workspace_id, updated_at DESC)`

---

## 2. knowledge_documents（知识库文档）

### 2.1 设计要点
- 一个 knowledge 内文档支持**多版本**（version）
- 支持多来源：上传文件、爬虫 URL、API 推送、手工文本
- 解析产物（原文提取、结构化信息）建议存对象存储，DB 存引用与摘要
- 为后续权限与合规预留：`access_policy_json`

### 2.2 字段（建议）
- 标识与隔离
  - `id` PK
  - `tenant_id`, `workspace_id` (NOT NULL)
  - `knowledge_id` (FK -> knowledge.id)
  - `doc_key`：同一逻辑文档的稳定 key（例如基于 URL 或业务 id），用于多版本聚合（NOT NULL）
  - `version`：从 1 递增（NOT NULL）
  - `is_latest`：最新版本标记（NOT NULL default true）
- 来源
  - `source_kind`：`upload | crawler | api | manual` (NOT NULL)
  - `source_uri`：URL/外部引用（可空）
  - `external_id`：业务系统的 id（可空）
  - `file_id`：上传文件 id（可空，指向 files 模块）
- 文件/内容元信息
  - `title`（可空）
  - `language`（可空，ISO 639-1）
  - `mime_type`（可空）
  - `filename`（可空）
  - `size_bytes`（可空）
  - `checksum`（可空，sha256）
  - `content_hash`（可空，原文 hash，便于去重）
- 处理流水线状态
  - `status`：`uploaded | parsing | parsed | chunking | chunked | indexing | indexed | failed | deleted`
  - `error_code`（可空）
  - `error_message`（可空，建议短文本）
  - `retry_count`（NOT NULL default 0）
- 解析/分块/索引元数据（引用对象存储）
  - `raw_text_artifact_key`：抽取后的纯文本（可空）
  - `parsed_artifact_key`：结构化解析结果（可空，如 markdown/json）
  - `chunking_json`：本次版本采用的分块策略（可空，默认继承 knowledge.chunking_json）
  - `parse_meta_json`：页数、表格数、图片数、耗时等
  - `index_meta_json`：写入向量数、失败原因摘要等
- 权限与合规
  - `access_policy_json`：例如部门/角色可见、脱敏策略等（可空）
- 审计
  - `created_by`, `updated_by`, `created_at`, `updated_at`, `deleted_at`

### 2.3 关键约束与索引
- UNIQUE：
  - `(tenant_id, workspace_id, knowledge_id, doc_key, version)`
- 推荐索引：
  - `(tenant_id, workspace_id, knowledge_id, is_latest)`
  - `(tenant_id, workspace_id, knowledge_id, status)`
  - `(tenant_id, workspace_id, knowledge_id, updated_at DESC)`
  - `(tenant_id, workspace_id, knowledge_id, content_hash)`（可选，用于去重）

> `is_latest` 建议通过事务保证：同一 `(knowledge_id, doc_key)` 只有一条 latest=true。

---

## 3. knowledge_chunks（文档分块）

### 3.1 设计要点
- chunk 不一定存全文：推荐存 `text_artifact_key` 指向对象存储，DB 存摘要与定位信息
- 支持来源定位：页码/段落/代码块/标题层级
- 支持与向量库映射：每个 chunk 对应一个 `vector_ref`（或 upsert 产生的主键）

### 3.2 字段（建议）
- 标识与隔离
  - `id` PK
  - `tenant_id`, `workspace_id` (NOT NULL)
  - `knowledge_id`（冗余，便于查询；与 document 约束一致）
  - `document_id` (FK -> knowledge_documents.id)
  - `document_version`（冗余，便于追溯；NOT NULL）
- 分块信息
  - `chunk_no`：从 0 递增（NOT NULL）
  - `chunk_key`：稳定标识（可空；如 `{doc_key}:{version}:{chunk_no}`）
  - `content_hash`（可空）
  - `text_preview`：短预览（可空，建议 <= 512）
  - `text_artifact_key`：全文存储 key（可空）
- 定位与结构
  - `start_offset` / `end_offset`（可空，字符偏移）
  - `page_no`（可空）
  - `section_path`（可空，如 `["H1","H2"]`）
  - `bbox_json`（可空，PDF 坐标）
  - `source_meta_json`（可空：表格/代码/图片引用等）
- 统计
  - `char_count`（可空）
  - `token_count`（可空）
- 向量映射与索引状态
  - `embedding_model_ref`（可空；默认继承 knowledge/default 或 index）
  - `vector_ref`：向量库主键/引用（可空，写入后填充）
  - `indexed_at`（可空）
  - `index_status`：`pending | indexed | failed`（NOT NULL default pending）
  - `index_error`（可空）
- 审计
  - `created_at`, `updated_at`

### 3.3 关键约束与索引
- UNIQUE：
  - `(tenant_id, workspace_id, document_id, chunk_no, document_version)`
- 索引：
  - `(tenant_id, workspace_id, knowledge_id, document_id)`
  - `(tenant_id, workspace_id, knowledge_id, index_status)`
  - `(tenant_id, workspace_id, knowledge_id, updated_at DESC)`

---

## 4. knowledge_indexes（索引配置与映射）

### 4.1 设计要点
- 一个 knowledge 可以有多个 index（不同 embedding / 不同 provider / 不同检索配置）
- index 需要记录：向量维度、距离度量、collection/partition 策略、构建版本、统计信息
- 支持灰度：`is_primary` + `status`

### 4.2 字段（建议）
- 标识与隔离
  - `id` PK
  - `tenant_id`, `workspace_id` (NOT NULL)
  - `knowledge_id` (FK -> knowledge.id)
  - `name`（NOT NULL）
  - `is_primary`（NOT NULL default false）
- Provider/存储映射
  - `provider`：`milvus | pgvector | elastic | other` (NOT NULL)
  - `endpoint_ref`（可空，引用 gateway 配置）
  - `collection_name`（可空）
  - `partition_strategy`（可空：`tenant|workspace|knowledge|none`）
  - `namespace`（可空：用于逻辑隔离）
- Embedding/检索配置
  - `embedding_model_ref`（NOT NULL）
  - `dimension`（NOT NULL）
  - `metric_type`（NOT NULL：`cosine | ip | l2`）
  - `index_params_json`（可空：建索引参数）
  - `search_params_json`（可空：检索参数，如 ef/top_k）
  - `reranker_ref`（可空）
  - `filters_json`（可空：默认过滤策略）
- 构建与统计
  - `status`：`draft | building | ready | failed | disabled` (NOT NULL)
  - `build_version`（NOT NULL default 1，重建递增）
  - `last_build_at`（可空）
  - `doc_count`（NOT NULL default 0）
  - `chunk_count`（NOT NULL default 0）
  - `vector_count`（NOT NULL default 0）
  - `last_error_code`（可空）
  - `last_error_message`（可空）
- 审计
  - `created_by`, `updated_by`, `created_at`, `updated_at`, `deleted_at`

### 4.3 关键约束与索引
- UNIQUE：
  - `(tenant_id, workspace_id, knowledge_id, name)`
- 索引：
  - `(tenant_id, workspace_id, knowledge_id, status)`
  - `(tenant_id, workspace_id, knowledge_id, is_primary)`
  - `(tenant_id, workspace_id, updated_at DESC)`

> `is_primary` 建议通过事务保证同一 knowledge 只有一个 primary=true。

---

## 5. 推荐的对象存储 Key 规范（可选但强烈建议）
- 原始文件：`tenants/{tenant}/workspaces/{ws}/knowledge/{ds}/raw/{file_id}`
- 解析文本：`.../docs/{doc_id}/v{version}/raw_text.txt`
- 解析结构：`.../docs/{doc_id}/v{version}/parsed.json`
- chunk 全文：`.../chunks/{chunk_id}.txt`
- 运行日志（如果关联 run）：`.../runs/{run_id}/...`

---

## 6. 与向量库映射建议（Milvus 参考）
- collection 维度建议：`tenant` 或 `workspace`（取决于规模）
- 过滤维度建议：`workspace_id + knowledge_id + document_id + chunk_id`
- chunk 表保留 `vector_ref`，支持回收/重建

---

## 7. 迁移建议
- 先落表结构与索引
- 再实现 pipeline：document.status 与 chunk.index_status 的状态流转
- 再实现 index 构建：knowledge_indexes.build_version 递增 + 统计回写
