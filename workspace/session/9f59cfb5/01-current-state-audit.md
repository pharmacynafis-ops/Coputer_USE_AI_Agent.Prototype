# 01 — Current State Audit

This audit documents discoveries from the codebase. Every statement below is supported by direct code evidence and references the relevant file and symbol.

- File: server.py
  - Class/Function: create_agent(api_key=None)
  - Evidence: `def create_agent(api_key=None):` defined in server.py
  - Current responsibility: Builds the AI `Agent` instance, registers core tools (`write_file`, `read_file`, `execute_command`, `redirect_to_scope_page`, `create_new_customization_tool`) and loads dynamic tools via `load_dynamic_tools_from_registry()`; returns `(agent, tools_registry)`.

- File: server.py
  - Function: execute_tool_backend(tool_name: str, arguments: Dict[str, Any])
  - Evidence: `def execute_tool_backend(tool_name: str, arguments: Dict[str, Any]) -> str:` in server.py
  - Current responsibility: Central dispatcher that enforces scope checks via `scope_mgr.is_path_allowed` and invokes registered tool implementations from `current_tools`.

- File: server.py
  - Request entry points / Routes:
    - `/api/set_scope` -> `set_scope()` (calls `scope_mgr.establish_scope`)
    - `/api/save_new_tool` -> `api_save_new_tool()` (uses `ToolCreator.save_new_tool`)
    - `/api/steps_log` -> `get_steps_log()`
    - `/api/memory_search` -> `memory_search()` (calls `context_owner.search_memory`)
    - `/api/set_api_key` -> `set_api_key()` (re-creates agent via `create_agent`)
  - Evidence: `@app.route` decorators and handler functions present in server.py.
  - Current responsibility: HTTP API surface for scope, history, tool creation, memory search, and agent API-key updates.

- File: dynamic_tool_loader.py
  - Functions: `load_dynamic_tools_from_registry()`, `parse_function_signature(code)`, `create_pydantic_model_for_tool(...)`, `register_dynamic_tools_with_agent(...)`
  - Evidence: Function definitions exist with these exact names in dynamic_tool_loader.py
  - Current responsibility: Reads `tools_registry.json`, parses `sample_code` AST to infer function signatures, builds Pydantic models for tool parameters, executes `sample_code` to obtain callable functions, and returns `loaded_tools` mapping.

- File: tools_registry.json
  - Evidence: JSON includes an entry `create_new_folder` with `sample_code` string and `parameters`.
  - Current responsibility: Persistent registry of dynamic tools used by `dynamic_tool_loader`.

- File: steps_planner.py
  - Class: `StepsPlanner` with methods `create_plan(...)` and `refine_plan(...)`
  - Evidence: `class StepsPlanner:` and `def create_plan(self, user_prompt: str, workspace_path: str = None) -> Dict[str, Any]:`
  - Current responsibility: Uses an LLM to transform a user prompt into a strict JSON plan of steps (tools + arguments), normalizes keys (`path`), and produces `session_id` for the plan.

- File: smartThinking.py
  - Class: `SmartThinking` with methods `should_skip_thinking`, `verify_step`, `final_verification`, `analyze_and_refine`.
  - Evidence: `class SmartThinking:` and method definitions in smartThinking.py
  - Current responsibility: Quality-checks agent responses, decides whether to short-circuit (SKIP vs NEED_AGENT), verifies tool results, and produces final verification/correction plans.

- File: long_term_memory.py
  - Class: `LongTermMemory` with methods `get_context_for_prompt`, `add_file_record`, `update_interaction`, etc.
  - Evidence: `class LongTermMemory:` and methods present in long_term_memory.py
  - Current responsibility: Persistent storage of user profile, project history, files created, and providing context snippets used by prompts.

