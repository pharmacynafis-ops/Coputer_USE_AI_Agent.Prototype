from flask import Flask, request, jsonify, render_template, Response, redirect
import json
import os
import time
import subprocess
import shlex
import uuid
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from dotenv import load_dotenv
from smartThinking import SmartThinking
from steps_planner import StepsPlanner
from context_owner import ContextOwner
from long_term_memory import LongTermMemory
from request_classifier import RequestClassifier
import task_router
from routes import chat_route, knowledge_route, development_route, automation_route, security_route, debug_route, analysis_route, research_route
from threading import Lock
from datetime import datetime
from scope_manager import ScopeManager
from add_new_tool import ToolCreator
from dynamic_tool_loader import load_dynamic_tools_from_registry
from security.validator import authorize_tool_execution
from automation.sandbox_runner import sandbox_executor
from flask_socketio import SocketIO, emit
from automation.sandbox_runner import start_interactive_terminal, write_to_terminal, close_terminal
import threading
from automation.validator import validate_terminal_input


load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

HISTORY_FILE = "chat_history.json"
STEPS_LOG_FILE = "steps_log.json"

request_lock = Lock()
# Legacy global single-request guard kept for backwards-compatibility.
# New per-session locks allow concurrent requests for different sessions.
is_processing = False
# Maps session_id -> Lock() to allow per-session concurrency
session_locks = {}
# Protects access to the session_locks map
session_locks_lock = Lock()
# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Expose the final system prompt variable for external inspection and reuse.
# This corresponds to the symbolic name #sym:final_system_prompt requested by the user.
sym_final_system_prompt = None

@socketio.on('start_terminal')
def handle_start_terminal(data):
    cwd = data.get('cwd', None)
    session_id, process = start_interactive_terminal(cwd)
    
    emit('terminal_started', {'session_id': session_id})
    
    # Stream stdout
    def read_stream(stream, event_name):
        while True:
            line = stream.readline()
            if not line and process.poll() is not None:
                break
            if line:
                socketio.emit(event_name, {'session_id': session_id, 'data': line})
    
    # Start threads to stream stdout and stderr without blocking
    threading.Thread(target=read_stream, args=(process.stdout, 'terminal_output'), daemon=True).start()
    threading.Thread(target=read_stream, args=(process.stderr, 'terminal_error'), daemon=True).start()

@socketio.on('terminal_input')
def handle_terminal_input(data):
    session_id = data.get('session_id')
    user_input = data.get('input', '')
    
    # 1. Validate the agent's input against Windows destructive patterns
    validation = validate_terminal_input(user_input)
    if not validation.get('allowed', False):
        # 2. Send the rejection back to the frontend terminal so the agent sees it failed
        socketio.emit('terminal_error', {
            'session_id': session_id, 
            'data': f"\r\n[SECURITY BLOCKED]: {validation.get('reason')}\r\n"
        })
        return # Abort writing to stdin

    # 3. Only write if safe
    write_to_terminal(session_id, user_input)

@socketio.on('stop_terminal')
def handle_stop_terminal(data):
    session_id = data.get('session_id')
    close_terminal(session_id)

# Replace app.run() with socketio.run()


def can_process_request(session_id: Optional[str] = None) -> bool:
    """Return True and acquire a lock for the request.

    If session_id is provided, try to acquire a per-session lock non-blocking
    so different sessions can be processed concurrently. If no session_id is
    provided, fall back to the legacy single-global-request guard.
    """
    global is_processing
    if session_id:
        # Ensure there's a lock object for this session
        with session_locks_lock:
            if session_id not in session_locks:
                session_locks[session_id] = Lock()
            lock = session_locks[session_id]
        # Try to acquire without blocking; caller should handle rejection
        return lock.acquire(blocking=False)

    # Legacy global lock behavior
    with request_lock:
        if is_processing:
            return False
        is_processing = True
        return True

def release_request(session_id: Optional[str] = None):
    """Release the lock acquired by can_process_request.

    If session_id is provided, release the per-session lock. Otherwise
    release the legacy global guard.
    """
    global is_processing
    if session_id:
        with session_locks_lock:
            lock = session_locks.get(session_id)
        if lock is not None and lock.locked():
            try:
                lock.release()
            except RuntimeError:
                # Already released or not owned; ignore to be robust
                pass
        return

    with request_lock:
        is_processing = False

