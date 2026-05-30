## Knowledge Route — Implementation Document

1. Purpose
 - Retrieve, rank, and provide factual context from the agent's long-term memory and session artifacts to support user queries and other routes (RAG).

2. Inputs
 - `query` (string) from classifier or user.
 - Available memory artifacts: `LongTermMemory.user_profile`, `project_history`, `files_created`, `ContextOwner.file_registry`.
 - Evidence: `LongTermMemory.get_context_for_prompt` builds context from `user_profile` and `project_history` in [long_term_memory.py](long_term_memory.py#L1), and `/api/memory_search` calls `context_owner.search_memory` in [server.py](server.py#L392).

3. Outputs
 - Ranked passages, citations (file paths), or concise factual answers to requests.

4. Decision criteria
 - If the classifier marks the request as knowledge (high confidence), route here.
 - If `StepsPlanner` plan requires reading files as part of steps, the Task Router should call Knowledge Route to fetch supporting context.

5. Required agents
 - Knowledge agent that can: perform memory search, call an embeddings/indexer (not present), perform passage ranking, and produce an answer.

6. Required tools
 - `context_owner.search_memory` (existing) returns `found_files`, `found_commands`, `relevant_conversation`.
 - Evidence: `def search_memory(self, query: str)` in [context_owner.py](context_owner.py#L1).

7. Required prompts
 - Retrieval prompt templates to turn memory results into context for LLM answers.

8. State transitions
 - Query -> retrieve artifacts -> rank/filter -> return or escalate to Research Route.

9. Failure handling
 - If no results, respond with explicit "Evidence Not Found" to comply with the core rule.

10. Retry handling
 - Re-run retrieval with relaxed matching or ask classifier to re-route to Research.

11. Cost considerations
 - Avoid LLM calls when memory search yields strong matches; use cached text responses.

12. Performance considerations
 - Current memory is file-based JSON — add an index/embedding store for scale.

13. Security considerations
 - Redact secrets from `files_created` or `file_registry` before returning passages.

14. Integration points
 - Called by `task_router` when a plan references `read_file` or the classifier chooses Knowledge route.

15. Required code modifications
 - Create `routes/knowledge_route.py` that wraps `context_owner.search_memory` and `long_term_memory.get_context_for_prompt`.
 - Add an adapter in `long_term_memory.py` to export data for indexing (if adding embeddings).

Traceability: Evidence for memory APIs is in [long_term_memory.py](long_term_memory.py#L1) and [context_owner.py](context_owner.py#L1); `/api/memory_search` endpoint exists in [server.py](server.py#L392).

