#!/usr/bin/env python3
"""
PreToolUse hook to ensure virtual environment is activated before bash commands.
Automatically prepends venv activation to all bash commands in this project.
"""
import json
import sys
import os
from pathlib import Path

def get_venv_activation_command():
    """Get the venv activation command for this project."""
    # Get the project root (where .claude directory is located)
    project_root = Path(__file__).parent.parent.parent
    venv_path = project_root / ".venv" / "bin" / "activate"

    if not venv_path.exists():
        # If venv doesn't exist, return empty string (no modification)
        return ""

    return f'source "{venv_path}" && '

def should_skip_activation(command: str) -> bool:
    """Check if command should skip venv activation."""
    # Skip if already activating venv
    if 'source' in command and 'activate' in command:
        return True

    # Skip if explicitly using system python
    if command.startswith('system python'):
        return True

    # Skip simple commands that don't need venv
    simple_commands = ['ls', 'pwd', 'cd', 'echo', 'cat', 'mkdir', 'rm', 'cp', 'mv', 'chmod', 'grep', 'find']
    first_word = command.strip().split()[0] if command.strip() else ""
    if first_word in simple_commands:
        return True

    return False

def main():
    try:
        # Read hook input from stdin
        input_data = json.load(sys.stdin)
        command = input_data.get('tool_input', {}).get('command', '')

        if not command or should_skip_activation(command):
            # No modification needed
            sys.exit(0)

        # Get the venv activation prefix
        venv_activation = get_venv_activation_command()

        if not venv_activation:
            # No venv found, don't modify
            sys.exit(0)

        # Prepend venv activation to the command
        new_command = venv_activation + command

        # Output JSON response to modify the tool call
        response = {
            "tool_input": {
                **input_data.get('tool_input', {}),
                "command": new_command
            }
        }

        print(json.dumps(response))
        sys.exit(0)

    except Exception as e:
        # Don't block command execution if hook fails
        print(f"Warning: venv activation hook failed: {e}", file=sys.stderr)
        sys.exit(0)

if __name__ == "__main__":
    main()