long_term_memory = LongTermMemory()
scope_mgr = ScopeManager(long_term_memory)
context_owner = ContextOwner()

def safe_load_json(filepath, default=None):
    if not os.path.exists(filepath):
        return default if default is not None else []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"⚠️ ملف {filepath} تالف، يتم إعادة إنشائه.")
        backup = default if default is not None else []
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(backup, f, ensure_ascii=False, indent=2)
        return backup

def load_history():
    return safe_load_json(HISTORY_FILE, [])

def save_history(history):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def save_step_log(entry):
    logs = safe_load_json(STEPS_LOG_FILE, [])
    logs.append(entry)
    with open(STEPS_LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

class UseToolModel(BaseModel):
    tool_name: str = Field(description="Tool name: 'write_file', 'read_file', 'execute_command', 'redirect_to_scope_page', 'create_new_customization_tool','interactive_command', or 'none'")
    arguments: Dict[str, Any] = Field(default={})

class AgentResponse(BaseModel):
    reasoning: str = Field(description="Detailed step-by-step thinking")
    current_step: str = Field(description="Short action label")
    is_goal_completed: bool = Field(description="True only if goal fully achieved")
    use_tool: UseToolModel = Field(description="Tool to use")
    message_to_user: Optional[str] = Field(None, description="Message to show user")

def get_model(api_key=None):
    key = api_key or os.getenv("OPENROUTER_API_KEY")
    os.environ["OPENAI_API_KEY"] = key
    os.environ["OPENAI_BASE_URL"] = "https://openrouter.ai/api/v1"
    return OpenAIChatModel("openai/gpt-4o-mini")

def read_system_files(filepath):
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        if filepath.endswith('.json'):
            return json.load(f)
        return f.read()

system_instructions = read_system_files(os.path.join('Sample', 'system_instructions.md')) or "You are an autonomous engineering agent."
exists_tools = read_system_files(os.path.join('Sample', 'exists_tools.json')) or {}

def create_agent(api_key=None):
    model = get_model(api_key)

    def write_file_tool(path: str, content: str) -> str:
        try:
            dirpath = os.path.dirname(path)
            if dirpath and not os.path.exists(dirpath):
                os.makedirs(dirpath, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Success: File written at {path}"
        except Exception as e:
            return f"Error: {str(e)}"

    def read_file_tool(path: str) -> str:
        try:
            if not os.path.exists(path):
                return f"Error: {path} not found"
            with open(path, "r", encoding="utf-8") as f:
                return f"Content:\n{f.read()}"
        except Exception as e:
            return f"Error: {str(e)}"

    def execute_command_tool(command: str, timeout_seconds: int = 30) -> str:
        try:
            shell_internal = command.strip().lower().startswith(('if ', 'for ', 'cd ', 'set ', 'dir ', 'echo '))
            if shell_internal:
                result = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds, shell=True)
            else:
                args = shlex.split(command)
                result = subprocess.run(args, capture_output=True, text=True, timeout=timeout_seconds, shell=False)
            output = result.stdout
            if result.stderr:
                output += f"\n[STDERR]: {result.stderr}"
            if result.returncode != 0:
                output += f"\n[Exit {result.returncode}]"
            return output.strip() or "[No output]"
        except subprocess.TimeoutExpired:
            return "Error: Command timeout"
        except Exception as e:
            return f"Error: {str(e)}"

    def redirect_to_scope_page_tool() -> str:
        return "__REDIRECT_TO_SCOPE_PAGE__"

    def create_new_customization_tool_tool(missing_tool: str, user_prompt: str) -> str:
        creator = ToolCreator(api_key=os.getenv("OPENROUTER_API_KEY"))
        tool_details = creator.generate_tool_details(user_prompt, missing_tool)
        context_owner.pending_tool_data = {
            "missing_tool": missing_tool,
            "original_prompt": user_prompt,
            "tool_details": tool_details
        }
        return "__SHOW_TOOL_FORM__"

    dynamic_tools_data = load_dynamic_tools_from_registry()
    dynamic_tools = {name: data["function"] for name, data in dynamic_tools_data.items()}

    dynamic_tools_desc = ""
    for tool_name, tool_data in dynamic_tools_data.items():
        params = tool_data.get("parameters", [])
        valid_params = [p for p in params if p.get('name') and p.get('name').strip()]
        param_str = ", ".join([f"{p.get('name', '')}: {p.get('type', 'str')}" for p in valid_params])
        description = tool_data.get("description", "أداة ديناميكية مخصصة")
        dynamic_tools_desc += f"- {tool_name}({param_str}): {description}\n"
    # Current Workspace section
    current_workspace = "Unknown"
    try:
        # Access the nested dictionary: last_workspace_scope -> workspace_path
        scope_data = long_term_memory.user_profile.get("last_workspace_scope", {})
        current_workspace = scope_data.get("workspace_path", "Unknown")
    except Exception:
        pass
    final_system_prompt = f"""You are CompLoca.
CompLoca is not a chatbot. CompLoca is not a terminal wrapper. CompLoca is not a file manipulation assistant.
CompLoca is a Computer Operator.
Your responsibility is to understand user intent, maintain conversation context, operate the computer safely, and execute tasks with the same logical expectations a competent human operator would have.

## Current Scope Information:
- Current Workspace Path: {current_workspace}
- If the user asks about the current workspace folder, answer ONLY with the path mentioned above. Do not guess.
- If the user requests to change the workspace folder, immediately use the redirect_to_scope_page tool.

## Strict Rules:
- There is NO tool named find_the_current_workspace_folder. NEVER attempt to use it.
- If the user asks for the current workspace path, answer immediately with the path in the "Current Scope Information" section above ({current_workspace}). Do not say you cannot detect it, and do not use any tool to find it.
- If the user requests to change the workspace folder, immediately use the redirect_to_scope_page tool.
- For file operations, use write_file or read_file.
- For standard terminal commands, use execute_command.
- For interactive terminal commands explicitly requested by the user, use interactive_command.

## Available Tools:
- write_file(path, content): Write text content to a file.
- read_file(path): Read the content of a file.
- execute_command(command, timeout_seconds=30): Execute a non-interactive command in the terminal.
- interactive_command(command): Execute a command in an interactive terminal session. Use this when the user explicitly asks to run a command using interactive_command. Pass the command in the command parameter. Example: {{ "tool": "interactive_command", "arguments": {{ "command": "tree /f" }} }}
- redirect_to_scope_page(): A special tool that takes no parameters.
- create_new_customization_tool(missing_tool, user_prompt): Used when the user requests a tool that does not exist.
{dynamic_tools_desc}
## Important Rules:
- In every iteration, start by outputting detailed reasoning.
- If the user says something casual (greeting, simple question), use use_tool.tool_name = "none" and answer in message_to_user.
- For file operations, use write_file or read_file.
- For standard terminal commands, use execute_command.
- For interactive terminal commands, use interactive_command.
- Set is_goal_completed = true ONLY when the goal is fully achieved.
- When a file is not found, search the memory for previously created files.
- To create a new directory, DO NOT use the mkdir command via execute_command. Instead, create a .gitkeep file inside the desired directory using write_file (e.g., write_file(path="path/to/new_folder/.gitkeep", content="")), as write_file automatically creates parent directories.

## NEW TOOL: redirect_to_scope_page
- This tool takes no parameters.
- Use it when the user explicitly requests to change or modify the current workspace folder.

## NEW TOOL: create_new_customization_tool
- Used when the user asks to create a new tool, or when an existing tool fails repeatedly.
- You must pass missing_tool (the name of the requested tool) and user_prompt (the user's original request).

## Additional Instructions:
- Remember the file paths you have created previously and use them when needed.
- Avoid destructive commands (like rm -rf) unless explicitly requested by the user.
- Use timeouts for long-running commands.
"""
    # Save the prompt to the module-level symbolic variable so callers
    # and other parts of the system can reference it as #sym:final_system_prompt
    try:
        # assign to module-level name
        globals()['sym_final_system_prompt'] = final_system_prompt.strip()
    except Exception:
        pass

    agent = Agent[None, AgentResponse](
        model=model,
        system_prompt=final_system_prompt.strip(),
    )

    # Also attach the prompt to the Agent instance for easy access
    try:
        setattr(agent, 'system_prompt_text', final_system_prompt.strip())
    except Exception:
        pass

    @agent.tool_plain
    def write_file(path: str, content: str) -> str:
        return write_file_tool(path, content)

    @agent.tool_plain
    def read_file(path: str) -> str:
        return read_file_tool(path)

    @agent.tool_plain
    def execute_command(command: str, timeout_seconds: int = 30) -> str:
        return execute_command_tool(command, timeout_seconds)

    @agent.tool_plain
    def redirect_to_scope_page() -> str:
        return redirect_to_scope_page_tool()

    @agent.tool_plain
    def create_new_customization_tool(missing_tool: str, user_prompt: str) -> str:
        return create_new_customization_tool_tool(missing_tool, user_prompt)

    for tool_name, tool_data in dynamic_tools_data.items():
        tool_func = tool_data["function"]
        @agent.tool_plain
        def dynamic_wrapper(**kwargs):
            return tool_func(**kwargs)
        dynamic_wrapper.__name__ = tool_name

    tools_registry = {
        "write_file": write_file_tool,
        "read_file": read_file_tool,
        "execute_command": execute_command_tool,
        "redirect_to_scope_page": redirect_to_scope_page_tool,
        "create_new_customization_tool": create_new_customization_tool_tool,
    }
    for tool_name, tool_func in dynamic_tools.items():
        tools_registry[tool_name] = tool_func

    return agent, tools_registry

current_agent, current_tools = create_agent()
smart = SmartThinking()
ENABLE_REQUEST_CLASSIFIER = os.getenv("ENABLE_REQUEST_CLASSIFIER", "1") == "1"
classifier = RequestClassifier() if ENABLE_REQUEST_CLASSIFIER else None

def execute_tool_backend(tool_name: str, arguments: Dict[str, Any]) -> str:
    if tool_name == "none":
        return ""

    if tool_name == "read_file":
        if "path" not in arguments:
            return "Error: read_file requires 'path' argument"
        path = arguments["path"]
        if not scope_mgr.is_path_allowed(path):
            return f"Error: Access denied. Cannot read '{path}' because it's outside your workspace scope."
        return current_tools[tool_name](path=path)

    elif tool_name == "write_file":
        if "path" not in arguments or "content" not in arguments:
            return "Error: write_file requires 'path' and 'content' arguments"
        path = arguments["path"]
        if not scope_mgr.is_path_allowed(path):
            return f"Error: Access denied. Path '{path}' is outside your workspace scope."
        return current_tools[tool_name](path=path, content=arguments["content"])

    elif tool_name == "execute_command":
        if "command" not in arguments:
            return "Error: execute_command requires 'command' argument"
        timeout = arguments.get("timeout_seconds", 30)
        try:
            auth = authorize_tool_execution('execute_command', arguments, scope_mgr)
            if not auth.get('allowed', False):
                save_step_log({
                    "session_id": None,
                    "type": "security_denial",
                    "tool": "execute_command",
                    "arguments": arguments,
                    "reason": auth.get('reason'),
                    "timestamp": time.time()
                })
                return f"Error: Access denied by security policy ({auth.get('reason')})"
        except Exception as e:
            return f"Error: security check failed: {e}"

        try:
            return sandbox_executor('execute_command', arguments, scope_mgr)
        except Exception:
            try:
                return current_tools[tool_name](command=arguments["command"], timeout_seconds=timeout)
            except Exception as e:
                return f"Error: command execution failed: {e}"

    elif tool_name == "redirect_to_scope_page":
        return current_tools[tool_name]()

    elif tool_name == "create_new_customization_tool":
        if "missing_tool" not in arguments or "user_prompt" not in arguments:
            return "Error: create_new_customization_tool requires 'missing_tool' and 'user_prompt' arguments"
        return current_tools[tool_name](missing_tool=arguments["missing_tool"], user_prompt=arguments["user_prompt"])
    # Add this elif block inside execute_tool_backend() in server.py
    elif tool_name == "interactive_command":
        # Agent explicitly requests an interactive session
        session_id, process = start_interactive_terminal(cwd=scope_mgr.current_scope.workspace_path)
        
        # Write the agent's command
        command = arguments.get('command', '')
        write_to_terminal(session_id, command + '\n')
        
        # Note: You will need to capture the stream output and return it to the agent.
        # For simplicity, we return the session ID.
        return f"Interactive session {session_id} started. Command executed."


    elif tool_name in current_tools:
        return current_tools[tool_name](**arguments)

    return f"Unknown tool: {tool_name}"

@app.route('/api/set_scope', methods=['POST'])
def set_scope():
    answers = request.json
    scope = scope_mgr.establish_scope(answers)
    return jsonify({"status": "scope_established", "workspace": scope.workspace_path})

@app.route('/scope-setup')
def scope_setup():
    return render_template("interactive_scoping_analysis.html")

@app.route('/new-tool-form')
def new_tool_form():
    tool_data = getattr(context_owner, 'pending_tool_data', None)
    if not tool_data:
        return redirect('/')
    return render_template("new_tool_form.html", tool_data=tool_data)

@app.route('/api/save_new_tool', methods=['POST'])
def api_save_new_tool():
    data = request.json
    tool_data = getattr(context_owner, 'pending_tool_data', {})
    if not tool_data:
        return jsonify({"status": "error", "message": "No pending tool data"})

    final_tool = {
        "tool_name": data.get("tool_name", tool_data.get("tool_details", {}).get("tool_name")),
        "tool_description": data.get("tool_description", tool_data.get("tool_details", {}).get("tool_description")),
        "parameters": data.get("parameters", tool_data.get("tool_details", {}).get("parameters", [])),
        "sample_code": data.get("sample_code", tool_data.get("tool_details", {}).get("sample_code")),
        "example_usage": data.get("example_usage", tool_data.get("original_prompt", ""))
    }

    creator = ToolCreator(api_key=os.getenv("OPENROUTER_API_KEY"))
    result = creator.save_new_tool(final_tool)
    if hasattr(context_owner, 'pending_tool_data'):
        delattr(context_owner, 'pending_tool_data')
    return jsonify(result)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/history", methods=["GET"])
def get_history():
    return jsonify(load_history())

@app.route("/api/history", methods=["POST"])
def add_to_history():
    data = request.json
    history = load_history()
    history.append(data)
    save_history(history)
    return jsonify({"status": "ok"})

@app.route("/api/clear_history", methods=["POST"])
def clear_history():
    save_history([])
    return jsonify({"status": "ok"})

@app.route("/api/set_api_key", methods=["POST"])
def set_api_key():
    global current_agent, current_tools
    new_key = request.json.get("api_key")
    if not new_key:
        return jsonify({"error": "No key provided"}), 400
    os.environ["OPENROUTER_API_KEY"] = new_key
    smart.set_api_key(new_key)
    current_agent, current_tools = create_agent(new_key)
    return jsonify({"status": "API key updated"})

@app.route("/api/get_api_key_status", methods=["GET"])
def get_api_key_status():
    key = os.getenv("OPENROUTER_API_KEY")
    return jsonify({"has_key": bool(key), "key_preview": key[:10] + "..." if key else None})

@app.route("/api/steps_log", methods=["GET"])
def get_steps_log():
    return jsonify(safe_load_json(STEPS_LOG_FILE, []))

@app.route("/api/memory_search", methods=["POST"])
def memory_search():
    query = request.json.get("query", "")
    if not query:
        return jsonify({"error": "No query provided"}), 400
    results = context_owner.search_memory(query)
    return jsonify(results)

@app.route("/api/ask_user", methods=["POST"])
def ask_user():
    question = request.json.get("question", "")
    if not question:
        return jsonify({"error": "No question provided"}), 400
    return jsonify({"question": question, "awaiting_response": True})


@app.route("/api/preview_prompt", methods=["POST"])
def preview_prompt():
    """Return the system prompt and the constructed enhanced prompt for inspection.

    POST JSON: { "prompt": "...", "session_id": "..." }
    """
    # Robustly parse JSON/body to handle different clients (curl on Windows, browsers, etc.)
    data = None
    try:
        data = request.get_json(silent=True)
    except Exception:
        data = None

    if not data:
        # Try raw body
        raw = request.get_data(as_text=True)
        if raw:
            try:
                data = json.loads(raw)
            except Exception:
                # Try form data
                try:
                    data = request.form.to_dict() if request.form else {}
                except Exception:
                    data = {}
        else:
            data = {}

    user_prompt = (data or {}).get('prompt', '')
    if not user_prompt or not str(user_prompt).strip():
        return jsonify({"error": "No prompt provided or failed to parse JSON body"}), 400

    # System prompt (as stored)
    system_prompt = globals().get('sym_final_system_prompt') or ''

    # Historical and conversation context similar to /stream
    try:
        historical_context = long_term_memory.get_context_for_prompt(user_prompt) or ''
    except Exception:
        historical_context = ''

    recent_history = load_history()
    conversation_context = ""
    if recent_history:
        last_messages = recent_history[-10:] if len(recent_history) > 10 else recent_history
        conversation_context = "\n\n## المحادثة الأخيرة:\n"
        for msg in last_messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')[:500]
            conversation_context += f"- {role}: {content}\n"

    enhanced_prompt = f"{historical_context}{conversation_context}\n\n## طلب المستخدم الحالي:\n{user_prompt}"

    return jsonify({
        "system_prompt": system_prompt,
        "enhanced_prompt": enhanced_prompt,
    })

@app.route('/new_session', methods=['POST'])
def new_session():
    """
    Resets the current session context (short-term memory) 
    while preserving LongTermMemory (user profile, project history).
    """
    try:
        # 1. Clear the in-memory conversation history and session ID
        context_owner.conversation_history = []
        context_owner.session_id = None
        context_owner.failure_log = []
        context_owner.reset_refine_count()
        
        # 2. Clear the frontend chat history file
        save_history([])
        
        # 3. LongTermMemory remains completely untouched as it reads from persistent JSON files.
        
        return jsonify({
            "status": "success", 
            "message": "New session started. Short-term memory cleared, long-term memory preserved."
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/stream")
def stream():
    user_prompt = request.args.get("prompt", "")
    requested_session = request.args.get('session_id')
    if not user_prompt.strip():
        return Response("data: {\"error\": \"Empty prompt\"}\n\n", mimetype="text/event-stream")

    if not can_process_request(requested_session):
        return Response("data: {\"error\": \"⚠️ الوكيل مشغول حالياً بتنفيذ طلب سابق. يرجى الانتظار حتى اكتماله ثم إعادة المحاولة.\"}\n\n",
                       mimetype="text/event-stream", status=429)

    recent_history = load_history()
    skip, quick_reply_text = smart.should_skip_thinking(user_prompt, recent_history)
    if skip:
        def generate_skip():
            release_request(requested_session)
            yield f"data: {json.dumps({'type': 'skip', 'message': quick_reply_text, 'is_goal_completed': True})}\n\n"
        return Response(generate_skip(), mimetype="text/event-stream")

    def generate():
        try:
            session_id = context_owner.start_session(user_prompt)
            if not scope_mgr.has_valid_scope(user_prompt):
                yield f"data: {json.dumps({'type': 'need_scope', 'redirect': '/scope-setup'})}\n\n"
                return

            api_key = os.getenv("OPENROUTER_API_KEY")
            if not context_owner.session_id:
                yield f"data: {json.dumps({'type': 'session_start', 'session_id': session_id})}\n\n"
            else:
                # Append to the existing clean session
                context_owner.conversation_history.append({
                    "role": "user",
                    "content": user_prompt,
                    "timestamp": datetime.now().isoformat()
                })
                yield f"data: {json.dumps({'type': 'session_start', 'session_id': context_owner.session_id})}\n\n"

            historical_context = long_term_memory.get_context_for_prompt(user_prompt)
            recent_history = load_history()
            conversation_context = ""
            if recent_history:
                last_messages = recent_history[-10:] if len(recent_history) > 10 else recent_history
                conversation_context = "\n\n## المحادثة الأخيرة:\n"
                for msg in last_messages:
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')[:500]
                    conversation_context += f"- {role}: {content}\n"

            enhanced_prompt = f"{historical_context}{conversation_context}\n\n## طلب المستخدم الحالي:\n{user_prompt}"

            if ENABLE_REQUEST_CLASSIFIER and classifier:
                try:
                    classification = classifier.classify(user_prompt, recent_history)
                    save_step_log({
                        "session_id": session_id,
                        "type": "classification",
                        "classification": classification,
                        "timestamp": time.time()
                    })
                except Exception:
                    pass

            planner = StepsPlanner(api_key)
            workspace_path = scope_mgr.current_scope.workspace_path if scope_mgr.current_scope else os.getcwd()
            workspace_path = workspace_path.replace('\\', '/')
            plan = planner.create_plan(enhanced_prompt, workspace_path)
            yield f"data: {json.dumps({'type': 'plan', 'plan': plan})}\n\n"

            try:
                route_plan = task_router.route_plan(plan)
            except Exception:
                route_plan = None

            if route_plan and route_plan.get('segments'):
                segments = route_plan.get('segments', [])
            else:
                segments = [{"route": "chat", "steps": plan.get("steps", [])}]

            if plan.get("total_steps", 0) == 0:
                try:
                    assistant_reply = smart.quick_reply(
                        f"الطلب التالي لا يبدو قابلاً للتنفيذ بأدوات النظام. اشرح لماذا لا توجد خطوات تنفيذية مرتكزة على الطلب التالي:\n\n{user_prompt}"
                    )
                except Exception:
                    assistant_reply = "لا توجد خطوات للتنفيذ."

                context_owner.conversation_history.append({
                    "role": "assistant",
                    "content": assistant_reply,
                    "timestamp": datetime.now().isoformat()
                })
                context_owner.save_conversation_to_session()
                try:
                    long_term_memory.update_interaction(user_prompt, assistant_reply, success=False)
                except Exception:
                    pass

                yield f"data: {json.dumps({'type': 'final', 'message': assistant_reply})}\n\n"
                return

            execution_log = []
            step_index = 0
            max_iterations = 25
            iteration = 0
            max_retries_per_step = 3
            retry_count = 0
            waiting_for_user = False

            for seg in segments:
                route_name = seg.get('route')
                handler = {
                    'chat': chat_route,
                    'knowledge': knowledge_route,
                    'development': development_route,
                    'automation': automation_route,
                    'security': security_route,
                    'debug': debug_route,
                    'analysis': analysis_route,
                    'research': research_route,
                }.get(route_name)

                session_context = {
                    'user_prompt': user_prompt,
                    'session_id': session_id,
                    'plan': plan,
                    'execution_log': execution_log,
                }

                if handler:
                    try:
                        pre = handler.handle_segment(seg, session_context, executor=None)
                    except Exception:
                        pre = None
                else:
                    pre = None

                if pre and not seg.get('steps'):
                    if pre.get('route') == 'chat' and pre.get('reply'):
                        yield f"data: {json.dumps({'type': 'final', 'message': pre.get('reply')})}\n\n"
                        continue

                seg_steps = seg.get('steps', [])
                si = 0
                while si < len(seg_steps) and iteration < max_iterations and not waiting_for_user:
                    iteration += 1
                    step = seg_steps[si]
                    step_number = step.get('step_number', step_index+1)
                    description = step.get("description", "")
                    tool_name = step.get("tool", "none")
                    arguments = step.get("arguments", {})

                    yield f"data: {json.dumps({'type': 'step_start', 'step_number': step_number, 'description': description, 'tool': tool_name})}\n\n"

                    try:
                        sec_check = security_route.handle_segment({'steps': [step]}, {'user_prompt': user_prompt})
                        denied = False
                        sec_reason = None
                        if sec_check and 'results' in sec_check and len(sec_check['results']) > 0:
                            res0 = sec_check['results'][0]
                            if not res0.get('allowed', True):
                                denied = True
                                sec_reason = res0.get('reason', 'denied by security policy')
                    except Exception:
                        denied = False

                    if denied:
                        tool_result = f"Error: Access denied by security policy ({sec_reason})"
                    else:
                        tool_result = execute_tool_backend(tool_name, arguments)

                    is_success = smart.verify_step(step, tool_result)
                    context_owner.update_after_step(step, tool_result, is_success)

                    step_record = {
                        "session_id": session_id, "user_prompt": user_prompt,
                        "step_number": step_number, "description": description,
                        "tool": tool_name, "arguments": arguments,
                        "result": tool_result, "success": is_success,
                        "timestamp": time.time()
                    }
                    execution_log.append(step_record)
                    save_step_log(step_record)

                    yield f"data: {json.dumps({'type': 'step_result', 'step_number': step_number, 'result': tool_result, 'success': is_success})}\n\n"

                    if not is_success:
                        retry_count += 1

                        is_stuck, stuck_reason = context_owner.is_stuck(step, tool_result)
                        if is_stuck:
                            memory_search = context_owner.search_memory(description)
                            question = context_owner.generate_help_question(step, tool_result, memory_search)
                            yield f"data: {json.dumps({'type': 'need_help', 'question': question, 'stuck_reason': stuck_reason})}\n\n"
                            waiting_for_user = True
                            break

                        if retry_count > max_retries_per_step:
                            yield f"data: {json.dumps({'type': 'step_failed', 'step_number': step_number, 'error': tool_result})}\n\n"
                            si += 1
                            step_index += 1
                            retry_count = 0
                            continue

                        context_owner.increment_refine_count()
                        refined_plan = planner.refine_plan(plan, step, tool_result, workspace_path)
                        new_steps = refined_plan.get("steps", [])
                        if new_steps:
                            seg_steps = seg_steps[:si] + new_steps + seg_steps[si+1:]
                            plan = refined_plan
                            yield f"data: {json.dumps({'type': 'plan_refined', 'plan': plan})}\n\n"
                            continue
                        else:
                            si += 1
                            step_index += 1
                            retry_count = 0
                            context_owner.reset_refine_count()
                    else:
                        retry_count = 0
                        si += 1
                        step_index += 1
                        context_owner.reset_refine_count()

            if waiting_for_user:
                yield f"data: {json.dumps({'type': 'awaiting_user', 'question': context_owner.generate_help_question(step, tool_result, {})})}\n\n"
            else:
                final_check = smart.final_verification(user_prompt, plan, execution_log)
                long_term_memory.update_interaction(user_prompt, final_check.get('report', ''), final_check.get('is_goal_achieved', False))
                for step in execution_log:
                    if step.get("tool") == "write_file":
                        long_term_memory.add_file_record(
                            step.get("arguments", {}).get("path", ""),
                            step.get("arguments", {}).get("content", ""),
                            session_id
                        )
                if final_check.get("is_goal_achieved", False):
                    yield f"data: {json.dumps({'type': 'final_success', 'report': final_check.get('report'), 'execution_log': execution_log})}\n\n"
                    save_history(load_history() + [{"role": "user", "content": user_prompt}, {"role": "assistant", "content": final_check.get('report', 'Done')}])
                else:
                    correction_plan = final_check.get("correction_plan")
                    if correction_plan and correction_plan.get("total_steps", 0) > 0:
                        yield f"data: {json.dumps({'type': 'plan', 'plan': correction_plan, 'is_correction': True})}\n\n"
                        correction_steps = correction_plan.get("steps", [])
                        correction_success = True
                        for step in correction_steps:
                            step_number = step.get("step_number", 0)
                            description = step.get("description", "")
                            tool_name = step.get("tool", "none")
                            arguments = step.get("arguments", {})
                            yield f"data: {json.dumps({'type': 'step_start', 'step_number': step_number, 'description': description, 'tool': tool_name})}\n\n"
                            tool_result = execute_tool_backend(tool_name, arguments)
                            is_success = smart.verify_step(step, tool_result)
                            step_record = {
                                "session_id": session_id, "user_prompt": user_prompt,
                                "step_number": step_number, "description": description,
                                "tool": tool_name, "arguments": arguments,
                                "result": tool_result, "success": is_success,
                                "timestamp": time.time()
                            }
                            execution_log.append(step_record)
                            save_step_log(step_record)
                            yield f"data: {json.dumps({'type': 'step_result', 'step_number': step_number, 'result': tool_result, 'success': is_success})}\n\n"
                            if not is_success:
                                correction_success = False
                                break
                        if correction_success:
                            yield f"data: {json.dumps({'type': 'final_success', 'report': 'تم التصحيح بنجاح: ' + final_check.get('report', ''), 'execution_log': execution_log})}\n\n"
                            save_history(load_history() + [{"role": "user", "content": user_prompt}, {"role": "assistant", "content": 'تم التصحيح بنجاح'}])
                        else:
                            yield f"data: {json.dumps({'type': 'final_failure', 'report': 'فشل التصحيح: ' + final_check.get('report', '')})}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'final_failure', 'report': final_check.get('report')})}\n\n"

            context_owner.save_conversation_to_session()
            if hasattr(context_owner, 'pending_tool_data'):
                delattr(context_owner, 'pending_tool_data')
        finally:
            release_request(requested_session)

    return Response(generate(), mimetype="text/event-stream")

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=8000, debug=True)
