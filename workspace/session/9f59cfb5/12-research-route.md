## Research Route — Implementation Document

1. Purpose
 - Perform deeper information gathering, external search, citation tracking, and produce evidence-backed answers for complex queries.

2. Inputs
 - User research queries or escalations from Knowledge/Analysis routes.
 - Evidence: LLM usage across `StepsPlanner`, `SmartThinking`, and `ToolCreator` demonstrates capability to call LLMs (see [steps_planner.py](steps_planner.py#L1), [smartThinking.py](smartThinking.py#L1), [add_new_tool.py](add_new_tool.py#L1)).

3. Outputs
 - Research reports with citations, suggested next steps, and saved research artifacts in long-term memory.

4. Decision criteria
 - When classifier confidence for Research is high, or Knowledge route returns insufficient evidence (`Evidence Not Found`).

5. Required agents
 - Research agent that can orchestrate web searches, literature retrieval, and build a knowledge artifact.

6. Required tools
 - Connectors to web search/APIs (not present), an indexer, and citation manager.

7. Required prompts
 - Research scaffolding prompts (query refinement, source validation, summarization templates).

8. State transitions
 - Query -> gather sources -> validate -> summarize -> persist findings.

9. Failure handling
 - If external sources are unreachable, return `Evidence Not Found` and suggest manual follow-up.

10. Retry handling
 - Re-try searches with query reformulation; escalate to human researcher if still insufficient.

11. Cost considerations
 - External search API calls and embedding/index costs; batch queries to reduce cost.

12. Performance considerations
 - Research may be long-running; return intermediate progress via SSE and persist partial artifacts.

13. Security considerations
 - Respect robots.txt and API license terms; avoid scraping restricted sources.

14. Integration points
 - Called by `task_router` when needed; results should be stored via `LongTermMemory.add_completed_project` or a dedicated research store.

15. Required code modifications
 - Implement `routes/research_route.py`, add connectors/adapters, and integrate with `LongTermMemory` to persist research artifacts.

Traceability: The repository contains LLM call patterns (evidence above), but no external search connectors: Evidence Not Found for connectors.

