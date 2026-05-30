"""
long_term_memory.py
مسؤول عن الذاكرة طويلة المدى للوكيل.
يتذكر المستخدم، تاريخ المحادثات، والملفات التي تم إنشاؤها.
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional


class LongTermMemory:
    
    def __init__(self, memory_dir: str = "memory/long_term"):
        self.memory_dir = memory_dir
        self._ensure_directories()
        self.user_profile = self._load_user_profile()
         # التأكد من وجود الحقل (للتحديث)
        if "last_workspace_scope" not in self.user_profile:
            self.user_profile["last_workspace_scope"] = None
        self.project_history = self._load_project_history()
        self.agent_identity = self._load_agent_identity()
    
    def _ensure_directories(self):
        if not os.path.exists(self.memory_dir):
            os.makedirs(self.memory_dir, exist_ok=True)
    
    def _load_user_profile(self) -> Dict:
        path = os.path.join(self.memory_dir, "user_profile.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "first_interaction": datetime.now().isoformat(),
            "interaction_count": 0,
            "last_interaction": None,
            "known_info": {
                "user_name": None,
                "user_preferences": [],
                "user_skills": []
            },
            "files_created": [],
            "projects_completed": []
        }
    
    def _load_project_history(self) -> List[Dict]:
        path = os.path.join(self.memory_dir, "project_history.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    
    def _load_agent_identity(self) -> Dict:
        path = os.path.join(self.memory_dir, "agent_identity.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "name": "AI Computer Use Agent",
            "version": "3.1",
            "capabilities": ["write_file", "read_file", "execute_command"],
            "created_at": datetime.now().isoformat(),
            "description": "وكيل ذكي متخصص في التحكم بالكمبيوتر، يمكنه إنشاء وقراءة الملفات وتنفيذ الأوامر الطرفية."
        }
    
    def _save_user_profile(self):
        path = os.path.join(self.memory_dir, "user_profile.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.user_profile, f, ensure_ascii=False, indent=2)
    
    def _save_project_history(self):
        path = os.path.join(self.memory_dir, "project_history.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.project_history, f, ensure_ascii=False, indent=2)

    def _ensure_research_dir(self):
        path = os.path.join(self.memory_dir, "research")
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)

    def add_research_artifact(self, artifact_name: str, description: str, sources: Optional[Dict] = None):
        """Persist research/analysis/debug artifacts for later human review.

        Stores a JSON file under `memory/long_term/research/` with a timestamped filename.
        """
        self._ensure_research_dir()
        filename = f"{artifact_name}.json"
        path = os.path.join(self.memory_dir, "research", filename)
        payload = {
            "name": artifact_name,
            "description": description,
            "sources": sources or {},
            "created_at": datetime.now().isoformat()
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    
    def update_interaction(self, user_prompt: str, assistant_response: str, success: bool = True):
        """تسجيل تفاعل جديد في الذاكرة"""
        self.user_profile["interaction_count"] += 1
        self.user_profile["last_interaction"] = datetime.now().isoformat()
        
        self.project_history.append({
            "timestamp": datetime.now().isoformat(),
            "user_prompt": user_prompt[:500],
            "assistant_response": assistant_response[:500],
            "success": success
        })
        
        # الاحتفاظ بآخر 50 تفاعل فقط
        if len(self.project_history) > 50:
            self.project_history = self.project_history[-50:]
        
        self._save_user_profile()
        self._save_project_history()
    
    def learn_about_user(self, key: str, value: Any):
        """تعلم معلومة جديدة عن المستخدم"""
        self.user_profile["known_info"][key] = {
            "value": value,
            "learned_at": datetime.now().isoformat()
        }
        self._save_user_profile()
    
    def get_context_for_prompt(self, user_prompt: str) -> str:
        """
        توليد سياق تاريخي لإضافته إلى برومبت المستخدم.
        هذا ما سيجعل الوكيل يتذكر الماضي.
        """
        context_parts = []
        
        # معلومات عن المستخدم
        known_info = self.user_profile.get("known_info", {})
        if known_info:
            context_parts.append("## معلومات سابقة عن المستخدم:")
            for key, info in known_info.items():
                # التحقق من أن info ليست None وقاموس وله قيمة
                if info is not None and isinstance(info, dict):
                    value = info.get("value")
                    if value:
                        context_parts.append(f"- {key}: {value}")
        
        # عدد التفاعلات
        interaction_count = self.user_profile.get("interaction_count", 0)
        if interaction_count > 0:
            context_parts.append(f"\n## إحصائيات: لقد تفاعلت مع المستخدم {interaction_count} مرة سابقاً.")
        
        # تاريخ المشروع (آخر 3 تفاعلات)
        if self.project_history:
            context_parts.append("\n## تاريخ المحادثات السابقة (آخر 3):")
            for item in self.project_history[-3:]:
                prompt_preview = item.get("user_prompt", "")[:100]
                timestamp = item.get("timestamp", "")[:16].replace("T", " ")
                status = "✅ نجاح" if item.get("success") else "❌ فشل"
                context_parts.append(f"- {timestamp}: {prompt_preview}... → {status}")
        
        # الملفات التي تم إنشاؤها سابقاً
        files_created = self.user_profile.get("files_created", [])
        if files_created:
            context_parts.append("\n## ملفات تم إنشاؤها مسبقاً:")
            for file_info in files_created[-5:]:
                context_parts.append(f"- {file_info.get('path', 'مسار غير معروف')}")
        
        # هوية الوكيل
        context_parts.append(f"\n## معلومات عنك (الوكيل):")
        context_parts.append(f"- اسمك: {self.agent_identity.get('name', 'وكيل ذكي')}")
        context_parts.append(f"- إصدارك: {self.agent_identity.get('version', '3.0')}")
        context_parts.append(f"- قدراتك: {', '.join(self.agent_identity.get('capabilities', []))}")
        
        context_parts.append("\n## تعليمات مهمة للرد على المستخدم:")
        context_parts.append("- عندما يسألك المستخدم 'ماذا تعرف عني؟'، أخبره بكل المعلومات التي تعلمتها عنه من الذاكرة.")
        context_parts.append("- عندما يسألك 'ماذا بنينا معاً؟'، أخبره بتاريخ المشروع والمحادثات السابقة.")
        context_parts.append("- إذا قال المستخدم 'أنا فannan' أو أي اسم آخر، تذكره في الذاكرة.")
        context_parts.append("- كن ودوداً وتذكر أن المستخدم هو صديقك وقد عملتما معاً على مشاريع عديدة.")
        
        return "\n".join(context_parts)


    def extract_user_info_from_conversation(self, user_prompt: str, assistant_response: str):
        """استخراج معلومات عن المستخدم من المحادثة وحفظها"""
        # مثال: إذا قال المستخدم "أنا فannan" أو "اسمي فannan"
        lower_prompt = user_prompt.lower()
        if "اسمي" in lower_prompt or "أنا" in lower_prompt:
            import re
            # محاولة استخراج الاسم
            name_match = re.search(r'(?:اسمي|أنا)[\s:]+([^\s\.]+)', user_prompt)
            if name_match:
                name = name_match.group(1)
                self.learn_about_user("user_name", name)
    
    def add_file_record(self, file_path: str, content: str, session_id: str):
        """تسجيل ملف تم إنشاؤه في الذاكرة طويلة المدى"""
        if "files_created" not in self.user_profile:
            self.user_profile["files_created"] = []
        
        self.user_profile["files_created"].append({
            "path": file_path,
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
            "content_preview": content[:100]
        })
        
        # الاحتفاظ بآخر 100 ملف فقط
        if len(self.user_profile["files_created"]) > 100:
            self.user_profile["files_created"] = self.user_profile["files_created"][-100:]
        
        self._save_user_profile()
    
    def add_completed_project(self, project_name: str, description: str):
        """تسجيل مشروع تم إنجازه"""
        if "projects_completed" not in self.user_profile:
            self.user_profile["projects_completed"] = []
        
        self.user_profile["projects_completed"].append({
            "name": project_name,
            "description": description,
            "completed_at": datetime.now().isoformat()
        })
        self._save_user_profile()