# Phase 4 Verification (HUMAN TESTING)

Phase: 4 — Harden Automation and Security

For each implemented requirement below follow the steps exactly. These steps are designed for a non-developer operator with access to the running server.

1) Verify authorization denies forbidden commands
- Test objective: Confirm sandbox/validator blocks destructive commands and records an audit entry.
- Steps:
  1. Start the server (if not running): `python server.py` (run from project root).
  2. Send a request that will execute a destructive command via the streaming API or via a tool runner that calls `execute_command` (for example: `rm -rf /` or `reboot`).
     - If using curl to hit `/stream`, craft a prompt that instructs the agent to run a forbidden command.
  3. Observe the assistant SSE output.
- Input: Prompt asking to run `rm -rf /` (or `reboot`).
- Expected output: The step result should report an error with `Access denied by security policy` and the forbidden reason.
- Failure indicators: Command executes on host, or no entry appears in `steps_log.json` with `type: security_denial`.

2) Verify sandboxed execution for allowed commands
- Test objective: Confirm allowed commands run through sandbox and return expected output.
- Steps:
  1. From the server host, issue a prompt that runs a harmless command, e.g., `echo hello` or `dir`/`ls` inside workspace.
  2. Observe SSE `step_result` showing command output.
- Input: Prompt asking to run `echo hello`.
- Expected output: `step_result` contains `hello` and no security denial.
- Failure indicators: Command denied unexpectedly, or command output missing/stderr present unexpectedly.

3) Verify dry-run behavior
- Test objective: Confirm `dry_run` argument returns `DRY_RUN` response and does not execute.
- Steps:
  1. Trigger an `execute_command` step with arguments including `{"command": "rm -rf /tmp/somefile", "dry_run": true}` via a plan or direct API call.
  2. Check SSE for `DRY_RUN: would execute:` message.
- Input: execute_command with `dry_run: true`.
- Expected output: Response starts with `DRY_RUN: would execute:` and no changes on filesystem.
- Failure indicators: Filesystem modified or no dry-run indicator.

4) Verify command policy enforcement in scope
- Test objective: Confirm per-workspace command allow-list and deny-list are respected.
- Steps:
  1. Call `/api/set_scope` and set `forbidden_commands` to include `shutdown` and `allowed_commands` empty.
  2. Attempt to run `shutdown -h now` via the agent.
  3. Check that the command is denied and logged.
- Input: scope payload with `forbidden_commands: "shutdown"` and prompt to run `shutdown`.
- Expected output: `Access denied by security policy (disallowed by workspace command policy)` and a `security_denial` entry in `steps_log.json`.
- Failure indicators: Command runs or no audit log.

5) Verify read/write path checks still enforced
- Test objective: Confirm `read_file`/`write_file` operations outside the workspace are denied.
- Steps:
  1. Attempt to read or write a file outside the established workspace path (e.g., `C:\Windows\system32\test.txt`).
  2. Observe `step_result` reporting `Access denied`.
- Input: write_file path outside workspace.
- Expected output: `Error: Access denied. Path '...' is outside your workspace scope.`
- Failure indicators: File written outside workspace.

6) Confirm rollback/fallback behavior exists
- Test objective: Ensure sandbox executor failure falls back to prior executor and does not crash the server.
- Steps:
  1. Intentionally cause sandbox_executor to raise by sending a malformed command that passes authorization but fails parsing.
  2. Verify the server returns a helpful error and remains responsive.
- Input: malformed command or cause sandbox to error.
- Expected output: Error message and server continues to accept new prompts; no unhandled exceptions in console.
- Failure indicators: Server crashes or becomes unresponsive.

Notes for tester:
- `steps_log.json` is the canonical audit log. Open it after each test and look for `security_denial` entries and normal `step` records.
- If you need guidance crafting prompts that trigger `execute_command`, use simple instructions like: "Run the command `echo hello` and report the output." The planner produces `execute_command` steps accordingly.

If any test fails, collect `steps_log.json` and server console output and escalate to the security engineering team for post-mortem.
