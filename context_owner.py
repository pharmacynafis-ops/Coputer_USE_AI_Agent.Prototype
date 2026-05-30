"""
context_owner.py
مسؤول عن الحفاظ على سياق المحادثة، وتتبع الملفات والأوامر،
واكتشاف ما إذا كان الوكيل عالقاً، والبحث في الذاكرة، وطلب المساعدة من المستخدم.
"""

import os
import json
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple


class ContextOwner:
    def __init__(self, memory_dir: str = "memory"):
        self.memory_dir = memory_dir
        self.session_id = None
        self.conversation_history: List[Dict] = []
        self.file_registry: Dict[str, Dict] = {}      # path -> {created_at, content_hash, session_id}
        self.command_history: List[Dict] = []         # {command, result, timestamp, session_id}
        self.failure_log: List[Dict] = []             # {step_number, error, timestamp, attempt_count}
        self.refine_count = 0
        self._ensure_directories()
    
    def _ensure_directories(self):
        """إنشاء هيكل مجلدات الذاكرة إذا لم تكن موجودة"""
        subdirs = ["sessions", "files", "commands"]
        for sub in subdirs:
            path = os.path.join(self.memory_dir, sub)
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
    
    def start_session(self, user_prompt: str) -> str:
        """بدء جلسة جديدة وحفظها"""
        import uuid
        self.session_id = str(uuid.uuid4())[:8]
        session_data = {
            "session_id": self.session_id,
            "started_at": datetime.now().isoformat(),
            "user_prompt": user_prompt,
            "conversation": [],
            "file_registry_snapshot": {},
            "command_history_snapshot": []
        }
        session_path = os.path.join(self.memory_dir, "sessions", f"session_{self.session_id}.json")
        with open(session_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
        
        # إضافة الطلب الأول إلى المحادثة
        self.conversation_history.append({
            "role": "user",
            "content": user_prompt,
            "timestamp": datetime.now().isoformat()
        })
        return self.session_id
    
    def update_after_step(self, step: Dict, result: str, success: bool):
        """تحديث الذاكرة بعد كل خطوة"""
        step_number = step.get("step_number", 0)
        tool_name = step.get("tool", "")
        arguments = step.get("arguments", {})
        
        # تسجيل في سجل المحادثة
        self.conversation_history.append({
            "role": "agent",
            "step_number": step_number,
            "tool": tool_name,
            "arguments": arguments,
            "result": result[:500],  # تقطيع النتائج الطويلة
            "success": success,
            "timestamp": datetime.now().isoformat()
        })
        
        # تسجيل الملفات التي تم إنشاؤها
        if tool_name == "write_file" and "path" in arguments:
            path = arguments["path"]
            content = arguments.get("content", "")
            content_hash = hashlib.md5(content.encode()).hexdigest()
            self.file_registry[path] = {
                "created_at": datetime.now().isoformat(),
                "content_hash": content_hash,
                "session_id": self.session_id,
                "last_content": content[:200]  # حفظ جزء فقط
            }
            # حفظ في ملف منفصل
            self._save_file_registry()
        
        # تسجيل الأوامر المنفذة
        if tool_name == "execute_command" and "command" in arguments:
            self.command_history.append({
                "command": arguments["command"],
                "result": result[:500],
                "timestamp": datetime.now().isoformat(),
                "session_id": self.session_id
            })
            self._save_command_history()
        
        # تسجيل الفشل إذا حدث
        if not success:
            self.failure_log.append({
                "step_number": step_number,
                "error": result[:200],
                "timestamp": datetime.now().isoformat(),
                "attempt_count": len([f for f in self.failure_log if f.get("step_number") == step_number]) + 1
            })
    
    def _save_file_registry(self):
        """حفظ سجل الملفات في ملف"""
        registry_path = os.path.join(self.memory_dir, "files", "file_registry.json")
        with open(registry_path, "w", encoding="utf-8") as f:
            json.dump(self.file_registry, f, ensure_ascii=False, indent=2)
    
    def _save_command_history(self):
        """حفظ سجل الأوامر في ملف"""
        history_path = os.path.join(self.memory_dir, "commands", "command_history.json")
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(self.command_history, f, ensure_ascii=False, indent=2)
    
    def get_failure_count_for_step(self, step_number: int) -> int:
        """الحصول على عدد مرات فشل خطوة معينة"""
        count = 0
        for failure in self.failure_log:
            if failure.get("step_number") == step_number:
                count += 1
        return count
    
    def get_failure_type(self, error_message: str) -> str:
        """تحديد نوع الخطأ بناءً على الرسالة"""
        error_lower = error_message.lower()
        if "not found" in error_lower:
            return "file_not_found"
        elif "permission denied" in error_lower:
            return "permission_denied"
        elif "timeout" in error_lower:
            return "timeout"
        elif "command" in error_lower and "not recognized" in error_lower:
            return "command_not_found"
        elif "requires" in error_lower and "argument" in error_lower:
            return "missing_argument"
        else:
            return "unknown"
    
    def is_stuck(self, step: Dict, error_message: str) -> Tuple[bool, str]:
        """
        تحديد إذا كان الوكيل عالقاً.
        تعيد: (is_stuck, reason)
        """
        step_number = step.get("step_number", 0)
        failure_count = self.get_failure_count_for_step(step_number)
        failure_type = self.get_failure_type(error_message)
        
        # معيار 1: نفس الخطوة تفشل 3 مرات متتالية
        if failure_count >= 3:
            return True, f"الخطوة {step_number} فشلت {failure_count} مرات متتالية"
        
        # معيار 2: ملف غير موجود وفشل مرتين
        if failure_type == "file_not_found" and failure_count >= 2:
            return True, f"الملف غير موجود، والخطوة {step_number} فشلت مرتين"
        
        # معيار 3: أمر طرفية يفشل مرتين
        if failure_type == "command_not_found" and failure_count >= 2:
            return True, f"الأمر غير معروف، والخطوة {step_number} فشلت مرتين"
        
        # معيار 4: إعادة تخطيط أكثر من 5 مرات في نفس الجلسة
        if self.refine_count >= 5:
            return True, f"تمت إعادة التخطيط {self.refine_count} مرات دون تقدم"
        
        return False, ""
    
    def search_memory(self, query: str) -> Dict[str, Any]:
        """
        البحث في الذاكرة عن سياق مفيد.
        تعيد قاموساً يحتوي على نتائج البحث.
        """
        results = {
            "found_files": [],
            "found_commands": [],
            "relevant_conversation": []
        }
        
        # البحث في سجل الملفات
        for path, info in self.file_registry.items():
            if query.lower() in path.lower():
                results["found_files"].append({
                    "path": path,
                    "created_at": info.get("created_at"),
                    "content_preview": info.get("last_content", "")
                })
        
        # البحث في سجل الأوامر
        for cmd in self.command_history:
            if query.lower() in cmd.get("command", "").lower():
                results["found_commands"].append(cmd)
        
        # البحث في المحادثة السابقة
        for msg in self.conversation_history[-10:]:  # آخر 10 رسائل
            if msg.get("role") == "user":
                if query.lower() in msg.get("content", "").lower():
                    results["relevant_conversation"].append(msg)
        
        return results
    
    def generate_help_question(self, step: Dict, error_message: str, memory_search: Dict) -> str:
        """
        توليد سؤال للمستخدم عندما يكون الوكيل عالقاً.
        """
        step_number = step.get("step_number", 0)
        description = step.get("description", "تنفيذ خطوة")
        tool_name = step.get("tool", "أداة")
        
        question = f"""🤔 **الوكيل عالق!**

❌ **الخطوة {step_number} فشلت:** {description}
🔧 **الأداة:** {tool_name}
⚠️ **الخطأ:** {error_message[:200]}

"""
        
        # إضافة اقتراحات من الذاكرة
        if memory_search.get("found_files"):
            question += "📂 **ملفات ذات صلة وجدتها في ذاكرتي:**\n"
            for file in memory_search["found_files"][:3]:
                question += f"   - `{file['path']}`\n"
            question += "\n"
        
        if memory_search.get("found_commands"):
            question += "💻 **أوامر سابقة ذات صلة:**\n"
            for cmd in memory_search["found_commands"][:2]:
                question += f"   - `{cmd.get('command')}`\n"
            question += "\n"
        
        question += """❓ **ماذا تريد مني أن أفعل؟**

🔘 [أ) أعد المحاولة بنفس الطريقة]
🔘 [ب) استخدم المسار الصحيح للملف]
🔘 [ج) أشرح لك ما أقصده أكثر]
🔘 [د) توقف عن هذه المهمة]

الرجاء إرسال إجابتك (أ، ب، ج، د)"""
        
        return question
    
    def save_conversation_to_session(self):
        """حفظ المحادثة الحالية في ملف الجلسة"""
        if not self.session_id:
            return
        session_path = os.path.join(self.memory_dir, "sessions", f"session_{self.session_id}.json")
        if os.path.exists(session_path):
            with open(session_path, "r", encoding="utf-8") as f:
                session_data = json.load(f)
            session_data["conversation"] = self.conversation_history
            session_data["file_registry_snapshot"] = self.file_registry
            session_data["command_history_snapshot"] = self.command_history
            with open(session_path, "w", encoding="utf-8") as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)

    def resume_session(self, session_id: str) -> bool:
        """
        Resume an existing session by loading its stored session file.
        Returns True if resumed successfully, False otherwise.
        """
        if not session_id:
            return False
        session_path = os.path.join(self.memory_dir, "sessions", f"session_{session_id}.json")
        if not os.path.exists(session_path):
            return False
        try:
            with open(session_path, "r", encoding="utf-8") as f:
                session_data = json.load(f)
            self.session_id = session_data.get("session_id", session_id)
            # Load previous conversation if present, otherwise start fresh list
            self.conversation_history = session_data.get("conversation", [])
            # Restore registries if present
            self.file_registry = session_data.get("file_registry_snapshot", self.file_registry)
            self.command_history = session_data.get("command_history_snapshot", self.command_history)
            return True
        except Exception:
            return False

    def get_last_assistant_message(self) -> Optional[str]:
        """Return the most recent assistant message content, or None if missing."""
        for msg in reversed(self.conversation_history):
            if msg.get("role") == "assistant":
                return msg.get("content")
        return None
    
    def reset_refine_count(self):
        """إعادة تعيين عداد إعادة التخطيط"""
        self.refine_count = 0
    
    def increment_refine_count(self):
        """زيادة عداد إعادة التخطيط"""
        self.refine_count += 1