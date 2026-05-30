from typing import List, Dict, Any
import py_compile
import os


def review_execution(execution_log: List[Dict[str, Any]], executor=None) -> Dict[str, Any]:
    """Run simple reviewer checks against the execution log.

    - Syntax-check any created `.py` files using `py_compile`.
    - If `executor` is provided and any test steps were executed, collect their
      output from the execution log.
    Returns a structured result describing passed/failed checks.
    """
    result = {"syntax": [], "tests": [], "summary": {"syntax_ok": True, "tests_ok": True}}

    for entry in execution_log:
        step = entry.get("step", {})
        res = entry.get("result", "")
        if step.get("tool") == "write_file":
            path = step.get("arguments", {}).get("path")
            if path and path.endswith(".py") and os.path.exists(path):
                try:
                    py_compile.compile(path, doraise=True)
                    result["syntax"].append({"path": path, "ok": True})
                except Exception as e:
                    result["syntax"].append({"path": path, "ok": False, "error": str(e)})
                    result["summary"]["syntax_ok"] = False

        if step.get("tool") == "execute_command":
            cmd = step.get("arguments", {}).get("command")
            # If this was a pytest run, inspect result for failures
            if cmd and "pytest" in cmd:
                output = res or ""
                failed = "FAILED" in output.upper() or "ERROR" in output.upper()
                result["tests"].append({"command": cmd, "output": output, "ok": not failed})
                if failed:
                    result["summary"]["tests_ok"] = False

    return result
