# 02 — Architecture Gap Analysis

Summary: This document compares the CURRENT implementation against the TARGET routed multi-agent architecture. Every finding is traceable to code evidence in the repository.

Target stack (for reference):
User -> Request Classifier -> Task Router -> {Chat, Knowledge, Analysis, Development, Automation, Security, Debug, Research}

For each route below I list: What exists (evidence), partial capabilities, what's missing, files to change, files to keep, risks, dependencies.

1) Request Classifier
- What exists: A lightweight pre-filter that decides SKIP vs NEED_AGENT via `SmartThinking.should_skip_thinking`.
	- Evidence: `def should_skip_thinking(self, user_prompt: str, conversation_history: List[Dict] = None)` in smartThinking.py
- Partially exists: It only outputs `SKIP` or `NEED_AGENT` and is invoked at the start of `/stream`.
	- Evidence: `skip, quick_reply_text = smart.should_skip_thinking(user_prompt, recent_history)` in server.py
- Missing: No multi-class classifier that maps requests to the full target categories (Chat, Knowledge, Analysis, Development, Automation, Security, Debug, Research). No confidence scoring or fallback behavior beyond SKIP/NEED_AGENT.
- Files to add/change: create `request_classifier.py`; modify `server.py` `/stream` to call new classifier before planning.
- Files to keep: `smartThinking.py` (its fast-path remains useful for trivial SKIP decisions).
- Risks: Overloading `should_skip_thinking` would conflate responsibilities. Without a classifier, routing will remain monolithic.
- Dependencies: LLM access (OpenRouter/OpenAI client used by `SmartThinking` and `StepsPlanner`).

2) Task Router
- What exists: Inline routing currently implemented as a single execution loop in `/stream` that always generates a `StepsPlanner` plan and executes steps sequentially.
	- Evidence: planner creation `planner = StepsPlanner(api_key)` and `plan = planner.create_plan(...)` in server.py and the step execution loop `while step_index < len(steps)` in server.py
- Partially exists: The execution loop supports refined plans, retries, and user-help branching, but it does not dispatch to specialized route handlers.
- Missing: A separate `TaskRouter` component that makes routing decisions (single-route vs multi-route orchestration), escalation rules, and multi-agent orchestration.
- Files to change/add: add `task_router.py` and refactor `server.py` to call the router instead of directly executing planner steps. Update `StepsPlanner` interface to support route hints in plan metadata.
- Files to keep: `steps_planner.py` (planner logic), `context_owner.py` (session state), `smartThinking.py` (verification hooks).
- Risks: Large refactor of `server.py` is required; must preserve SSE behavior and plan JSON semantics.
- Dependencies: `StepsPlanner`, `ContextOwner`, `execute_tool_backend`.

3) Chat Route
- What exists: Human-facing replies for non-actionable requests via `SmartThinking.quick_reply` and the planner returning `total_steps = 0` path.
	- Evidence: Branch in server.py where if `plan.get("total_steps", 0) == 0` then `assistant_reply = smart.quick_reply(...)` and assistant reply persisted.
- Partially exists: Basic assistant reply generation is present, but no dedicated conversational state machine, no specialized chat agent with turn-level memory control.
- Missing: Dedicated chat agent module, rich context management for dialogues, message-level classifiers, and conversation-level policies.
- Files to change/add: add `routes/chat_route.py` that implements conversation semantics; update `task_router` to route to chat route when appropriate.
- Files to keep: `long_term_memory.py` (context retrieval), `server.py` SSE scaffolding (session start, streaming events).
- Risks: Potential duplication with existing quick-reply; must keep the SKIP fast-path.

4) Knowledge Route
- What exists: `LongTermMemory.get_context_for_prompt` and `ContextOwner.search_memory` plus `/api/memory_search` endpoint.
	- Evidence: `def get_context_for_prompt(self, user_prompt: str)` in long_term_memory.py and `@app.route("/api/memory_search")` handler `memory_search()` in server.py
- Partially exists: Retrieval of simple context snippets and memory search; no indexed vector store, no relevance ranking, and no dedicated knowledge agent.
- Missing: Search/indexing (embeddings), passage ranking, query reformulation, and knowledge route agent wrapping retrieval + RAG.
- Files to change/add: add `routes/knowledge_route.py`, integrate a retrieval/index (or add adapter to external DB), upgrade `LongTermMemory` with an index API.
- Files to keep: `long_term_memory.py`, `context_owner.py`.
- Risks: Current memory is file-based JSON; scaling will require migrating to an indexed store.

5) Analysis Route
- What exists: `SmartThinking.verify_step`, `StepsPlanner.refine_plan`, and `final_verification` implement analysis and verification capabilities.
	- Evidence: `verify_step` and `final_verification` in smartThinking.py and `refine_plan` in steps_planner.py
- Partially exists: Analysis is embedded in the execution loop and focused on step verification; there's no separate analysis agent orchestrating deeper investigations or running multiple probes in parallel.
- Missing: Dedicated analysis agent, standardized result objects, and workflows for multi-step analytical tasks.
- Files to change/add: create `routes/analysis_route.py` and refactor `smartThinking.py` into `analysis_agent.py` with clearer interfaces.
- Files to keep: `steps_planner.py`, `steps_log.json` (execution records) for auditability.

