## Automation Route — Implementation Document

1. Purpose
 - Safely execute system-level automation tasks (commands, filesystem operations, scheduled jobs) under policy and scope constraints.

2. Inputs
 - `user_prompt` mapped by classifier or planner into `execute_command` / `write_file` steps.
 - Evidence: `execute_command_tool` and `execute_tool_backend` paths in [server.py](server.py#L120, server.py#L272).

3. Outputs
 - Command outputs, execution logs, and success/failure events streamed via SSE (`step_result`).

4. Decision criteria
 - If plan steps include `execute_command` or automation-specific dynamic tools, route to Automation.

5. Required agents
 - Automation agent that enforces policy, runs sandboxed commands, supports dry-run and rollback.

6. Required tools
 - `execute_command` (existing), improved sandbox/wrapper, optional containerized runner.

7. Required prompts
 - Safety policy prompts for the automation agent to validate commands before execution.

8. State transitions
 - Validate command -> run in sandbox -> verify with `SmartThinking.verify_step` -> commit or rollback.

9. Failure handling
 - Retry up to `max_retries_per_step` (existing default=3) then escalate to `need_help` or create correction plan.
	- Evidence: retry and refine logic in [server.py](server.py#L486-L502).

10. Retry handling
 - Use planner.refine_plan to adjust commands; expose `dry_run` mode to the user.

11. Cost considerations
 - Running commands is cheap but sandboxing and orchestration add infra cost.

12. Performance considerations
 - Long-running commands should be executed asynchronously with progress updates (SSE is suitable).

13. Security considerations
 - `execute_command` currently accepts arbitrary commands; must add strict sanitization and run in constrained environment. Also avoid shell=True usage where possible.
	- Evidence: `subprocess.run(..., shell=True)` used conditionally in [server.py](server.py#L139).

14. Integration points
 - Replace direct `execute_tool_backend` invocation in `server.py` with `task_router` calling `automation_route.execute(...)`.

15. Required code modifications
 - Implement `routes/automation_route.py`, add a sandboxed runner, and enhance `scope_manager` with command policies and whitelists.

Traceability: Execution logic and retries are in [server.py](server.py#L456-L506), and `execute_command_tool` is defined in [server.py](server.py#L120).

