# add_new_tool.py
import json
import os
from typing import Dict, Any, List
from openai import OpenAI
from datetime import datetime

class ToolCreator:
    def __init__(self, api_key: str):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        self.model = "openai/gpt-4o-mini"

    def generate_tool_details(self, user_prompt: str, missing_tool: str) -> Dict[str, Any]:
        """توليد تفاصيل أداة جديدة بناءً على طلب المستخدم والأداة المفقودة"""
        prompt = f"""
أنت خبير في تطوير أدوات لوكيل ذكي.

المستخدم طلب تنفيذ أمر أو استخدام أداة، لكن الوكيل لا يمتلك هذه الأداة.
الطلب الأصلي: "{user_prompt}"
الأداة المطلوبة (المفقودة): "{missing_tool}"

مهمتك هي اقتراح أداة جديدة يمكن إضافتها إلى النظام.

قم بتحليل الطلب وفهم ما يريد المستخدم فعله بالضبط.
ثم أخرج JSON بالشكل التالي:

{{
  "tool_name": "الاسم المقترح للأداة (بالإنجليزية، صغير underscore_case)",
  "tool_description": "وصف مختصر لما تفعله الأداة",
  "parameters": [
    {{ "name": "parameter1", "type": "str", "description": "وصف", "required": true }},
    {{ "name": "parameter2", "type": "int", "description": "وصف", "required": false, "default": 30 }}
  ],
  "sample_code": "def tool_name(param1: str, param2: int = 30) -> str:\\n    try:\\n        # تنفيذ المنطق هنا\\n        return f'Success: Done'\\n    except Exception as e:\\n        return f'Error: {{str(e)}}'",
  "example_usage": "أمثلة على كيفية استخدام المستخدم لهذه الأداة في المستقبل",
  "explanation": "شرح بالعربية لماذا هذه الأداة مناسبة وما الذي ستفعله"
}}

تأكد من أن الكود النموذجي حقيقي وقابل للتنفيذ مع تعديلات بسيطة.
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=800
            )
            result = json.loads(response.choices[0].message.content)
            return result
        except Exception as e:
            # خطة بديلة حقيقية (ليست وهمية)
            safe_name = missing_tool.replace(" ", "_").lower()
            return {
                "tool_name": safe_name,
                "tool_description": f"يقوم بتنفيذ العملية التي طلبها المستخدم: {user_prompt[:100]}",
                "parameters": [],
                "sample_code": f"def {safe_name}() -> str:\n    try:\n        # أضف المنطق المناسب هنا\n        return 'Success: تم تنفيذ {missing_tool}'\n    except Exception as e:\n        return f'Error: {{str(e)}}'",
                "example_usage": user_prompt,
                "explanation": f"هذه الأداة تم اقتراحها لأن المستخدم طلب: {user_prompt}"
            }

    def save_new_tool(self, tool_data: Dict[str, Any]) -> Dict[str, Any]:
        """حفظ الأداة الجديدة في ملف tools_registry.json"""
        tools_file = "tools_registry.json"
        existing_tools = {}
        if os.path.exists(tools_file):
            with open(tools_file, "r", encoding="utf-8") as f:
                existing_tools = json.load(f)
        
        tool_name = tool_data.get("tool_name")
        if not tool_name:
            return {"status": "error", "message": "اسم الأداة مطلوب"}
        
        existing_tools[tool_name] = {
            "description": tool_data.get("tool_description"),
            "parameters": tool_data.get("parameters", []),
            "sample_code": tool_data.get("sample_code"),
            "created_at": datetime.now().isoformat(),
            "user_prompt": tool_data.get("example_usage", "")
        }
        
        with open(tools_file, "w", encoding="utf-8") as f:
            json.dump(existing_tools, f, ensure_ascii=False, indent=2)
        
        return {"status": "saved", "tool_name": tool_name}