- File: scope_manager.py
  - Class: `ScopeManager` and `WorkspaceScope`
  - Evidence: `class ScopeManager:` and `def is_path_allowed(self, path: str) -> bool:`
  - Current responsibility: Maintains workspace scope, enforces `is_path_allowed` checks used by `execute_tool_backend`, provides `establish_scope` to set allowed/forbidden directories.

- File: context_owner.py
  - Class: `ContextOwner` with methods `start_session`, `update_after_step`, `search_memory`, `is_stuck`, `generate_help_question`, `resume_session`.
  - Evidence: `class ContextOwner:` and method definitions in context_owner.py
  - Current responsibility: In-session context tracking (conversation history, file & command registries, failure log), deciding when the agent is stuck and producing user help prompts.

- File: add_new_tool.py
  - Class: `ToolCreator` with methods `generate_tool_details` and `save_new_tool`
  - Evidence: `class ToolCreator:` and methods in add_new_tool.py
  - Current responsibility: Generates candidate tool metadata via an LLM and persists new tool entries into `tools_registry.json`.

- Observed flows (evidence-backed):
  - Agent creation & tool registration: `server.create_agent()` constructs an `Agent` with system prompt and registers core tools and dynamic tools loaded by `dynamic_tool_loader.load_dynamic_tools_from_registry()`.
    - Evidence: calls to `load_dynamic_tools_from_registry()` and `@agent.tool_plain` decorators inside `create_agent`.
  - Tool execution flow: `execute_tool_backend()` receives `tool_name` and `arguments`, enforces scope via `scope_mgr.is_path_allowed`, and calls corresponding function from `current_tools`.
    - Evidence: explicit branching in `execute_tool_backend` in server.py.
  - Planning flow: `StepsPlanner.create_plan()` produces a JSON plan and sets `session_id`.
    - Evidence: `plan["session_id"] = str(uuid.uuid4())` in steps_planner.py.
  - Memory flow: `LongTermMemory` provides `get_context_for_prompt()` and `ContextOwner` maintains `session` and `file_registry` snapshots.
    - Evidence: methods exist and are called from server or other modules (e.g., server imports and instantiates `LongTermMemory`, `ContextOwner`).
 
  - File: server.py
    - Route: `/stream` -> `stream()`
    - Evidence: `@app.route("/stream")` and `def stream():` in server.py
    - Current responsibility: Primary request entry point for user prompts (SSE). Behavior observed:
      - Uses `SmartThinking.should_skip_thinking` to short-circuit trivial requests.
      - Establishes or resumes sessions via `ContextOwner.start_session` / `ContextOwner.resume_session` and yields `session_start` SSE event.
      - Builds `enhanced_prompt` combining `LongTermMemory.get_context_for_prompt` and recent history.
      - Calls `StepsPlanner.create_plan` to produce a JSON plan and yields it as SSE `plan` event.
      - Executes plan steps in a loop: for each step, calls `execute_tool_backend`, verifies with `SmartThinking.verify_step`, updates `ContextOwner.update_after_step`, logs via `save_step_log`, and yields `step_start`/`step_result` SSE events.
      - On repeated failures uses `ContextOwner.is_stuck` to ask the user for help (yields `need_help`).
      - Invokes `StepsPlanner.refine_plan` to attempt automated recovery and yields `plan_refined` events.
      - After completion runs `SmartThinking.final_verification` and either yields `final_success` or `final_failure` events; may run correction plan steps similarly.
      - Persists conversation and long-term memory updates (`long_term_memory.update_interaction`, `long_term_memory.add_file_record`).

    - Evidence lines: plan creation `plan = planner.create_plan(...)`, loop `while step_index < len(steps)`, `tool_result = execute_tool_backend(tool_name, arguments)`, `is_success = smart.verify_step(step, tool_result)`, `refined_plan = planner.refine_plan(plan, step, tool_result, workspace_path)`, `final_check = smart.final_verification(user_prompt, plan, execution_log)`.


If you want, I will continue by expanding the audit to additional files and generating the full gap analysis document next.
