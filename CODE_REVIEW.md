# Codebase Review

## Summary
- The application is a Streamlit-based website copy generator that orchestrates OpenAI calls to produce page outlines, drafts, and refined medical pages while supporting brand inputs and SEO mappings.
- Core modules include:
  - `app.py`: Streamlit UI flow for building site copy and running a QA lab.
  - `generation_pipeline.py`: Outline, draft, refinement, and medical page generation steps using OpenAI responses.
  - `golden_rules.py`: Embedding and retrieval helpers for "golden rule" guidance chunks.
  - `utils.py`: Data models, CSV parsing, keyword parsing, and preview rendering helpers.
  - `openai_client.py`: Client initialization and response handling helpers.

## Notable issues
1. `openai_client.py` references `os` and `json` without importing them, so any API call that touches environment variables or response parsing will raise `NameError` before reaching OpenAI. (e.g., `get_api_key` and `call_openai_json`).
2. `utils.py` omits imports for fundamental dependencies (`dataclass`, typing utilities, `pandas as pd`, `streamlit as st`, and `Document` from `docx`) while using them throughout the module, causing import-time failures and preventing CSV parsing and preview rendering. No validations guard against these missing symbols.
3. The Streamlit app (`app.py`) assumes valid `seo_map` lookups but does not handle missing slug entries when building `seo_entry`, which may result in `KeyError` if a page slug is not present in the SEO CSV. Consider using `.get()` when pulling SEO entries to keep UX resilient.
4. Embedding helpers in `golden_rules.py` do not handle API or rate-limit failures; a single embedding error will abort the entire flow without partial results or user guidance. Adding basic error handling and batching could improve robustness.
5. The `generation_pipeline.py` functions rely on `call_openai_json` returning JSON text, but no guard rails validate that parsed payloads match the expected schemas before continuing, which may surface as runtime errors downstream when rendering.
6. There is no automated test coverage or linting configuration in the repository (`requirements.txt` only lists runtime deps). Adding minimal unit tests for CSV parsing, keyword utilities, and schema handling would increase safety before hitting external APIs.
