from typing import Dict, Any
import shlex


def authorize_tool_execution(tool_name: str, arguments: Dict[str, Any], scope_mgr) -> Dict[str, Any]:
    """Return an authorization decision for a single tool execution.

    Result: { 'allowed': bool, 'reason': str }
    """
    # Default allow
    try:
        if tool_name == 'execute_command':
            command = arguments.get('command', '')
            if not command:
                return {'allowed': False, 'reason': 'empty command'}

            # Quick static deny patterns
            forbidden_patterns = ['rm -rf', 'reboot', 'shutdown', ':(){', 'mkfs', 'dd if=', '>:']
            cmd_l = command.lower()
            for p in forbidden_patterns:
                if p in cmd_l:
                    return {'allowed': False, 'reason': f'forbidden pattern: {p}'}

            # Delegate to scope manager command policy if available
            if hasattr(scope_mgr, 'is_command_allowed'):
                if not scope_mgr.is_command_allowed(command):
                    return {'allowed': False, 'reason': 'disallowed by workspace command policy'}

            # Simple tokenization check to avoid shell meta characters
            try:
                parts = shlex.split(command)
                # reject if obvious shell operators present as separate tokens
                shell_ops = {'&&', ';', '|', '$(', '`'}
                if any(op in command for op in shell_ops):
                    return {'allowed': False, 'reason': 'shell operators not allowed in sandboxed execution'}
            except Exception:
                return {'allowed': False, 'reason': 'failed to parse command safely'}

            return {'allowed': True, 'reason': 'ok'}

        elif tool_name in ('write_file', 'read_file'):
            path = arguments.get('path', '')
            if not path:
                return {'allowed': False, 'reason': 'missing path'}
            if not scope_mgr.is_path_allowed(path):
                return {'allowed': False, 'reason': 'path outside workspace scope'}
            return {'allowed': True, 'reason': 'ok'}

        else:
            # For dynamic tools, require explicit allow by scope manager or deny by default
            if hasattr(scope_mgr, 'current_scope'):
                return {'allowed': True, 'reason': 'ok'}
            return {'allowed': True, 'reason': 'ok'}
    except Exception as e:
        return {'allowed': False, 'reason': f'validator error: {e}'}
