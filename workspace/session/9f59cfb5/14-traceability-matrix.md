# Traceability Matrix

Requirement -> Evidence -> Proposed Change -> Files Impacted

- Request Classification -> Evidence: `SmartThinking.should_skip_thinking` invoked in [server.py](server.py#L416) -> Change: add `request_classifier.py` and call from `/stream` -> Files: `request_classifier.py`, `server.py`

- Task Router -> Evidence: inlined plan-execute loop in [server.py](server.py#L436-L521) -> Change: add `task_router.py`, refactor `/stream` to call router -> Files: `task_router.py`, `routes/*`, `server.py`

- Chat Route -> Evidence: planner returns `total_steps == 0` fallback uses `smart.quick_reply` ([server.py](server.py#L444)) -> Change: implement `routes/chat_route.py`, route directly when classifier indicates `chat` -> Files: `routes/chat_route.py`, `server.py`, `task_router.py`

- Knowledge Route -> Evidence: `LongTermMemory.get_context_for_prompt` and `/api/memory_search` ([long_term_memory.py], [server.py]) -> Change: implement `routes/knowledge_route.py` and memory indexing adapter -> Files: `routes/knowledge_route.py`, `long_term_memory.py`

- Analysis Route -> Evidence: `smart.final_verification` and `StepsPlanner.refine_plan` used in [server.py] -> Change: extract into `routes/analysis_route.py` and make it callable by `task_router` -> Files: `routes/analysis_route.py`, `smartThinking.py`, `steps_planner.py`

- Development Route -> Evidence: `write_file` tool, `dynamic_tool_loader` exist ([server.py], [dynamic_tool_loader.py]) -> Change: create `routes/development_route.py`, `decomposer/`, `builders/`, `reviewers/` -> Files: `routes/development_route.py`, `decomposer/*`, `builders/*`, `reviewers/*`, `dynamic_tool_loader.py`

- Automation Route -> Evidence: `execute_command` tool and `execute_tool_backend` in [server.py] -> Change: add `routes/automation_route.py` and sandboxed runner -> Files: `routes/automation_route.py`, `automation/sandbox_runner.py`, `scope_manager.py`

- Security Route -> Evidence: `scope_manager.is_path_allowed` present but `dynamic_tool_loader.exec()` is unsafe -> Change: add `routes/security_route.py`, `security/validator.py`, harden `dynamic_tool_loader.py` to remove `exec()` -> Files: `routes/security_route.py`, `security/validator.py`, `dynamic_tool_loader.py`, `tools_registry.json`

- Debug Route -> Evidence: `ContextOwner.is_stuck` and `generate_help_question` in [context_owner.py] -> Change: implement `routes/debug_route.py` to handle interactive user recovery -> Files: `routes/debug_route.py`, `server.py`

- Research Route -> Evidence: LLM usage present but no external connectors -> Change: implement `routes/research_route.py` and connectors to external search -> Files: `routes/research_route.py`, `connectors/*`, `long_term_memory.py`

Notes:
- Any recommendation that would introduce execution of untrusted code is conditional on first hardening `dynamic_tool_loader.py` (Evidence: `exec(sample_code, namespace)` in [dynamic_tool_loader.py]). Until hardened, dynamic tool execution should be disabled by default.

*** End of matrix
