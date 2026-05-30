## 13 — Implementation Roadmap

Goal: incrementally transform CompLoca into a routed multi-agent architecture with minimal risk and verifiable steps.

Principles:
- Small, reversible increments.
- Keep backward compatibility (feature-flagged refactors) until validated.
- Preserve existing SSE contract and user-visible events.

Phase 0 — Safety quick wins (preconditions)
- Goal: prevent most immediate security risks before large refactor.
- Files affected: `dynamic_tool_loader.py`, `server.py`.
- Actions:
	1. Disable auto-exec of dynamic `sample_code` by default: change `exec(sample_code, namespace)` to a safe-flag path or sandboxed loader. (Low risk)
	2. Add a configuration flag `ENABLE_DYNAMIC_TOOL_EXEC=0` read from env. (Low risk)
- Validation: repository no longer executes arbitrary code on agent startup. Tests: start server and ensure no `exec` runs for dynamic tools.
- Rollback: revert flag to re-enable behavior.

Phase 1 — Add Request Classifier (non-breaking)
- Goal: Add `request_classifier.py` and wire into `/stream` but keep old `should_skip_thinking` path behind a feature flag.
- Files affected: `request_classifier.py` (new), `server.py` (small injection near the top of `stream`).
- Risk: low; classifier can be heuristic-first.
- Validation: unit tests for heuristics; integration test: assert that classifier returns category/confidence and server logs it to `steps_log.json`.
- Rollback: remove call and use original `should_skip_thinking`.

Phase 2 — Add Task Router and routes skeleton (safe integration)
- Goal: Implement `task_router.py` and empty `routes/*` handlers that mirror current server behavior by delegating to existing logic.
- Files affected: `task_router.py`, `routes/__init__.py`, `routes/chat_route.py`, `routes/knowledge_route.py`, etc.
- Risk: medium (integration surface increases).
- Validation: Green-path: router invoked, but internal handlers call existing `StepsPlanner` + execution loop to produce identical SSE events.
- Rollback: feature-flag router invocation in `server.py`.

Phase 3 — Refactor `/stream` to use Task Router (safe switch)
- Goal: Replace inlined plan-execution with `task_router.route(...)` and stream events produced by route handlers.
- Files affected: `server.py`, `task_router.py`, `routes/*`.
- Risk: medium-high; preserve existing SSE event shapes exactly to avoid client breakage.
- Validation: compare SSE event sequences before/after using test harness with sample prompts; ensure JSON event types match.
- Rollback: revert to original loop if mismatch.

Phase 4 — Harden Automation and Security
- Goal: Add `routes/security_route.py` and `routes/automation_route.py` with sandboxed execution.
- Files affected: `scope_manager.py` (extend policy), `server.py` (authorization wrapper), `security/validator.py`, `automation/sandbox_runner.py`.
- Risk: high (security critical). Require review and controlled rollout.
- Validation: pen-tests, attempt to execute forbidden commands; audit logs appear in `steps_log.json`.
- Rollback: revert to previous executor but keep enhanced logging for post-mortem.

Phase 5 — Build Development route internals (decomposer, builder, reviewer)
- Goal: Implement `routes/development_route.py`, `decomposer/`, `builders/runner.py`, `reviewers/`.
- Files affected: as above plus `steps_planner.py` if stricter contract needed.
- Risk: medium.
- Validation: run a sample dev task (create file, run tests) and ensure `smart.final_verification` returns success.
- Rollback: disable automated builder and require manual approval.

Phase 6 — Analysis, Debug, Research agents and tooling
- Goal: Implement `routes/analysis_route.py`, `routes/debug_route.py`, `routes/research_route.py`, add connectors for external search if needed.
- Files affected: new routes and `long_term_memory.py` (index adapter if adding embeddings).
- Risk: medium.
- Validation: run failure scenarios and ensure analysis produces correction plans and debug prompts.
- Rollback: revert to manual debug flows.

Phase 7 — Production hardening & observability
- Goal: Add monitoring, metrics (counts of route usage, failure rates), RBAC policies, signed tools registry, and automated tests.
- Files affected: `server.py` (metrics hooks), `dynamic_tool_loader.py` (tool signature checks), `tools_registry.json` (signed metadata).
- Risk: medium-low.
- Validation: run integration tests, confirm metrics emitted and tools require signature to load.

Ordering notes:
- Steps are ordered by dependency: safety -> classifier -> router skeleton -> router switch -> security/hardening -> development internals -> analysis/debug/research -> production hardening.

Completion criteria (project-level):
- All routes exist as separate handlers and are reachable via `task_router`.
- No dynamic `exec()` of untrusted code in default configuration.
- SSE contract preserved and `smart.final_verification` used as Decision Engine across routes.