6) Development Route
- What exists: `write_file` tool, `dynamic_tool_loader` for sample_code execution, `ToolCreator` for proposing new tools, and `steps_planner` that generates write_file steps.
	- Evidence: `write_file` registration in server.py, dynamic loader `load_dynamic_tools_from_registry()` in dynamic_tool_loader.py, and `ToolCreator.generate_tool_details` in add_new_tool.py.
- Partially exists: Basic file creation and dynamic tool scaffolding exist; no dedicated Decomposer/Builder/Reviewer pipeline, nor code linting/unit tests integration.
- Missing: Formal planner->decomposer->builder->reviewer workflow, code validators, CI hooks, and reviewer agent.
- Files to change/add: `routes/development_route.py`, `builders/` with linters/test harness integration, update `StepsPlanner` to produce structured development tasks (e.g., code, tests, run commands).
- Files to keep: `dynamic_tool_loader.py`, `add_new_tool.py`, `steps_planner.py`.
- Risks: `dynamic_tool_loader` executes `sample_code` via `exec()`; security risk when loading untrusted code. Also `write_file` allows arbitrary writes within `scope_mgr`-approved paths.

7) Automation Route
- What exists: `execute_command` tool, `scope_manager` checks, and automated plan execution loop.
	- Evidence: `execute_command_tool` in server.py, `is_path_allowed` in scope_manager.py, and execution inside `/stream` loop `tool_result = execute_tool_backend(tool_name, arguments)` in server.py
- Partially exists: Basic automation flows work; no scheduler, transactional safety, or sandboxing for dangerous commands.
- Missing: Stronger sandboxing, role-based policies, dry-run mode, and an Automation agent that can schedule and rollback operations.
- Files to change/add: `routes/automation_route.py`, enhancements to `scope_manager.py` to support whitelisting/blacklisting policies, add sandboxing for `execute_command` (e.g., containerized execution, or simulated dry-run option).
- Files to keep: `server.py`'s execute path, `context_owner.py` for command history.
- Risks: `execute_command` currently spawns subprocesses and sometimes uses shell=True for certain commands — risk of command injection if plan generation includes malicious commands.

8) Security Route
- What exists: `scope_manager.is_path_allowed` provides basic path scoping; `ContextOwner.get_failure_type` classifies some failure types.
	- Evidence: `is_path_allowed` in scope_manager.py and `get_failure_type` in context_owner.py
- Partially exists: Basic containment and failure classification; no dedicated security agent, auditing, RBAC, or secrets handling policies.
- Missing: Security route and policy engine, auditing pipeline, tool permission model, and runtime isolation for dynamic tools.
- Files to change/add: `routes/security_route.py`, harden `dynamic_tool_loader.py` (remove raw exec, validate sandbox), add an authorization layer around `execute_tool_backend`.
- Files to keep: `scope_manager.py`, `steps_log.json` (audit trail).
- Risks: `dynamic_tool_loader` uses `exec()` on `sample_code` from `tools_registry.json` — high-risk. `execute_command` can run arbitrary shell commands; there is no RBAC.

9) Debug Route
- What exists: `ContextOwner.is_stuck`, `generate_help_question`, `steps_log.json`, and `save_step_log` in `server.py` provide on-failure debugging and user help.
	- Evidence: `is_stuck` and `generate_help_question` in context_owner.py, `save_step_log` in server.py and `steps_log.json` contents.
- Partially exists: Reactive debugging when steps fail; no dedicated debug agent that can run diagnostics proactively or suggest corrective patches automatically (beyond `StepsPlanner.refine_plan`).
- Missing: Structured debugging route, causal analysis tools, and automated patch suggestion/validation cycle.
- Files to change/add: `routes/debug_route.py`, extend `smartThinking.final_verification` to produce code patches and unit-run steps.

10) Research Route
- What exists: LLM-driven generation capabilities (used across the codebase), but no research agent or tooling for literature search, citations, or persistent research artifacts.
	- Evidence: LLM clients used in `steps_planner.py`, `smartThinking.py`, `add_new_tool.py`.
- Missing: Research agent, connectors to external sources, knowledge graph, citation tracking.
- Files to change/add: `routes/research_route.py`, connectors/adapters for search APIs, indexers.

Overall conclusions:
- The codebase already implements many foundational building blocks: an LLM-backed planner (`StepsPlanner`), an execution loop with verification and retry (`/stream` in `server.py`), session & memory (`ContextOwner`, `LongTermMemory`), dynamic tool registry (`tools_registry.json` + `dynamic_tool_loader.py`), and basic scope controls (`ScopeManager`).
- Missing core router/classifier and per-route specialized agents. The major refactor points are `server.py` (central execution loop), `dynamic_tool_loader.py` (security), and adding `request_classifier.py` and `task_router.py` plus `routes/` modules for each route.

Next: Phase 3 (Route Design). I will generate per-route implementation documents that map required components back to the files above and provide exact code modification guidance.
