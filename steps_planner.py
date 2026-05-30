"""
steps_planner.py
مسؤول عن إنشاء خطة تفصيلية لتنفيذ طلب المستخدم.
"""

import json
import uuid
import re
from typing import Dict, Any, List, Optional
from openai import OpenAI
from datetime import datetime

class StepsPlanner:
    def __init__(self, api_key: str):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        self.model = "openai/gpt-4o-mini"

    def _fix_json(self, content: str) -> str:
        """محاولة إصلاح JSON التالف بشكل بسيط"""
        first_brace = content.find('{')
        last_brace = content.rfind('}')
        if first_brace != -1 and last_brace != -1:
            content = content[first_brace:last_brace+1]
        
        backslash_count = content.count('\\')
        quote_count = content.count('"') - backslash_count
        if quote_count % 2 != 0:
            content += '"'
        
        content = re.sub(r'}\s*{', '},{', content)
        
        return content

    def create_plan(self, user_prompt: str, workspace_path: str = None) -> Dict[str, Any]:
        planning_prompt = f"""
أنت خبير في تخطيط المهام بدقة عالية. مهمتك: تحليل طلب المستخدم وتقسيمه إلى خطوات صغيرة قابلة للتنفيذ باستخدام الأدوات المتاحة.

طلب المستخدم: "{user_prompt}"

مسار العمل الحالي: "{workspace_path or 'e:\\Computer_Use\\v2_using_AI'}"
**مهم جداً: عند إنشاء ملفات، يجب أن يكون المسار داخل مسار العمل الحالي أو في مجلد فرعي منه.**

الأدوات المتاحة:
1. write_file (path, content) - لكتابة أو تعديل ملف. MUST use "path" as the key for file path, NOT "file_path".
2. read_file (path) - لقراءة ملف. MUST use "path" as the key.
3. execute_command (command) - لتنفيذ أمر طرفية. MUST use "command" as the key.
4. redirect_to_scope_page () - لا تأخذ معاملات، تستخدم لتوجيه المستخدم إلى صفحة تعديل النطاق.
5. create_new_customization_tool (missing_tool, user_prompt) - هذه الأداة تُستخدم عندما يطلب المستخدم أداة غير موجودة في النظام أو يفشل استخدامها بشكل متكرر. تقوم بتوليد صفحة تفاعلية لعرض تفاصيل الأداة المقترحة.

قواعد صارمة جداً:
- **عند استخدام write_file، يجب أن يكون arguments بهذا الشكل بالضبط:**
  {{ "path": "C:\\المسار\\الملف.html", "content": "محتوى الملف كاملاً" }}
- **لإنشاء مجلد جديد، لا تستخدم execute_command مع mkdir. بدلاً من ذلك، استخدم write_file لإنشاء ملف .gitkeep داخل المجلد. على سبيل المثال، لإنشاء مجلد "new_folder"، استخدم: {{ "path": "E:\\specific\\path\\new_folder\\.gitkeep", "content": "" }}**
- **لا تستخدم أبداً "file_path" أو "filePath" أو أي مفتاح آخر بدلاً من "path".**
- لا تضع أكثر من أداة واحدة في كل خطوة.
- عدد الخطوات يجب أن يكون مناسباً لتعقيد المهمة (بين 1 و 10 خطوات).
- اشرح كل خطوة بوضوح وبالعربية.
- إذا كان الطلب لا يحتاج أدوات (تحية، سؤال عادي، سؤال متابعة مثل "لماذا"، "كيف"، "هذا"، "ذلك")، اجعل total_steps = 0.
- تأكد من أن التسلسل منطقي.
- للتحقق من وجود ملف، استخدم read_file وليس execute_command.
- **إذا كنت ستكتب محتوى في ملف، اكتب المحتوى كاملاً في خطوة واحدة.** لا تقسم كتابة ملف واحد إلى عدة خطوات.
- أضف خطوات تحقق عند الحاجة.
- **إذا كان الطلب يتضمن "redirect me to the scope page" أو "تعديل مجلد العمل" أو ما شابه، استخدم الأداة redirect_to_scope_page مع arguments = {{}}.**

أخرج الخطة بصيغة JSON فقط بالشكل التالي:
{{
  "total_steps": <عدد>,
  "steps": [
    {{
      "step_number": 1,
      "description": "وصف الخطوة",
      "tool": "write_file",
      "arguments": {{ "path": "مسار الملف", "content": "محتوى الملف كاملاً" }}
    }},
    {{
      "step_number": 2,
      "description": "وصف الخطوة",
      "tool": "read_file",
      "arguments": {{ "path": "مسار الملف" }}
    }},
    {{
      "step_number": 3,
      "description": "وصف الخطوة",
      "tool": "execute_command",
      "arguments": {{ "command": "الأمر المطلوب" }}
    }},
    {{
      "step_number": 4,
      "description": "توجيه المستخدم إلى صفحة تعديل النطاق",
      "tool": "redirect_to_scope_page",
      "arguments": {{}}
    }},
     {{
      "step_number": 5,
      "description": "إنشاء أداة جديدة لأن المستخدم طلب أمراً غير موجود",
      "tool": "create_new_customization_tool",
      "arguments": {{ "missing_tool": "execute_command", "user_prompt": "can you run tree /f" }}
    }}
  ],
  "explanation": "شرح موجز للخطة"
}}

لا تضف أي نص خارج JSON.
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": planning_prompt}],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=800
            )
            content = response.choices[0].message.content
            plan = json.loads(content)
        except Exception as e:
            print(f"Planning error: {e}")
            plan = {
                "total_steps": 1,
                "steps": [{
                    "step_number": 1,
                    "description": "محاولة تنفيذ الطلب مباشرة",
                    "tool": "execute_command",
                    "arguments": {"command": f"echo 'Executing: {user_prompt}'"}
                }],
                "explanation": f"تعذر التخطيط المفصل. الخطأ: {str(e)[:100]}"
            }
        
        # تطبيع arguments للتأكد من استخدام المفاتيح الصحيحة
        for step in plan.get("steps", []):
            if step.get("tool") == "write_file":
                args = step.get("arguments", {})
                # تحويل file_path إلى path إذا وجد
                if "file_path" in args and "path" not in args:
                    args["path"] = args.pop("file_path")
                if "filePath" in args and "path" not in args:
                    args["path"] = args.pop("filePath")
                # إذا كان path مفقوداً أو فارغاً، استخدم مساراً افتراضياً داخل مجلد العمل
                if "path" not in args or not args["path"]:
                    args["path"] = "test.txt"
                if "content" not in args:
                    args["content"] = ""
                step["arguments"] = args
            elif step.get("tool") == "read_file":
                args = step.get("arguments", {})
                if "file_path" in args and "path" not in args:
                    args["path"] = args.pop("file_path")
                if "filePath" in args and "path" not in args:
                    args["path"] = args.pop("filePath")
                step["arguments"] = args
            elif step.get("tool") == "redirect_to_scope_page":
                # تأكد من أن arguments فارغة
                step["arguments"] = {}
            elif step.get("tool") == "create_new_customization_tool":
                args = step.get("arguments", {})
                if "missing_tool" not in args:
                    args["missing_tool"] = "unknown_tool"
                if "user_prompt" not in args:
                    args["user_prompt"] = user_prompt
                step["arguments"] = args
        
        plan["session_id"] = str(uuid.uuid4())
        plan["user_prompt"] = user_prompt
        plan["created_at"] = datetime.now().isoformat()
        return plan

    def refine_plan(self, original_plan: Dict, failed_step: Dict, error_message: str, workspace_path: str = None) -> Dict:
        refine_prompt = f"""
