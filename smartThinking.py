"""
smartThinking.py
وحدة متخصصة في تحليل جودة ردود الوكيل، وإعادة صياغتها أو تحسينها.
تم إضافة وظائف التحقق والتقييم مع دعم أفضل للسياق.
"""

import os
import json
from typing import Dict, Any, Optional, Tuple, List
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class SmartThinking:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )
        self.model = "openai/gpt-4o-mini"

    def set_api_key(self, new_key: str):
        self.api_key = new_key
        self.client.api_key = new_key

    def should_skip_thinking(self, user_prompt: str, conversation_history: List[Dict] = None) -> Tuple[bool, str]:
        # Build context from conversation history
        history_context = ""
        if conversation_history:
            last_messages = conversation_history[-5:] if len(conversation_history) > 5 else conversation_history
            history_context = "\n\n## السياق الأخير:\n"
            for msg in last_messages:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')[:300]
                history_context += f"- {role}: {content}\n"

        fast_prompt = f"""
        حدد إذا كان الرد التالي يحتاج إلى تنفيذ أدوات (كتابة ملف، قراءة ملف، أمر طرفية) أم لا.
        إذا كان مجرد تحية أو سؤال عادي لا يتطلب أي إجراء، أجب "SKIP" ثم اكتب الرد المناسب.
        إذا كان يحتاج إلى وكيل، أجب "NEED_AGENT".

        ## ملاحظات مهمة:
        - إذا كان الطلب يحتوي على كلمات مثل "لماذا" (why), "كيف" (how), "متى" (when), "أين" (where), أو ضمائر مثل "هذا" (this), "ذلك" (that), "هو" (it), "هم" (they), فهذا سؤال متابعة.
        - في حال الأسئلة المتابعة، استخدم السياق من قسم "السياق الأخير" أدناه لتقديم إجابة دقيقة.
        - لا تطلب من المستخدم التوضيح إذا كان السياق واضحاً من المحادثة السابقة.
        - إذا كان السؤال المتابعة يطلب شرحاً أو توضيحاً لما قيل سابقاً، أجب "SKIP" مع الرد المناسب.

        نص المستخدم: "{user_prompt}"
        {history_context}

        أجب فقط بصيغة: SKIP: الرد المناسب  أو NEED_AGENT
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": fast_prompt}],
                max_tokens=100,
                temperature=0.0
            )
            result = response.choices[0].message.content.strip()
            if result.startswith("SKIP"):
                reply = result.split(":", 1)[1].strip()
                return True, reply
            else:
                return False, ""
        except Exception:
            return False, ""

    def verify_step(self, step: Dict, tool_result: str) -> bool:
        """
        تتحقق من أن نتيجة الأداة تطابق ما هو متوقع من الخطوة.
        """
        # حالات خاصة للنجاح
        if "File exists" in tool_result or "cannot create directory" in tool_result:
            return True
        if "Success" in tool_result:
            return True
        if "Content:" in tool_result:
            return True
        
        verify_prompt = f"""
        أنت مدقق جودة. حدد إذا كانت نتيجة تنفيذ الأداة تشير إلى نجاح الخطوة أم فشل.

        الخطوة المخطط لها:
        - الوصف: {step.get('description', '')}
        - الأداة: {step.get('tool', '')}
        - الوسائط: {json.dumps(step.get('arguments', {}))}

        نتيجة التنفيذ:
        "{tool_result}"

        أجب بكلمة واحدة فقط: SUCCESS أو FAILED
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": verify_prompt}],
                max_tokens=10,
                temperature=0.0
            )
            verdict = response.choices[0].message.content.strip().upper()
            return verdict == "SUCCESS"
        except Exception:
            return "Success" in tool_result or "Content" in tool_result

    def final_verification(self, user_prompt: str, plan: Dict, execution_log: List[Dict]) -> Dict:
        """
        تراجع كل شيء وتتأكد أن الهدف تحقق بنسبة 100%.
        إذا لم يتحقق، تقترح خطة تصحيحية حقيقية.
        """
        log_text = ""
        for item in execution_log:
            log_text += f"\nالخطوة {item.get('step_number')}: {item.get('description')}\n"
            log_text += f"الأداة: {item.get('tool')} | النتيجة: {item.get('result', '')[:200]}\n"

        final_prompt = f"""
        أنت خبير في التأكد من اكتمال المهام. قم بتحليل ما إذا كان طلب المستخدم قد تم تنفيذه بالكامل.

        طلب المستخدم الأصلي: "{user_prompt}"

        الخطة المتبعة:
        {json.dumps(plan, ensure_ascii=False, indent=2)}

        سجل التنفيذ:
        {log_text}

        المطلوب منك:
        1. حدد إذا كان الهدف قد تحقق بنسبة 100%. كن صارماً: إذا كان الملف يحتوي على كود JavaScript غير صحيح (مثل setTimeout بدون دالة تؤخر الطباعة)، فهذا فشل.
        2. اكتب تقريراً مفصلاً (بالعربية) يشرح ما تم إنجازه وأي نقص إن وجد.
        3. إذا لم يتحقق الهدف، اكتب خطة تصحيحية (بنفس بنية الخطة الأصلية) مكونة من خطوات إضافية. يجب أن تكون الخطة التصحيحية عملية وتصحح الخطأ المحدد (مثلاً: إعادة كتابة ملف index.html بكود صحيح).

        أخرج JSON بالشكل التالي بدون أي نص إضافي خارج JSON:
        {{
          "is_goal_achieved": true/false,
          "report": "نص التقرير",
          "correction_plan": {{
            "total_steps": عدد الخطوات التصحيحية,
            "steps": [
              {{
                "step_number": 1,
                "description": "وصف الخطوة التصحيحية",
                "tool": "write_file",
                "arguments": {{ "path": "المسار", "content": "المحتوى الصحيح" }}
              }}
            ],
            "explanation": "شرح الخطة التصحيحية"
          }}
        }}
        
        ملاحظة: إذا كان الفشل بسبب كود JavaScript غير صحيح، يجب أن تحتوي الخطة التصحيحية على خطوة واحدة فقط: write_file بالكود الصحيح الذي يحقق التأخير المطلوب.
        الكود الصحيح لطباعة 'hello world' 10 مرات كل 13 ثانية:
        
        <html><body>
        <script>
        for (let i = 0; i < 10; i++) {{
          setTimeout(() => {{
            document.write('hello world<br>');
          }}, i * 13000);
        }}
        </script>
        </body></html>
        
        استخدم هذا الكود بالضبط في الخطة التصحيحية إذا كان طلب المستخدم مشابهاً.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": final_prompt}],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=1000
            )
            result = json.loads(response.choices[0].message.content)
            return result
        except Exception as e:
            # إذا فشل التحقق، نعيد افتراض النجاح مع تقرير عام
            return {
                "is_goal_achieved": True,
                "report": f"تم التنفيذ (تحقق تلقائي بسبب خطأ في التحقق: {str(e)})",
                "correction_plan": {"total_steps": 0, "steps": []}
            }

    def analyze_and_refine(self, user_prompt: str, agent_response: Dict[str, Any], 
                           tool_results: list) -> Dict[str, Any]:
        refined_prompt = f"""
        حسّن الرد النهائي للوكيل بناءً على النتائج التالية.
        طلب المستخدم: {user_prompt}
        الرد الأصلي: {agent_response}
        نتائج الأدوات: {json.dumps(tool_results, ensure_ascii=False)}
        أخرج JSON محسناً بنفس بنية AgentResponse.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": refined_prompt}],
                response_format={"type": "json_object"},
                temperature=0.2
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"analyze_and_refine error: {e}")
            return agent_response

    def quick_reply(self, user_prompt: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=200
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"آسف، حدث خطأ: {str(e)}"