import subprocess
import shlex
from typing import Dict, Any
import threading
import uuid

# Store active terminal sessions
active_terminals: Dict[str, subprocess.Popen] = {}

def start_interactive_terminal(cwd: str = None) -> str:
    """Starts a persistent CMD process and returns the session ID."""
    session_id = str(uuid.uuid4())[:8]
    
    # Windows-specific flags to create a new console process group
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    
    process = subprocess.Popen(
        ['cmd.exe'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        creationflags=creationflags,
        shell=False,
        text=True
    )
    active_terminals[session_id] = process
    return session_id, process

def write_to_terminal(session_id: str, user_input: str):
    """Sends keystrokes to the active terminal's stdin."""
    process = active_terminals.get(session_id)
    if process and process.poll() is None:
        process.stdin.write(user_input)
        process.stdin.flush()

def close_terminal(session_id: str):
    """Terminates the terminal process."""
    process = active_terminals.pop(session_id, None)
    if process:
        process.terminate()


def run_sandboxed_command(command: str, timeout_seconds: int = 30, cwd: str = None, dry_run: bool = False) -> str:
    """Execute a command in a constrained sandbox runner.

    This runner intentionally avoids shell=True, rejects common destructive
    patterns, and supports a `dry_run` mode returning what would be executed.
    Returns: output string or error message.
    """
    if not command or not command.strip():
        return "Error: empty command"

    cmd = command.strip()

    # Reject obvious destructive patterns
    destructive = ['rm -rf', 'mkfs', 'dd if=', ':(){', 'shutdown', 'reboot', '>:']
    low = cmd.lower()
    for p in destructive:
        if p in low:
            return f"Error: command denied by sandbox (pattern: {p})"

    if dry_run:
        return f"DRY_RUN: would execute: {cmd}"

    # Tokenize and run without invoking the shell
    try:
        args = shlex.split(cmd)
    except Exception as e:
        return f"Error: failed to parse command: {e}"

    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout_seconds, shell=False)
        output = result.stdout or ""
        if result.stderr:
            output += f"\n[STDERR]: {result.stderr}"
        if result.returncode != 0:
            output += f"\n[Exit {result.returncode}]"
        return output.strip() or "[No output]"
    except subprocess.TimeoutExpired:
        return "Error: Command timeout"
    except FileNotFoundError:
        return "Error: command not found"
    except Exception as e:
        return f"Error: {e}"


def sandbox_executor(tool_name: str, arguments: Dict[str, Any], scope_mgr=None) -> str:
    """Convenience executor used by route handlers: currently only supports execute_command."""
    if tool_name == 'execute_command':
        cmd = arguments.get('command', '')
        timeout = arguments.get('timeout_seconds', 30)
        dry_run = arguments.get('dry_run', False)
        return run_sandboxed_command(cmd, timeout_seconds=timeout, dry_run=dry_run)

    # Fallback: indicate unsupported tool for sandboxed executor
    return f"Error: sandbox_executor does not support tool '{tool_name}'"