الخطة الأصلية فشلت في الخطوة رقم {failed_step.get('step_number')}:
- الوصف: {failed_step.get('description')}
- الأداة: {failed_step.get('tool')}
- الوسائط: {json.dumps(failed_step.get('arguments', {}))}
- الخطأ: {error_message}

طلب المستخدم الأصلي: {original_plan.get('user_prompt')}

مسار العمل الحالي: "{workspace_path or 'e:\\Computer_Use\\v2_using_AI'}"

**معلومات مهمة للتصحيح:**
- إذا كان الخطأ يقول "requires 'path' argument"، فهذا يعني أنك استخدمت مفتاحاً خاطئاً مثل "file_path".
- الصيغة الصحيحة لـ write_file هي: {{ "path": "المسار", "content": "المحتوى" }}
- الصيغة الصحيحة لـ read_file هي: {{ "path": "المسار" }}
- الصيغة الصحيحة لـ execute_command هي: {{ "command": "الأمر" }}
- إذا فشلت write_file بسبب نقص "path" أو "content"، أضف القيم الافتراضية: path = "test.txt", content = "".
- إذا كان الخطأ "Access denied" لأن المسار خارج نطاق العمل، استخدم مساراً داخل مسار العمل الحالي: {workspace_path or 'e:\\Computer_Use\\v2_using_AI'}

