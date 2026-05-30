from typing import Dict, List, Any


def decompose_segment(segment: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert a high-level development segment into atomic steps.

    Rules applied:
    - Preserve `write_file` steps as-is (one per target file).
    - If a step contains `run_tests: true` or any test command hint, append an
      `execute_command` step to run tests (`python -m pytest -q`).
    - Ensure the returned list is a plain list of step dicts.
    """
    steps: List[Dict[str, Any]] = []
    original = segment.get("steps", [])
    for s in original:
        tool = s.get("tool")
        args = s.get("arguments", {})
        # Keep write_file and read_file steps
        if tool in ("write_file", "read_file", "execute_command"):
            steps.append(s)

            # If the step requests tests afterwards, add a test step
            if args.get("run_tests") or args.get("path", "").endswith("_test.py"):
                steps.append({
                    "tool": "execute_command",
                    "arguments": {"command": "python -m pytest -q", "timeout_seconds": 60}
                })

        else:
            # Unknown tools are preserved to avoid losing intent
            steps.append(s)

    return steps
