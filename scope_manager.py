# scope_manager.py
import os
import json
import platform
from typing import Dict, Optional, List
from datetime import datetime

class WorkspaceScope:
    def __init__(self, workspace_path: str, allowed_dirs: List[str], forbidden_dirs: List[str], mode: str = "normal"):
        self.workspace_path = workspace_path
        self.allowed_directories = allowed_dirs
        self.forbidden_directories = forbidden_dirs
        self.creation_mode = mode  # "normal", "safe", "strict"
        self.established_at = datetime.now().isoformat()
        # Command policies (Phase 4): optional lists to control automation
        self.allowed_commands: List[str] = []
        self.forbidden_commands: List[str] = []

    def to_dict(self):
        return {
            "workspace_path": self.workspace_path,
            "allowed_directories": self.allowed_directories,
            "forbidden_directories": self.forbidden_directories,
            "creation_mode": self.creation_mode,
            "established_at": self.established_at
        }

class ScopeManager:
    def __init__(self, long_term_memory):
        self.ltm = long_term_memory
        # Initialize with a default workspace path in the user's home directory
        
        # Get the current user name
        username = os.getlogin() if hasattr(os, 'getlogin') else os.path.expanduser('~').split(os.sep)[-1]
        
        # Create a default workspace path based on the operating system
        if platform.system() == 'Windows':
            default_workspace = f"C:\\Users\\{username}\\computer_use_source"
        elif platform.system() == 'Darwin':  # macOS
            default_workspace = f"/Users/{username}/computer_use_source"
        else:  # Linux and other Unix-like systems
            default_workspace = f"/home/{username}/computer_use_source"
        
        # Ensure the directory exists
        os.makedirs(default_workspace, exist_ok=True)
        
        # Set the default scope
        self.current_scope: Optional[WorkspaceScope] = WorkspaceScope(
            workspace_path=default_workspace,
            allowed_dirs=["*"],
            forbidden_dirs=[],
            mode="normal"
        )

    def has_valid_scope(self, user_prompt: str) -> bool:
        # If we already have a scope (default or user-defined), return True
        if self.current_scope:
            # Verify the workspace path still exists
            if os.path.exists(self.current_scope.workspace_path):
                return True
            else:
                # If the workspace no longer exists, reset to default
                self._reset_to_default_scope()
                return True

        # If no scope is set, try to restore from last saved scope
        last_scope_data = self.ltm.user_profile.get("last_workspace_scope")
        if last_scope_data:
            workspace_path = last_scope_data.get("workspace_path", "")
            if os.path.exists(workspace_path):
                allowed = last_scope_data.get("allowed_directories", ["*"])
                forbidden = last_scope_data.get("forbidden_directories", [])
                mode = last_scope_data.get("creation_mode", "safe")
                self.current_scope = WorkspaceScope(workspace_path, allowed, forbidden, mode)
                return True

        greetings = ["مرحباً", "السلام", "كيف حالك", "what is your name", "hello", "hi", "how are you"]
        if any(greeting in user_prompt.lower() for greeting in greetings):
            return True

        if "إنشاء ملف" in user_prompt or "create file" in user_prompt.lower() or "mkdir" in user_prompt.lower():
            return False

        return False

    def request_scope_from_user(self, user_prompt: str) -> dict:
        return {
            "needs_scope": True,
            "user_prompt": user_prompt,
            "questions": [
                "ما هو المجلد الرئيسي الذي تريد العمل فيه؟ (مثال: C:\\my_workspace)",
                "هل تسمح لي بإنشاء ملفات في أي مجلد فرعي داخل هذا المجلد؟ (نعم/لا)",
                "هل هناك مجلدات ممنوع الاقتراب منها؟ (مثال: C:\\Windows, C:\\Program Files)"
            ]
        }

    def _reset_to_default_scope(self):
        """Reset to a default workspace when the current one no longer exists"""
        # Get the current user name
        username = os.getlogin() if hasattr(os, 'getlogin') else os.path.expanduser('~').split(os.sep)[-1]
        
        # Create a default workspace path based on the operating system
        if platform.system() == 'Windows':
            default_workspace = f"C:\\Users\\{username}\\computer_use_source"
        elif platform.system() == 'Darwin':  # macOS
            default_workspace = f"/Users/{username}/computer_use_source"
        else:  # Linux and other Unix-like systems
            default_workspace = f"/home/{username}/computer_use_source"
        
        # Ensure the directory exists
        os.makedirs(default_workspace, exist_ok=True)
        
        # Set the default scope
        self.current_scope = WorkspaceScope(
            workspace_path=default_workspace,
            allowed_dirs=["*"],
            forbidden_dirs=[],
            mode="normal"
        )
        
        # Save the default scope to user profile
        self.ltm.user_profile["last_workspace_scope"] = self.current_scope.to_dict()
        self.ltm._save_user_profile()

    def establish_scope(self, answers: dict) -> WorkspaceScope:
        workspace_path = answers.get("workspace_path")
        if not workspace_path or not workspace_path.strip():
            workspace_path = os.getcwd()

        allow_subdirs = answers.get("allow_subdirs", True)
        allowed = ["*"] if allow_subdirs else [workspace_path]

        forbidden_raw = answers.get("forbidden_dirs", [])
        if isinstance(forbidden_raw, str):
            forbidden = [d.strip() for d in forbidden_raw.split(",") if d.strip()]
        else:
            forbidden = forbidden_raw if isinstance(forbidden_raw, list) else []

        mode = "safe" if answers.get("safe_mode", True) else "normal"

        scope = WorkspaceScope(workspace_path, allowed, forbidden, mode)

        # Optional command policies
        allowed_cmds = answers.get("allowed_commands", [])
        forbidden_cmds = answers.get("forbidden_commands", [])
        if isinstance(allowed_cmds, str):
            allowed_cmds = [c.strip() for c in allowed_cmds.split(",") if c.strip()]
        if isinstance(forbidden_cmds, str):
            forbidden_cmds = [c.strip() for c in forbidden_cmds.split(",") if c.strip()]
        scope.allowed_commands = allowed_cmds
        scope.forbidden_commands = forbidden_cmds

        self.ltm.user_profile["last_workspace_scope"] = scope.to_dict()
        self.ltm._save_user_profile()

        self.current_scope = scope
        return scope

    def is_command_allowed(self, command: str) -> bool:
        """Simple policy check for commands. Returns False when command matches a forbidden pattern
        or does not match an allow-list when one is configured.
        """
        if not self.current_scope:
            return False

        cmd = command.strip().lower()

        # Check forbidden patterns first
        for pat in getattr(self.current_scope, 'forbidden_commands', []) or []:
            if not pat:
                continue
            if pat.lower() in cmd:
                return False

        allowed = getattr(self.current_scope, 'allowed_commands', []) or []
        # If an allow-list exists, require that one of the allowed patterns appears
        if allowed:
            for pat in allowed:
                if pat.lower() in cmd:
                    return True
            return False

        # Default allow if no explicit policies
        return True

    def is_path_allowed(self, path: str) -> bool:
        # If no scope is set, try to establish a default scope
        if not self.current_scope:
            self._reset_to_default_scope()
            
        # If still no scope (shouldn't happen with default), deny access
        if not self.current_scope:
            return False
            
        # Normalize paths for comparison
        normalized_path = os.path.normpath(path)
        normalized_workspace = os.path.normpath(self.current_scope.workspace_path)
        
        # Check if path is within the workspace
        if not normalized_path.startswith(normalized_workspace):
            return False
            
        # Check against forbidden directories
        for forbidden in self.current_scope.forbidden_directories:
            if forbidden:
                normalized_forbidden = os.path.normpath(forbidden)
                if normalized_path.startswith(normalized_forbidden):
                    return False
        
        return True