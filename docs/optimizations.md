# LLM API optimizations — tracking

List of possible LLM API optimizations and whether they are implementable with the current architecture. For those that are not, what is needed is listed.

---

## Implementable now (no architecture change)

- [ ] **Retrieval instead of long prompts (RAG)**  
  Store docs in `EmbeddingStore`; implement RAG as tools (e.g. Obsidian search, doc search) that call `EmbeddingStore.search()` and return relevant chunks. Model receives short context instead of full documents.  
  *No change needed.*

- [ ] **Tool-first architecture**  
  Tools already preprocess data and return `ToolResult`; orchestrator passes that to the model. Optional later: explicit “preprocessing” step that runs tools before the first model call (e.g. always run search for a query).  
  *No change needed for basic tool-first; optional pipeline refinement later.*

---

## Blocked — what’s needed

### Multi-model routing

*Use different models by task complexity (cheap for simple, strong for complex).*

- [ ] **Model router or multiple providers**  
  Either a single facade that delegates by task (chat / embedding / “simple” / “complex”) or separate providers (e.g. chat provider, embedding provider) wired into the app.

- [ ] **Task type / complexity**  
  A way to decide which model to use: heuristic (e.g. message length, presence of tools), or a cheap classifier call before the main request.

- [ ] **Config**  
  Which model (or provider) per task type (e.g. `chat`, `embed`, `simple`, `complex`).

---

### Prompt caching

*Reuse repeated prompt parts (system instructions, tool descriptions) and use provider cache APIs.*

- [ ] **Request / message format**  
  Extend `ChatRequest` or message format to mark cacheable regions (e.g. system block, tool definitions). E.g. cache boundaries or a “cacheable” flag on message parts.

- [ ] **ModelProvider support**  
  Implementations use the provider’s cache API (e.g. OpenAI cache control parameters). No new interface method required if cache is expressed via existing request fields.

---

### Local models for cheap tasks

*Run small local models for embeddings, classification, tagging; keep paid APIs for heavy work.*

- [ ] **Same as multi-model routing**  
  Route by task: embeddings / classification / tagging → local provider; complex chat → cloud. Requires model router or separate embedding (and optionally “simple”) provider.

- [ ] **Config**  
  Which provider and model per task type (e.g. `embed` → local, `chat` → OpenAI).

---

### Batch processing

*Combine multiple similar tasks into one request to reduce prompt overhead and cost.*

- [ ] **Product definition**  
  Define what “batch” means (e.g. bulk tag notes, bulk summarize). Current design is one request per user message.

- [ ] **API**  
  New surface: e.g. `POST /batch` or a job queue that aggregates tasks and sends one or few requests to the model.

- [ ] **ModelProvider**  
  Optional `batch_chat(requests)` (or similar) if the provider supports batched requests; otherwise implement batching in the orchestrator (e.g. multiple tasks in one prompt).

---

## Summary

| Optimization              | Status        |
|---------------------------|---------------|
| RAG                       | Implementable |
| Tool-first                | Implementable |
| Multi-model routing       | Blocked       |
| Prompt caching            | Blocked       |
| Local for cheap tasks     | Blocked       |
| Batch processing          | Blocked       |

See **§7** in `architecture.md` for how each fits the current design.