قم بتعديل الخطة لتصحيح هذه الخطوة فقط (أعد صياغة الخطوات من هذه النقطة فصاعداً).
أخرج JSON بنفس بنية الخطة الأصلية (total_steps, steps, explanation).
لا تضف أي نص خارج JSON.
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": refine_prompt}],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=600
            )
            content = response.choices[0].message.content
            fixed_content = self._fix_json(content)
            new_part = json.loads(fixed_content)
        except Exception as e:
            print(f"Refinement error: {e}")
            new_part = {
                "total_steps": 1,
                "steps": [{
                    "step_number": failed_step.get('step_number', 1),
                    "description": "تخطي الخطوة التي فشل تصحيحها",
                    "tool": "none",
                    "arguments": {}
                }],
                "explanation": f"تم التخطي تلقائياً بسبب فشل LLM في إنتاج خطة بديلة صالحة: {str(e)[:100]}"
            }

        
        # تطبيع arguments في الخطة المصححة (مع إضافة القيم الافتراضية إذا لزم الأمر)
        for step in new_part.get("steps", []):
            if step.get("tool") == "write_file":
                args = step.get("arguments", {})
                if "file_path" in args and "path" not in args:
                    args["path"] = args.pop("file_path")
                if "filePath" in args and "path" not in args:
                    args["path"] = args.pop("filePath")
                if "path" not in args or not args["path"]:
                    # محاولة استخراج مسار من الخطأ إذا كان متاحاً
                    if "outside your workspace scope" in error_message:
                        # استخدام مسار افتراضي داخل مجلد العمل (سيتم التحقق منه لاحقاً)
                        args["path"] = "test.txt"
                    else:
                        args["path"] = "test.txt"
                if "content" not in args:
                    args["content"] = ""
                step["arguments"] = args
            elif step.get("tool") == "read_file":
                args = step.get("arguments", {})
                if "file_path" in args and "path" not in args:
                    args["path"] = args.pop("file_path")
                if "filePath" in args and "path" not in args:
                    args["path"] = args.pop("filePath")
                step["arguments"] = args
            elif step.get("tool") == "redirect_to_scope_page":
                step["arguments"] = {}
        
        original_steps = original_plan.get("steps", [])
        failed_index = failed_step.get("step_number", 1) - 1
        if failed_index < 0:
            failed_index = 0
        new_steps = new_part.get("steps", [])
        if not new_steps:
            new_steps = [{
                "step_number": failed_step.get('step_number', 1),
                "description": "تخطي الخطوة الفاشلة",
                "tool": "none",
                "arguments": {}
            }]
        
        corrected_steps = original_steps[:failed_index] + new_steps + original_steps[failed_index+1:]
        original_plan["steps"] = corrected_steps
        original_plan["total_steps"] = len(corrected_steps)
        original_plan["explanation"] = new_part.get("explanation", "تم تصحيح الخطة")
        original_plan["refined_at"] = datetime.now().isoformat()
        return original_plan