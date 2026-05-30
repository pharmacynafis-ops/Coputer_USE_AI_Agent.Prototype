# automation/validator.py
import re

# Windows-specific destructive patterns that an AI agent should NEVER run
FORBIDDEN_PATTERNS = [
    r'\bformat\s+[a-zA-Z]:', # Formatting drives
    r'\bdel\s+/[sS]',        # Deleting recursively
    r'\brmdir\s+/[sS]',      # Removing directories recursively
    r'\breg\s+(add|delete)', # Modifying Windows registry
    r'\bnet\s+(user|localgroup)', # Modifying users/groups
    r'\bshutdown\b',         # Shutting down
    r'\breboot\b',           # Rebooting
    r'\btaskkill\s+/[fF]',   # Force killing critical tasks
    r'\bcd\s+[a-zA-Z]:\\',   # Changing drive roots (agent should stay in workspace)
    r'&{2}|;|\|',            # Shell chaining operators (&&, ;, |)
]

def validate_terminal_input(user_input: str) -> dict:
    """Validates agent input for the interactive terminal.
    Returns: {'allowed': bool, 'reason': str}"""
    
    if not user_input or not user_input.strip():
        return {'allowed': True, 'reason': 'Empty/whitespace allowed'}

    input_lower = user_input.lower().strip()
    
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, input_lower):
            return {'allowed': False, 'reason': f'Forbidden Windows pattern matched: {pattern}'}
            
    return {'allowed': True, 'reason': 'Input is safe'}
