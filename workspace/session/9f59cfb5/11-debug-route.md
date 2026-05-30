## Debug Route — Implementation Document

1. Purpose
 - Diagnose persistent failures, recommend corrective actions, and interactively solicit user guidance when automated fixes fail.

2. Inputs
 - Failed execution steps, failure logs from `ContextOwner.failure_log`, and `steps_log.json`.
 - Evidence: `context_owner.failure_log` and `save_step_log` used in [server.py](server.py#L521).

3. Outputs
 - Human-readable diagnostic questions (via SSE `need_help`), corrective plan suggestions, or bug reports.

4. Decision criteria
 - Trigger when `ContextOwner.is_stuck` returns True or when repeated retries exceed thresholds.
 - Evidence: `is_stuck, stuck_reason = context_owner.is_stuck(step, tool_result)` in [server.py](server.py#L494).

5. Required agents
 - Debug agent that can gather context, propose patches (via `StepsPlanner.refine_plan`), and run diagnostic commands.

6. Required tools
 - Access to `steps_log.json`, `ContextOwner.generate_help_question` (existing), and `long_term_memory`.

7. Required prompts
 - Diagnostic prompt templates (already used by `generate_help_question` in [context_owner.py](context_owner.py#L1)).

8. State transitions
 - Failed step -> is_stuck -> generate_help_question -> await user -> apply user choice (retry, provide path, stop).

9. Failure handling
 - If user chooses retry, run `StepsPlanner.refine_plan` and resume execution; else abort and persist failure.

10. Retry handling
 - Controlled by `max_retries_per_step` and `ContextOwner.get_failure_count_for_step`.

11. Cost considerations
 - Low; use LLM only for explanation generation when needed.

12. Performance considerations
 - Debugging is interactive — use SSE to keep the user informed.

13. Security considerations
 - When presenting file contents or commands, redact secrets and avoid exposing system internals unnecessarily.

14. Integration points
 - Integrated already in `/stream`; refactor to `routes/debug_route.py` and call from `task_router` when `is_stuck`.

15. Required code modifications
 - Extract `ContextOwner.generate_help_question` usage into `routes/debug_route.py` and implement a small UI endpoint for user choices (already partially implemented by `/ask_user`).

Traceability: Stuck detection and help generation in [context_owner.py](context_owner.py#L1) and the `/stream` handling of `need_help` in [server.py](server.py#L498-L506).

