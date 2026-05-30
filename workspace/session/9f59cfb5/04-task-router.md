## 04 — Task Router Design

Purpose: implement a production-grade Task Router that consumes classifier output, plan metadata, and runtime signals to select and orchestrate route handlers (Chat, Knowledge, Analysis, Development, Automation, Security, Debug, Research).

1) Inputs
 - `user_prompt`, `session_id`, `classification` (category + confidence), `enhanced_context` (from `LongTermMemory`), and optionally a `plan` returned by `StepsPlanner`.
 - Evidence: `/stream` builds `enhanced_prompt` and calls `StepsPlanner.create_plan(...)` in [server.py](server.py#L426-L436).

2) Outputs
 - Selected route(s) and route-specific execution instructions; SSE events streamed back to user are unchanged (the router interfaces with existing SSE streams in `server.py`).

3) Route selection rules
 - If classifier confidence >= 0.85, route to that category directly.
 - If planner returns `total_steps == 0`, prefer Chat Route.
 - If plan contains `read_file`/`write_file`/`execute_command`, prefer Development/Automation depending on tool mix (commands -> Automation; primarily `write_file` -> Development).
 - If `context_owner.is_stuck` or repeated verification failures occur, prefer Debug/Analysis.
 - Evidence: existing heuristic behavior in [server.py] where planner always executes steps; propose replacing with router decisions.

4) Escalation rules
 - If a route fails repeatedly (exceeds `max_retries_per_step` or `ContextOwner.is_stuck`), escalate to Analysis -> Debug -> Security as needed.
 - Example: persistent command failures escalate to Automation->Analysis->Debug.
 - Evidence: Current code uses `planner.refine_plan` and `context_owner.is_stuck` to detect stuck states in [server.py](server.py#L486-L506).

5) Route switching rules
 - Allow route switching mid-execution under two cases:
	 a) Plan refinement returns steps that indicate a different route (e.g., a read_file reveals a research need) -> router switches accordingly.
	 b) Safety/security check fails -> route to Security to validate or deny the operation.

6) Multi-route execution rules
 - Support multi-route composition: split plan into segments by tool-type and dispatch segments to specialized route handlers; collect results and run final verification in Analysis route.
 - Implementation: Task Router transforms `plan.steps` into sub-plans by grouping contiguous steps of same route and invokes handlers sequentially.

7) Failure routing rules
 - On failure of a step, Task Router: record failure, consult `ContextOwner` for failure counts, request refinement via `StepsPlanner.refine_plan`, or route to Debug when `is_stuck` returns True.
 - Evidence: this control flow exists in [server.py](server.py#L486-L506).

8) Integration points (exact)
 - Replace the inlined plan-execute loop in `server.py` `/stream` (starting at `plan = planner.create_plan(...)` and the `while step_index < len(steps)` loop) with:
	 - `classification = request_classifier.classify(user_prompt)`
	 - `route_plan = task_router.route(user_prompt, classification, plan, session_context)`
	 - For each segment in `route_plan`, call the corresponding `routes/<name>_route.handle(segment, session_context)` which returns SSE-ready events and step results.
 - Keep SSE event emission behavior by returning/generating the same `step_start`, `step_result`, `plan_refined`, `need_help`, `final_success`, `final_failure` events from route handlers.

9) Required files and modifications
 - Add `task_router.py` implementing the routing logic and grouping of steps.
 - Add `routes/` package with modules for each route (`chat_route.py`, `knowledge_route.py`, `analysis_route.py`, `development_route.py`, `automation_route.py`, `security_route.py`, `debug_route.py`, `research_route.py`).
 - Modify `server.py` to call `request_classifier` and `task_router` prior to executing steps.

10) Observability and telemetry
 - Task Router must log chosen routes, classifier confidences, and reasons for switching into `steps_log.json` with `session_id` for traceability.

11) Rollback and transaction semantics
 - For stateful actions (`write_file`, destroy operations), implement optional transaction grouping and rollback steps via a `dry_run` and `commit` pattern enforced by Automation/Development route handlers.

12) Risks and mitigations
 - Risk: refactor of `server.py` may introduce regressions; mitigate by implementing `task_router` behind a feature flag and keeping the original loop as a fallback.
 - Risk: multi-route orchestration complexity; mitigate by starting with conservative grouping rules (tool-type based) and iterating.

Traceability: All the orchestration primitives referenced above are visible in [server.py] (plan creation, execution loop, refinement, stuck detection), `StepsPlanner`, and `ContextOwner`.
