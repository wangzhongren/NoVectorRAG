# NoVectorRAG
A Retrieval Augmented Generation (RAG) system that uses LLMs for intelligent document chunking and directly judges relevance for retrieval, without requiring a vector database.（一个不依赖向量数据库的 RAG 系统，它利用 LLM 进行智能分块并直接判断相关性来检索信息。）

# [你的项目名称]

[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT) 一个独特的检索增强生成 (RAG) 系统，它完全**不依赖传统的向量数据库或关键词索引**进行信息检索，而是贯穿使用大型语言模型 (LLM) 来实现智能分块和直接的相关性判断。

## ✨ 项目简介 (Introduction)

处理长文档问答是 LLM 应用中的一个常见挑战。传统的 RAG 方案通常依赖于将文档嵌入（Embedding）到向量空间并在向量数据库中进行相似度检索。

本项目提供了一种不同的思路：构建一个**端到端尽可能利用 LLM 能力**的 RAG 流程。我们不使用向量检索，而是直接让 LLM 来理解、判断并找出与用户问题最相关的文档片段。

## 🚀 独特之处与核心功能 (Unique Approach & Features)

与依赖向量数据库的标准 RAG 不同，本项目在关键的检索环节采用了基于 LLM 的独特实现：

1.  **🧠 LLM 驱动的智能分块 (LLM-Driven Intelligent Chunking):** 利用 LLM 的语言理解能力，对原始长文档进行智能化的语义分块，确保每个块包含更完整的上下文和逻辑单元。
2.  **📄 LLM 生成的摘要 (LLM Summarization):** 为每个智能分块后的文本块生成简洁的摘要，用于后续的相关性判断环节。
3.  **🔎 基于 LLM 的相关性判断与评分检索 (LLM-based Relevance Judgment & Scored Retrieval):** 这是项目的核心创新点。
    * 接收用户查询后，系统将文档摘要（通过分批处理以克服上下文窗口限制）发送给 LLM。
    * LLM 直接判断并为每个摘要与用户查询的相关性打分（例如 1-10 分）。
    * 收集所有批次的评分，并根据评分对摘要进行排序和过滤，选出最相关的摘要。
4.  **🔗 关联原文片段：** 根据 LLM 判断出的相关摘要，精确提取对应的原始文本块。
5.  **🗣️ 基于原文的 LLM 回答生成 (Grounded LLM Generation):** 将用户查询和检索到的相关原文片段提供给最终的 LLM，生成高质量、忠实于原文的答案。

这种方法的核心优势在于构建一个**技术栈更统一（聚焦于 LLM API）**，并且**避免了向量数据库的引入**。

## 🚧 权衡与局限性 (Trade-offs and Limitations)

请注意，这种独特的方法也存在一些权衡和潜在局限性，特别是在与经过高度优化的向量检索方案相比时：

* **扩展性：** 处理非常大的文档集或需要对海量数据进行检索时，通过多次 LLM 调用进行判断的扩展性可能不如向量数据库高效。
* **效率和延迟：** 每次检索都需要进行 LLM API 调用，相较于毫秒级的向量数据库查询，检索环节的延迟通常更高。
* **成本：** 检索环节需要进行多次 LLM 调用，可能会导致较高的运行成本。
* **检索的全局最优性：** 分批次的 LLM 判断可能难以保证最终选出的片段是**全局**最相关的，因为 LLM 在判断某个批次时看不到所有其他批次的摘要。
* **LLM 评分一致性：** 让 LLM 在不同调用和不同数据批次之间保持完全一致的评分标准存在挑战。

本项目旨在提供一种**可行的替代方案**，尤其适用于对向量技术有顾虑、文档集规模适中、或希望探索 LLM 直接用于检索判断的研究场景。

## 🛠️ 技术栈 (Technology Stack)

* Python
* 大型语言模型 API (e.g., OpenAI API,或其他兼容 API)
* JSON 文件或其他轻量级存储方式 (用于存储分块和摘要)
