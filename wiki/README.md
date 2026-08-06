# Chumji Research Wiki

Obsidian-compatible, local-first research wiki. It deliberately uses no embedding model, vector database, or RAG service.

```bash
python3 tools/llm_wiki.py build
python3 tools/llm_wiki.py lint
python3 -m unittest tests.test_llm_wiki
```

Generated files live under `wiki/indexes/`. Do not hand-edit them.
