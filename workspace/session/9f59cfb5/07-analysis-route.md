## Analysis Route — Implementation Document

1. Purpose
 - Run verification, hypothesis testing, root-cause analysis, and generate corrective plans based on observed execution traces.

2. Inputs
 - Execution logs (`steps_log.json` / `execution_log` assembled in `/stream`).
 - `user_prompt`, `plan`, and `tool_results` from runtime.
 - Evidence: `execution_log` built and saved using `save_step_log` inside [server.py](server.py#L521) and `steps_log.json` contents.

3. Outputs
 - Analysis report, correction plan (JSON), or escalation to Research/Debug routes.

4. Decision criteria
 - Trigger when `SmartThinking.verify_step` returns `False` repeatedly or `ContextOwner.is_stuck` returns True.
 - Evidence: `is_stuck = context_owner.is_stuck(step, tool_result)` in [server.py](server.py#L500).

5. Required agents
 - Analysis agent (refactor `smartThinking.final_verification` to be callable as a service that returns structured JSON reliably).

6. Required tools
 - Access to `steps_log.json`, `ContextOwner` registries, and `LongTermMemory` for historical context.

7. Required prompts
 - Diagnostic prompt templates used by `SmartThinking.final_verification` (already present; returns structured JSON according to code).
 - Evidence: `final_verification` includes instructions for JSON output in [smartThinking.py](smartThinking.py#L1).

8. State transitions
 - Entry: failed step or explicit Analysis request -> run verifier -> produce correction_plan -> return plan to Task Router.

9. Failure handling
 - If analysis fails to produce a valid repair, mark as `Evidence Not Found` and route to human review (await user input via `need_help`).

10. Retry handling
 - Allow analysis to propose a correction plan; Task Router can execute correction plan with the same execution-verification loop.

11. Cost considerations
 - Analysis uses larger LLM prompts; restrict to when automated retries fail.

12. Performance considerations
 - Analysis may be asynchronous — run in background and notify user via SSE when ready.

13. Security considerations
 - Do not include system secrets in analysis outputs. Sanitize file contents.

14. Integration points
 - `server.py` already calls `smart.final_verification` after plan execution and may run correction plan steps; extract that logic into `routes/analysis_route.py` and call from `task_router`.

15. Required code modifications
 - Refactor `smartThinking.final_verification` into `routes/analysis_route.py` API and call it from `server.py` via `task_router`.

Traceability: Analysis capabilities are present in `smartThinking.py` and invoked in `server.py` after execution (`final_check = smart.final_verification(...)` in [server.py](server.py#L584)).

