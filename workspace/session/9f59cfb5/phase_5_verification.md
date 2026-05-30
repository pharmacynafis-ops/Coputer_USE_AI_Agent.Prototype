# Phase 5 — Development Route Verification

This document provides human-executable verification steps for Phase 5 implemented components.

Requirement 1: `routes/development_route.py` orchestrates decomposer, builder, reviewer, evidence collection, and final verification.

1. Test objective: Verify the Development route executes a simple development task and produces final verification.
2. Steps:
   - Start the server: `python server.py` in the workspace root.
   - Use the agent (via UI or API) to request: "Create a Python file `tmp_hello.py` with function `hello()` that returns 'hello', and add a test `test_tmp_hello.py` asserting `hello()` returns 'hello'. Run tests." 
   - Alternatively, run a small script that simulates a plan containing `write_file` steps and an `execute_command` pytest step and call `routes/development_route.handle_segment(...)` via a small harness.
3. Input: The user prompt as above, or a plan/segment JSON with `write_file` steps for `tmp_hello.py` and `test_tmp_hello.py`, plus an `execute_command` step `python -m pytest -q`.
4. Expected output: `final_verification` object with `is_goal_achieved: true` and reviewer `tests` showing `ok: true`.
5. Failure indicators: Syntax errors in created files, pytest failures, or `final_verification.is_goal_achieved` false.

Requirement 2: `decomposer/simple_decomposer.py` produces atomic steps.

1. Test objective: Ensure a segment with write_file steps is returned unchanged and that `run_tests` hints produce an execute_command step.
2. Steps: Import `decomposer.simple_decomposer.decompose_segment` in a Python REPL, pass a segment with a write_file including `run_tests: true`, confirm returned list contains an `execute_command` step.

Requirement 3: `builders/runner.py` executes steps and creates backups for overwritten files.

1. Test objective: Confirm a `.bak` file is created when writing over an existing file.
2. Steps: Create a small file `existing.py`, run builder with a write_file step for `existing.py` changing content, check `existing.py.bak` exists.

Requirement 4: `reviewers/lint_and_test.py` performs syntax checks and reports test outputs.

1. Test objective: Check reviewer reports syntax_ok and tests_ok for the sample task.
2. Steps: After running the sample dev task above, inspect the `review` field returned by the route for `syntax` entries and `tests` entries with `ok: true`.

General failure handling:
- If any step fails, inspect `steps_log.json` and the execution log returned by the route to identify failing steps and outputs.
