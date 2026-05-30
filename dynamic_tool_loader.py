# dynamic_tool_loader.py
import json
import os
import ast
import inspect
from typing import Dict, Any, List, Callable, Optional, get_type_hints
from pydantic import BaseModel, create_model, Field
import warnings

def parse_function_signature(code: str) -> Dict[str, Any]:
    """
    Parse the function signature from the sample code.

    Args:
        code: The sample code string containing the function definition

    Returns:
        Dictionary with function name, parameters, and return type
    """
    try:
        # Parse the code as an AST
        tree = ast.parse(code)

        # Find the function definition
        func_def = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_def = node
                break

        if not func_def:
            return {}

        # Extract function name
        func_name = func_def.name

        # Extract parameters
        parameters = []
        defaults = {}
        for arg in func_def.args.args:
            param_name = arg.arg

            # Get type annotation if available
            param_type = "str"  # Default to str
            if arg.annotation:
                if isinstance(arg.annotation, ast.Name):
                    param_type = arg.annotation.id
                elif isinstance(arg.annotation, ast.Subscript):
                    # Handle complex types like Dict[str, Any]
                    if isinstance(arg.annotation.value, ast.Name):
                        param_type = arg.annotation.value.id

            # Check if there's a default value
            has_default = False
            default_idx = len(func_def.args.args) - len(func_def.args.defaults)
            arg_idx = func_def.args.args.index(arg)
            if arg_idx >= default_idx:
                has_default = True
                default_value = func_def.args.defaults[arg_idx - default_idx]
                # Try to evaluate the default value
                try:
                    if isinstance(default_value, ast.Constant):
                        defaults[param_name] = default_value.value
                    elif isinstance(default_value, ast.Num):
                        defaults[param_name] = default_value.n
                    elif isinstance(default_value, ast.Str):
                        defaults[param_name] = default_value.s
                    elif isinstance(default_value, ast.NameConstant):
                        defaults[param_name] = default_value.value
                    elif isinstance(default_value, ast.UnaryOp) and isinstance(default_value.op, ast.USub):
                        # Handle negative numbers
                        if isinstance(default_value.operand, ast.Num):
                            defaults[param_name] = -default_value.operand.n
                except:
                    pass

            parameters.append({
                "name": param_name,
                "type": param_type,
                "required": not has_default,
                "default": defaults.get(param_name)
            })

        return {
            "name": func_name,
            "parameters": parameters,
            "return_type": "str"  # Most tools return str
        }
    except Exception as e:
        print(f"Error parsing function signature: {e}")
        return {}

def create_pydantic_model_for_tool(func_name: str, parameters: List[Dict[str, Any]]) -> BaseModel:
    """
    Create a Pydantic model for a tool's parameters.

    Args:
        func_name: Name of the function (used for model name)
        parameters: List of parameter definitions

    Returns:
        Pydantic BaseModel class for the tool's parameters
    """
    fields = {}

    for param in parameters:
        param_name = param["name"]
        param_type = param["type"]
        param_required = param["required"]
        param_default = param.get("default")

        # Map string types to Python types
        type_mapping = {
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            "Any": Any,
        }

        python_type = type_mapping.get(param_type, str)

        # Create field with appropriate default
        if param_required:
            fields[param_name] = (python_type, Field(description=f"Parameter: {param_name}"))
        else:
            if param_default is not None:
                fields[param_name] = (python_type, Field(default=param_default, description=f"Parameter: {param_name} (optional)"))
            else:
                # For optional parameters without explicit defaults, use None
                fields[param_name] = (Optional[python_type], Field(default=None, description=f"Parameter: {param_name} (optional)"))

    # Create the model with a unique name
    model_name = f"{func_name.capitalize()}Params"
    return create_model(model_name, **fields)

def load_dynamic_tools_from_registry() -> Dict[str, Dict[str, Any]]:
    """
    Load dynamic tools from tools_registry.json with proper Pydantic models.

    Returns:
        Dictionary mapping tool names to their function and Pydantic model
    """
    registry_path = "tools_registry.json"
    if not os.path.exists(registry_path):
        return {}

    with open(registry_path, "r", encoding="utf-8") as f:
        dynamic_tools = json.load(f)

    loaded_tools = {}
    for tool_name, tool_info in dynamic_tools.items():
        sample_code = tool_info.get("sample_code", "")
        if not sample_code:
            print(f"⚠️ الأداة {tool_name} ليس لديها sample_code، يتم تخطيها")
            continue

        # Parse the function signature
        signature = parse_function_signature(sample_code)
        if not signature or signature.get("name") != tool_name:
            print(f"⚠️ فشل تحليل توقيع الأداة {tool_name}")
            continue

        # Create a Pydantic model for the tool's parameters
        try:
            pydantic_model = create_pydantic_model_for_tool(tool_name, signature.get("parameters", []))

            # Execute the function code
            namespace = {}
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                exec(sample_code, namespace)

            if tool_name in namespace:
                loaded_tools[tool_name] = {
                    "function": namespace[tool_name],
                    "model": pydantic_model,
                    "parameters": signature.get("parameters", []),
                    "description": tool_info.get("description", "")
                }
            else:
                print(f"⚠️ الدالة {tool_name} لم توجد في namespace بعد exec")
        except Exception as e:
            print(f"⚠️ فشل تحميل الأداة {tool_name}: {e}")

    return loaded_tools

def register_dynamic_tools_with_agent(agent, dynamic_tools: Dict[str, Dict[str, Any]]) -> None:
    """
    Register dynamic tools with a pydantic_ai Agent.

    Args:
        agent: The pydantic_ai Agent instance
        dynamic_tools: Dictionary of loaded dynamic tools
    """
    for tool_name, tool_info in dynamic_tools.items():
        tool_func = tool_info["function"]
        pydantic_model = tool_info["model"]

        # Create a wrapper that validates parameters using the Pydantic model
        def create_wrapper(func, model):
            def wrapper(**kwargs):
                try:
                    # Validate parameters using the Pydantic model
                    validated = model(**kwargs)
                    # Call the original function with validated parameters
                    return func(**validated.model_dump())
                except Exception as e:
                    return f"Error: {str(e)}"
            return wrapper

        # Register the tool with the agent
        wrapped_func = create_wrapper(tool_func, pydantic_model)
        wrapped_func.__name__ = tool_name

        # Use tool_plain decorator for simple tools
        @agent.tool_plain
        def dynamic_tool(**kwargs):
            return wrapped_func(**kwargs)

        # Set the function name for proper identification
        dynamic_tool.__name__ = tool_name
