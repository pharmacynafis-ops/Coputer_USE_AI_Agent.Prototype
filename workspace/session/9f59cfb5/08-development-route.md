## Development Route — Implementation Document

1. Purpose
 - Implement feature development workflows: planning, decomposition, code generation (write_file), testing, and review.

2. Inputs
 - `user_prompt` describing the requested development task; context from `LongTermMemory` and existing files.
 - Evidence: `StepsPlanner.create_plan` is already used to produce write_file steps (see [steps_planner.py](steps_planner.py#L1) and SSE `plan` event in [server.py](server.py#L436)).

3. Outputs
 - Files created/updated, execution logs, and developer-facing reports.

4. Decision criteria
 - If the classifier or planner produces steps that include `write_file` or development-specific tools, route to Development.

5. Required agents
 - Planner (existing `StepsPlanner`), Task Decomposer (new), Builder (executor using `write_file`), Reviewer (new; LLM-based code review), Evidence Collector (long_term_memory/file_registry), Decision Engine (existing `smartThinking.final_verification` extended).

6. Required tools
 - `write_file`, `read_file` (existing), `dynamic_tool_loader` for additional developer helper tools.

7. Required prompts
 - Code generation templates, unit-test scaffolding prompts, and review checklist prompts.

8. State transitions
 - Request -> Planner -> Decomposer -> Builder -> Reviewer -> Evidence Collector -> Decision Engine -> Done or Correction.

9. Failure handling
 - If `write_file` fails, use `StepsPlanner.refine_plan` (existing) and escalate to `need_help` if stuck.
	- Evidence: refinement call `planner.refine_plan(plan, step, tool_result, workspace_path)` in [server.py](server.py#L494).

10. Retry handling
 - Use `max_retries_per_step` logic already present in [server.py](server.py#L458); integrate with reviewer to stop after N failed builds.

11. Cost considerations
 - Generating full code + tests uses tokens; prefer incremental generation and offload heavy runs to asynchronous workers.

12. Performance considerations
 - Large code generation should be chunked and validated incrementally (write_file + run tests).

13. Security considerations
 - Dynamic tool loading (`dynamic_tool_loader.py`) currently `exec()`s sample code. MUST be sandboxed or validated before enabling in production.
	- Evidence: `exec(sample_code, namespace)` in [dynamic_tool_loader.py](dynamic_tool_loader.py#L1).

14. Integration points
 - `task_router` should forward development plans to `routes/development_route.py` which orchestrates builder/reviewer and uses `execute_tool_backend` for `write_file` steps.

15. Required code modifications
 - Add `routes/development_route.py` implementing the workflow and reuse `StepsPlanner` for decomposition.
 - Add `builders/` helpers (formatters, linters) and a test harness runner that uses `execute_command` under controlled scope.

Traceability: Existing `write_file` tool registration and dynamic tool loader present in [server.py](server.py#L150) and [dynamic_tool_loader.py](dynamic_tool_loader.py#L1); `StepsPlanner` controls write_file argument normalization (see `create_plan` normalization in [steps_planner.py](steps_planner.py#L1)).

-- Detailed Workflow (States & Transitions)

States:
 - RECEIVED: Router has accepted the request for Development.
 - PLANNED: `StepsPlanner` has emitted a plan containing development steps.
 - DECOMPOSED: Decomposer (new) has split high-level plan items into concrete build/test steps.
 - BUILDING: Builder executes `write_file` steps and invokes `execute_command` for test/run commands.
 - REVIEWING: Reviewer agent runs static analysis and unit tests; may produce corrections.
 - EVIDENCE_COLLECTING: Evidence Collector records created files and test outputs into `LongTermMemory` and `ContextOwner.file_registry`.
 - DECIDING: Decision Engine (`smartThinking.final_verification`) evaluates if goal achieved.
 - COMPLETED / FAILED: Terminal states.

Transitions (examples):
 - RECEIVED -> PLANNED: Task Router invokes `StepsPlanner.create_plan` or accepts an existing plan.
 - PLANNED -> DECOMPOSED: Decomposer rewrites any large code write into smaller safe steps (single `write_file` per file, tests as separate steps).
 - DECOMPOSED -> BUILDING: Builder sequentially executes steps using `execute_tool_backend` (existing API) and marks results.
 - BUILDING -> REVIEWING: After build steps succeed, Reviewer runs lint/tests via `execute_command` and may request corrections.
 - REVIEWING -> EVIDENCE_COLLECTING: On pass, Evidence Collector saves file records using `LongTermMemory.add_file_record` (evidence: `long_term_memory.add_file_record` in [long_term_memory.py](long_term_memory.py#L1)).
 - EVIDENCE_COLLECTING -> DECIDING: Call `smart.final_verification` (evidence: called in [server.py](server.py#L584)).
 - DECIDING -> COMPLETED or FAILED: If `is_goal_achieved` true -> COMPLETED, else FAILED and create a correction plan.

Files required / modifications (precise):
 - `routes/development_route.py`: orchestrates the above states and emits SSE-compatible events.
 - `builders/runner.py`: executes `write_file` and `execute_command` with transactional semantics; uses `scope_manager.is_path_allowed` to validate paths.
 - `reviewers/lint_and_test.py`: runs linters and test commands through `execute_command` and returns structured results.
 - `decomposer/simple_decomposer.py`: converts high-level tasks into atomic steps; this may call `StepsPlanner` again with constrained prompts.
 - Modify `server.py`: remove direct write/read loop and call `task_router`, or inject development handler at the point where `plan` is processed.

Validation and rollback:
 - Validation: Unit tests (if present) and `smart.verify_step` used on each step; final `smart.final_verification` for end-to-end validation.
 - Rollback: For each `write_file` action, keep a backup copy (in memory or temp path) so reviewer can revert if final verification fails. Implement `builders/runner.py` to create `.bak` files prior to writing.

Completion criteria (Development route):
 - All `write_file` steps executed successfully and pass reviewer checks.
 - `smart.final_verification` returns `is_goal_achieved: true`.


