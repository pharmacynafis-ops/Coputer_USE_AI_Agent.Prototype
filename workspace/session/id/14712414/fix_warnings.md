# Fix for Pydantic JSON Schema Warnings

## Issue Description
The warning "Default value <function create_new_folder at 0x000002F998385EE0> is not JSON serializable; excluding default from JSON schema [non-serializable-default]" is occurring in the server.py file when running the application.

## Root Cause
This warning appears in the `UseToolModel` class (line 82 in server.py) where there's a default factory for the `arguments` field:

```python
arguments: Dict[str, Any] = Field(default_factory=dict)
```

Pydantic is trying to serialize this default factory function to JSON schema, but function objects are not JSON serializable.

## Solution
To fix this warning, we need to modify the `UseToolModel` class in server.py to specify a different default value or configure Pydantic to handle this case properly.

### Option 1: Change the default value
Instead of using `default_factory=dict`, we can use a simple default value:

```python
arguments: Dict[str, Any] = Field(default={})
```

### Option 2: Configure Pydantic to ignore warnings
We can add configuration to Pydantic to ignore these specific warnings:

```python
import warnings
from pydantic import ConfigDict

# Add this before creating the model
warnings.filterwarnings("ignore", category="pydantic.json_schema.PydanticJsonSchemaWarning")

# Or configure the model with config option
class UseToolModel(BaseModel):
    model_config = ConfigDict(json_schema_extra={"exclude_defaults": True})
    arguments: Dict[str, Any] = Field(default_factory=dict)
```

### Option 3: Use a different approach for default values
We can use a lambda function or a different approach that doesn't trigger the warning:

```python
arguments: Dict[str, Any] = Field(default_factory=lambda: {})
```

## Recommended Fix
Option 1 is the simplest and most straightforward approach. Change line 82 in server.py from:
```python
arguments: Dict[str, Any] = Field(default_factory=dict)
```

to:
```python
arguments: Dict[str, Any] = Field(default={})
```

This will eliminate the warning while maintaining the same functionality.
