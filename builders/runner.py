from typing import List, Dict, Any
import os
import shutil


def _backup_file(path: str) -> None:
    if os.path.exists(path):
        bak = path + ".bak"
        shutil.copy2(path, bak)


def run_steps(steps: List[Dict[str, Any]], executor) -> List[Dict[str, Any]]:
    """Execute a list of atomic steps using the provided `executor` callable.

    Each entry in the returned execution log contains: {step, result}
    """
    log: List[Dict[str, Any]] = []
    for step in steps:
        tool = step.get("tool")
        args = step.get("arguments", {})

        # For write_file, create a backup first
        if tool == "write_file":
            path = args.get("path")
            if path:
                try:
                    _backup_file(path)
                except Exception:
                    pass

        try:
            res = executor(tool, args)
        except Exception as e:
            res = f"Error: {e}"

        log.append({"step": step, "result": res})

    return log
