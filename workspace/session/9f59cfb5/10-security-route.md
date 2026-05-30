## Security Route — Implementation Document

1. Purpose
 - Enforce access control, sandbox dynamic tools, audit actions, and mediate any operation that touches the host system.

2. Inputs
 - Any plan step that performs I/O (`write_file`, `read_file`, `execute_command`) or dynamic tool registration.
 - Evidence: `execute_tool_backend` checks `scope_mgr.is_path_allowed(path)` for file ops in [server.py](server.py#L277).

3. Outputs
 - Authorization decisions, sanitized execution requests, audit logs, and alerts when policy violations occur.

4. Decision criteria
 - Deny operations outside `ScopeManager.current_scope` or in `forbidden_directories`; require elevation for sensitive actions.

5. Required agents
 - Security agent / policy engine that can evaluate commands and tool code before execution.

6. Required tools
 - Hardened `dynamic_tool_loader` (remove `exec()` or sandbox it), authorization wrapper for `execute_tool_backend`.
	- Evidence: `exec(sample_code, namespace)` used in [dynamic_tool_loader.py](dynamic_tool_loader.py#L1) — high risk.

7. Required prompts
 - Policy-check prompts to LLM (if using LLM for heuristic checks) and deterministic rule checks in code.

8. State transitions
 - Request -> Security check -> allow/deny -> routed to execution or returned with `Evidence Not Found` or `access denied`.

9. Failure handling
 - On policy failure, return explicit denial message and log event to `steps_log.json`.

10. Retry handling
 - No automatic retries for denied operations; require human approval or reclassification.

11. Cost considerations
 - Sandboxing and runtime isolation may require containers or VMs (infra cost).

12. Performance considerations
 - Policy checks should be fast; use cached decisions for repeated operations.

13. Security considerations
 - Immediate: stop `exec()` of untrusted code, require reviewers for new tools, add signatures/hashes for approved tools in `tools_registry.json`.

14. Integration points
 - Wrap `current_tools` registry access in an authorization layer; modify `create_agent` to only register vetted dynamic tools.

15. Required code modifications
 - Implement `routes/security_route.py` and `security/validator.py`.
 - Replace `exec(sample_code, namespace)` in [dynamic_tool_loader.py](dynamic_tool_loader.py#L1) with a safe loader that validates and signs code or compiles to a restricted runtime.

Traceability: Current risky behavior is in [dynamic_tool_loader.py](dynamic_tool_loader.py#L1) and `execute_command` shell usage in [server.py](server.py#L139). Basic scoping exists in [scope_manager.py](scope_manager.py#L1).

