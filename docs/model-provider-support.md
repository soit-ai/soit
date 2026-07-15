# SOIT 1.0 Model Provider Support Matrix

Status: Phase 1 acceptance support matrix. This document records implementation evidence and the remaining live-credential checks for ModelHub 1.0.

## Matrix

| Provider | Runtime adapter | ModelHub diagnostics | Phase 1 acceptance status | Notes |
|---|---|---|---|---|
| OpenAI | Yes, `app/adapters/llm/openai.py` | Catalog, chat test, embedding test | Accepted implementation path | Supports chat, streaming, tool calls, embeddings, and embedding-based rerank. |
| OpenAI-compatible | Yes, through `OpenAILLMPort` with `base_url` | Catalog/chat/embedding diagnostics through OpenAI-compatible client paths | Accepted implementation path | Covers self-hosted or compatible gateways when API semantics match OpenAI. |
| DeepSeek | Yes, `app/adapters/llm/deepseek.py` | Provider configuration is supported; runtime uses OpenAI-compatible chat adapter | Accepted implementation path for chat runtime | Model IDs containing `:` are preserved by DeepSeek-specific parsing. |
| Anthropic | Yes, `app/adapters/llm/anthropic.py` | Catalog and chat diagnostics | Diagnostic/runtime foundation, with limitations | Chat is supported. Tool calling, embeddings, and rerank are explicitly unsupported in this adapter. |
| Gemini | No dedicated runtime adapter in `app/adapters/llm` | Chat diagnostics and catalog paths in ModelHub provider adapter | Diagnostic foundation only | Do not count as Phase 1 runtime acceptance until a runtime adapter is added. |

## Phase 1 acceptance

Phase 1 requires at least two mainstream model source types to be configurable and usable through the 1.0 flow. Current implementation evidence supports these as the acceptance candidates:

1. OpenAI or OpenAI-compatible provider.
2. DeepSeek provider through the OpenAI-compatible runtime path.

Anthropic can be used for chat runtime where configured, but it has documented limitations. Gemini must remain diagnostic-only until a runtime adapter is implemented.

## Verification commands

Run these from `server/`:

```bash
uv run pytest tests/unit/test_modelhub_provider_catalog.py -q
uv run pytest tests/unit/test_openai_tool_calling.py tests/unit/test_deepseek_llm_port.py tests/unit/test_anthropic_llm_port.py -q
uv run pytest tests/entrypoints/test_modelhub_api.py tests/entrypoints/test_modelhub_workbench_api.py -q
```

## Live credential spot-check

Do not mark the roadmap provider-source exit condition complete until at least two provider kinds have fresh local evidence with real or customer-approved test credentials:

- Provider can be created or updated from ModelHub.
- Connectivity test returns a successful response.
- An active model can be selected by Agent / Workflow / Chat.
- A failure state is visible and understandable when credentials are invalid.

The live credential evidence should record provider kind, test model ID, timestamp, and whether the source was OpenAI, OpenAI-compatible, DeepSeek, Anthropic, or Gemini.

Copy `docs/deployment/model-provider-spotcheck-evidence.example.json` to `docs/deployment/model-provider-spotcheck-evidence.json` for each release candidate, replace every evidence reference with real diagnostic, chat completion, and cost attribution output, and validate it from `server/` with repository-root checks enabled:

```bash
uv run python scripts/verify_model_provider_spotcheck.py ../docs/deployment/model-provider-spotcheck-evidence.json --repo-root ..
```

The verifier requires at least two passing provider records and rejects missing credential, model, diagnostic, chat, or cost evidence references. Diagnostic, chat completion, and cost attribution evidence refs must be unique across provider records and must exist as local files when `--repo-root` is used.
