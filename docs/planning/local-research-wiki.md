# Local Personal Knowledge Wiki

The personal-agent knowledge system uses an Obsidian-compatible Markdown wiki without embeddings, a vector database, or a RAG service. It covers research, development, work, operations, and confirmed personal preferences through separate domains.

## Boundary

- Evidence remains in original files or explicit source pointers.
- External material enters as raw/source material, never directly as wiki fact.
- The wiki stores explicit entities, concepts, questions, hypotheses, and reproducible notes.
- Deterministic tooling builds aliases, backlinks, a link graph, source deduplication, broken-link reports, and question-gap indexes.
- A view layer is deferred until the research loop proves which structures are useful.
- Agent sessions invoke the `maintain-personal-wiki` workflow automatically when a task may depend on or produce durable reusable knowledge.

The implementation is a clean-room scaffold. It takes architectural inspiration from Karpathy's LLM Wiki concept, Obsidian conventions, and the MIT-licensed `alfadur7/llm-wiki-newsroom`, but imports no external example knowledge, ontology, prompts, or code.

## First pilot

The Poland HS 284190 May 2026 decline is the first pilot. It deliberately distinguishes the reproducible trade-value observation from unsupported causal explanations and records the additional evidence needed to expand the question.
