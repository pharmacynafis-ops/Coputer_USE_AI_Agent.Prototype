# Implementation of Option 3: Dynamic Tool Loading with Pydantic Models

## Overview
This document describes the implementation of Option 3 to fix the Pydantic JSON schema warnings by creating a proper approach for dynamic tools with Pydantic models.

## Changes Made

### 1. Created New Module: dynamic_tool_loader.py
A new module was created to handle dynamic tool loading with proper Pydantic models. This module includes:

#### Function: parse_function_signature(code: str)
- Parses the function signature from the sample code string
- Extracts function name, parameters, and return type
- Handles parameter types, default values, and required/optional flags
- Uses Python's AST (Abstract Syntax Tree) for safe parsing

#### Function: create_pydantic_model_for_tool(func_name: str, parameters: List[Dict[str, Any]])
- Creates a Pydantic BaseModel class for a tool's parameters
- Maps string types to Python types (str, int, float, bool, list, dict, Any)
- Handles required and optional parameters with appropriate defaults
- Creates unique model names for each tool

#### Function: load_dynamic_tools_from_registry()
- Loads dynamic tools from tools_registry.json with proper Pydantic models
- For each tool:
  1. Parses the function signature
  2. Creates a Pydantic model for the tool's parameters
  3. Executes the function code safely
  4. Stores the function, model, parameters, and description
- Returns a dictionary with complete tool information

#### Function: register_dynamic_tools_with_agent(agent, dynamic_tools)
- Registers dynamic tools with a pydantic_ai Agent
- Creates wrapper functions that validate parameters using Pydantic models
- Ensures proper parameter validation before calling the original function

### 2. Updated server.py
The server.py file was updated to use the new dynamic_tool_loader module:

#### Changes:
1. Added import for the new module:
   ```python
   from dynamic_tool_loader import load_dynamic_tools_from_registry
   ```

2. Updated the create_agent function to:
   - Use the new load_dynamic_tools_from_registry() function
   - Extract both functions and models from the loaded tools
   - Build the system prompt with proper tool descriptions
   - Register dynamic tools with proper parameter handling

3. Modified the UseToolModel to use a simple default instead of default_factory:
   ```python
   arguments: Dict[str, Any] = Field(default={})
   ```

## How It Works

1. When the server starts, it loads dynamic tools from tools_registry.json
2. For each tool:
   - The function signature is parsed using AST
   - A Pydantic model is created for the tool's parameters
   - The function code is executed in a safe namespace
   - The function, model, and metadata are stored together

3. When a tool is called:
   - The parameters are validated using the Pydantic model
   - The validated parameters are passed to the original function
   - The result is returned to the caller

## Benefits

1. **Eliminates Warnings**: No more PydanticJsonSchemaWarning about non-serializable defaults
2. **Type Safety**: Proper type checking for all tool parameters
3. **Validation**: Automatic validation of parameter values
4. **Documentation**: Clear parameter definitions with types and descriptions
5. **Error Handling**: Better error messages when parameters are invalid
6. **Maintainability**: Cleaner code structure with separation of concerns

## Testing

To test the implementation:

1. Replace the original server.py with server_new.py
2. Run the server: `python server_new.py`
3. Verify that no PydanticJsonSchemaWarning appears
4. Test the dynamic tools (e.g., create_new_folder) to ensure they work correctly

## Notes

- The implementation maintains backward compatibility with existing code
- The dynamic tool loader is designed to be extensible for future enhancements
- Error handling is included to gracefully handle invalid tool definitions
- The solution follows best practices for dynamic code execution with proper validation
