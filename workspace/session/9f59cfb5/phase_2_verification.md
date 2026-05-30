# Phase 2 Verification — Task Router + Routes Skeleton

This document contains executable, non-developer verification steps for Phase 2 (Add Task Router and routes skeleton).

Requirement 1: Add `task_router.py` that groups plan steps into route segments
1. Test objective: Confirm `task_router.route_plan(plan)` groups contiguous steps by route.
2. Steps:
   - Open `task_router.py` and inspect `route_plan` implementation.
   - Run a small script:

```bash
python -c "from task_router import route_plan; print(route_plan({'steps':[{'step_number':1,'tool':'read_file'},{'step_number':2,'tool':'write_file'},{'step_number':3,'tool':'execute_command'}]}))"
```
3. Input: None.
4. Expected output: JSON-like structure with `segments` grouping `read_file` as `knowledge`, `write_file` as `development`, and `execute_command` as `automation`.
5. Failure indicators: function missing or segments incorrect.

Requirement 2: Add `routes/` skeleton modules with `handle_segment` functions
1. Test objective: Confirm each route module exists and exposes `handle_segment(segment, session_context, executor=None)`.
2. Steps:
   - List files under `routes/` and open each file to locate `handle_segment`.
   - Run a quick Python import check:

```bash
python -c "import routes.chat_route as c; import routes.development_route as d; print(callable(c.handle_segment), callable(d.handle_segment))"
```

3. Input: None.
4. Expected output: `True True` printed and no import errors.
5. Failure indicators: Import errors or missing functions.

Requirement 3: Ensure skeletons are non-destructive and require an explicit executor to run actions
1. Test objective: Confirm `development_route.handle_segment` and `automation_route.handle_segment` return planned steps when `executor` is not provided, and execute only when `executor` is provided.
2. Steps:
   - Run a small test:

```bash
python - <<'PY'
from routes.development_route import handle_segment
seg = {'steps':[{'step_number':1,'tool':'write_file','arguments':{'path':'tmp.txt','content':'x'}}]}
print(handle_segment(seg, {'user_prompt':'Create file'}, executor=None))
PY
```

3. Expected output: dict with `planned_steps` key and no file writes.
4. Failure indicators: File `tmp.txt` created or unexpected side-effects.

Requirement 4: Add `phase_2_verification.md` to workspace session folder (this file)
1. Test objective: Present human-executable tests for Phase 2.
2. Steps: Open this file and follow the tests above.
3. Expected output: This file exists and is readable.

---

If all checks pass, Phase 2 skeletons are implemented correctly.

*** End of Phase 2 Verification ***