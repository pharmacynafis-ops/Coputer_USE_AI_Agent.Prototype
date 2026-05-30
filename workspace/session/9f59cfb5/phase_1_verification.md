# Phase 1 Verification — Current State Audit

This document contains executable, non-developer verification steps for the Phase 1 (Current State Audit) deliverables. Each test maps to a single requirement extracted from the approved documents.

Requirement 1: Identify Request entry points
1. Test objective: Confirm the system documents HTTP routes and SSE entry points.
2. Steps:
   - Open the file workspace/session/9f59cfb5/01-current-state-audit.md and locate the section listing `server.py` routes.
3. Input: None (read-only).
4. Expected output: The audit file lists `/stream`, `/api/set_scope`, `/api/save_new_tool`, `/api/steps_log`, `/api/memory_search`, `/api/set_api_key`.
5. Failure indicators: Any of the listed routes missing from the audit.

Requirement 2: Document Chat flow
1. Test objective: Confirm the audit documents the `/stream` chat flow and the quick-reply fallback.
2. Steps:
   - Read workspace/session/9f59cfb5/01-current-state-audit.md and find the `/stream` behavior section describing `should_skip_thinking` and `smart.quick_reply`.
3. Input: None.
4. Expected output: Audit contains bullet about `SmartThinking.should_skip_thinking` invocation and fallback to `smart.quick_reply` when plan total_steps == 0.
5. Failure indicators: No mention of `should_skip_thinking` or `quick_reply` in the audit.

Requirement 3: Document Agent flow
1. Test objective: Confirm `create_agent` and agent tool registration are documented.
2. Steps:
   - Open workspace/session/9f59cfb5/01-current-state-audit.md and find `create_agent(api_key=None)` and tool registration evidence.
3. Input: None.
4. Expected output: Audit mentions `create_agent`, registration of `write_file`, `read_file`, `execute_command`, `redirect_to_scope_page`, `create_new_customization_tool`, and dynamic tools load.
5. Failure indicators: Missing `create_agent` or missing list of core tools.

Requirement 4: Document Tool execution flow
1. Test objective: Confirm `execute_tool_backend` behavior and scope checks are recorded.
2. Steps:
   - Read the audit file and confirm there is an entry for `execute_tool_backend` describing `scope_mgr.is_path_allowed` checks.
3. Input: None.
4. Expected output: Audit documents `execute_tool_backend` branching and scope enforcement.
5. Failure indicators: `execute_tool_backend` not mentioned.

Requirement 5: Document Memory flow
1. Test objective: Confirm `LongTermMemory` and `ContextOwner` responsibilities are documented.
2. Steps:
   - Read the audit file and find sections for `long_term_memory.py` and `context_owner.py` describing `get_context_for_prompt`, `add_file_record`, `start_session`, etc.
3. Input: None.
4. Expected output: Audit contains entries for `LongTermMemory` methods and `ContextOwner` methods.
5. Failure indicators: Missing `LongTermMemory` or `ContextOwner` entries.

Requirement 6: Document Session flow
1. Test objective: Confirm session start/resume and conversation persistence are documented.
2. Steps:
   - Read the `/stream` and `context_owner` parts of the audit to find `start_session`, `resume_session`, and `save_conversation_to_session` references.
3. Input: None.
4. Expected output: Audit references session start and persistence.
5. Failure indicators: No session handling described.

Requirement 7: Document Workspace flow (scope manager)
1. Test objective: Confirm `ScopeManager` and `is_path_allowed` behavior is recorded.
2. Steps:
   - Read the audit file and find `scope_manager.py` section.
3. Expected output: Audit references default workspace path, `establish_scope`, and `is_path_allowed`.
4. Failure indicators: Missing `ScopeManager` mention.

Requirement 8: Document Prompt generation and Planning flow
1. Test objective: Confirm `enhanced_prompt` composition and `StepsPlanner.create_plan` usage are documented.
2. Steps:
   - Read the `/stream` section showing `historical_context`, `conversation_context`, `enhanced_prompt`, and the call to `StepsPlanner.create_plan`.
3. Expected output: Audit documents the prompt assembly and plan creation.
4. Failure indicators: Absent references to planner or enhanced prompt.

Requirement 9: Document Development flow and dynamic tools
1. Test objective: Confirm `dynamic_tool_loader`, `tools_registry.json`, and `ToolCreator` are recorded.
2. Steps:
   - Read the audit entries for `dynamic_tool_loader.py`, `tools_registry.json`, and `add_new_tool.py`.
3. Expected output: Audit mentions sample_code `exec()` and dynamic tool registration.
4. Failure indicators: Missing dynamic tool evidence.

Requirement 10: Document existing routing, classification, orchestration, automation, debugging, research, and security logic
1. Test objective: Verify each area is present in the audit (routing in `/stream`, classification in `SmartThinking.should_skip_thinking`, orchestration loop, `execute_command` automation logic, `ContextOwner.is_stuck` debugging, LLM-research notes, and `ScopeManager` security).
2. Steps:
   - Scan workspace/session/9f59cfb5/01-current-state-audit.md for the mentioned keywords and sections.
3. Expected output: Audit contains entries covering these items (see the Observed flows and `/stream` details).
4. Failure indicators: Any major area omitted.

---

If all checks pass, the Phase 1 audit is confirmed.

*** End of Phase 1 Verification ***

---

## Phase 1 Execution — Request Classifier Verification

This section provides non-developer, executable verification steps for the Phase 1 implementation (Request Classifier).

Requirement: Add `request_classifier.py` and wire it into `/stream` to log classifications to `steps_log.json`.

1. Test objective: Verify the classifier runs, returns a category and confidence, and that the server logs the classification.
2. Steps:
   - Open a terminal in the repository root (where `server.py` lives).
   - Run the unit test script for the classifier:

```bash
python tests/test_request_classifier.py
```

   - Run the integration test that persists a classification to `steps_log.json`:

```bash
python tests/test_integration_classification_logging.py
```

   - Alternatively, start the server and send a simple prompt via the browser or curl to `/stream?prompt=Create a new file` and then inspect `steps_log.json` for a recent entry of type `classification`.

3. Input: No developer tools required; run the commands above.
4. Expected output:
   - Unit test prints `RequestClassifier basic tests passed`.
   - Integration test prints `Integration logging test passed` and `steps_log.json` contains a final entry where `type` equals `classification` and has `classification` object with `category` and `confidence`.
5. Failure indicators:
   - Tests raise exceptions or the Python scripts fail to run.
   - `steps_log.json` does not exist or last entry is not of type `classification`.

Notes:
- If the classifier is not enabled, ensure the environment variable `ENABLE_REQUEST_CLASSIFIER` is set to `1` before starting the server.
- To revert the change, remove `request_classifier.py` and the added logging line from `server.py`.

