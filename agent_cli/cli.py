"""Command-line interface for Agent CLI."""

import sys
import argparse
import os
import json
import subprocess
from typing import List, Optional, Dict, Any, Tuple

from agent_cli.config import ConfigManager
from agent_cli.providers import get_provider, LLMProvider
from agent_cli.chat import ChatSession
from agent_cli.utils import stream_response, get_input_safely, reopen_tty
from agent_cli.errors import AgentCLIError, APIError


def print_help():
    """Print help information for interactive mode."""
    print("\n=== Agent CLI Help ===")
    print("Available commands:")
    print("  help          - Show this help message")
    print("  clear         - Clear conversation history")
    print("  exit, quit    - Exit the program")
    print("  !config       - Show current configuration")
    print("  !system TEXT  - Change system prompt for current session")
    print("  !save PATH    - Save conversation history to file")
    print("  !load PATH    - Load conversation history from file")
    print("  !provider NAME - Switch provider")
    print("  !model NAME   - Switch model")
    print("  !apikey KEY   - Update API key in config file")
    print("  !bash COMMAND - Execute bash command and include output in chat")
    print("  !file PATH... - Load one or more files and discuss their content")
    print("\nUsage tips:")
    print("  - Press Ctrl+C to interrupt a long response")
    print("  - Use pipes to process file content: cat file.txt | agent")
    print("  - Add options to process file with instructions: cat file.txt | agent summarize this")
    print("  - Execute commands and discuss results: !bash ls -la")
    print("  - Analyze multiple files: !file file1.py file2.py \"path with spaces.txt\"")
    print("==============================\n")


def show_config(config: Dict[str, Any]):
    """Show current configuration.
    
    Args:
        config: Current configuration dictionary
    """
    print("\n=== Current Configuration ===")
    # Hide full API key for security
    if "api_key" in config:
        api_key = config["api_key"]
        masked_key = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else "****"
        config_display = {**config, "api_key": masked_key}
    else:
        config_display = config
        
    for key, value in config_display.items():
        print(f"  {key}: {value}")
    print("==============================\n")


def execute_bash_command(command: str) -> Tuple[bool, str, str]:
    """Execute a bash command and return its output.
    
    Args:
        command: Bash command to execute
        
    Returns:
        Tuple[bool, str, str]: Success status, output (stdout+stderr), error message
    """
    if not command:
        return False, "", "No command specified"
    
    try:
        # Run the command in a shell
        process = subprocess.Popen(
            command, 
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            executable='/bin/bash'
        )
        
        # Get output
        stdout, stderr = process.communicate(timeout=60)  # 60 second timeout
        
        # Combine stdout and stderr
        output = stdout
        if stderr:
            if output:
                output += "\n"
            output += f"Error output: {stderr}"
        
        return process.returncode == 0, output, stderr
        
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out after 60 seconds"
    except Exception as e:
        return False, "", f"Error executing command: {e}"


def handle_bash_command(command: str, session: ChatSession) -> None:
    """Execute a bash command and add the result to the conversation.
    
    Args:
        command: Bash command to execute
        session: Chat session
    """
    if not command:
        print("Please specify a command: !bash ls -la")
        return
        
    print(f"Executing: {command}")
    print("-" * 40)
    
    success, output, error = execute_bash_command(command)
    
    if not success and not output:
        print(f"Command failed: {error}")
        return
    
    # Display output to user
    if output:
        print(output)
    
    print("-" * 40)
    
    # Prepare the command result part
    command_result = f"I executed the following bash command:\n```bash\n{command}\n```\n\nHere's the output:\n```\n{output}\n```\n\n"
    
    # Ask user for additional instructions
    additional_prompt = input("\033[1;34mYour prompts: \033[0m").strip()
    
    # Combine the command result with any additional instructions
    if additional_prompt:
        full_prompt = f"{command_result}{additional_prompt}"
    else:
        full_prompt = f"{command_result}Please help me understand or work with this output."
    
    # Add to conversation
    try:
        # print("Sending command and output to AI...")
        response = session.get_response(full_prompt, stream=True)
        print("\033[1;33mAI: \033[0m", end="", flush=True)
        reply = stream_response(response, session)
        if reply:
            session.add_message("assistant", reply)
    except APIError as e:
        print(f"\n[Error] {e}")
    except KeyboardInterrupt:
        print("\n[Interrupted]")


def update_api_key(config_manager: ConfigManager, config: Dict[str, Any], api_key: str) -> None:
    """Update API key in configuration and save to file.
    
    Args:
        config_manager: Configuration manager instance
        config: Current configuration dictionary
        api_key: New API key
    """
    if not api_key:
        print("Please provide an API key: !apikey YOUR_API_KEY_HERE")
        return
        
    # Update in memory config
    config["api_key"] = api_key
    
    # Find the config file path
    if hasattr(config_manager, 'last_config_path') and config_manager.last_config_path:
        config_path = config_manager.last_config_path
    else:
        config_path = config_manager.get_default_config_path()
    
    # Save to file
    try:
        # Read existing config first (to preserve any comments or formatting)
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
            else:
                file_config = {}
        except json.JSONDecodeError:
            file_config = {}
        
        # Update and save
        file_config["api_key"] = api_key
        
        # Ensure all config values are saved
        for key, value in config.items():
            if key not in file_config:
                file_config[key] = value
                
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(file_config, f, ensure_ascii=False, indent=4)
            
        print(f"API key updated and saved to {config_path}")
        print("New configuration will be used for future sessions and new API calls.")
        
        # Note about restarting session
        if hasattr(config_manager, 'last_provider_name') and config_manager.last_provider_name:
            print(f"To apply the new API key to this session, use: !provider {config['provider']}")
    except Exception as e:
        print(f"Error saving configuration: {e}")


def change_system_prompt(session: ChatSession, prompt_text: str) -> None:
    """Change the system prompt for the current session.
    
    Args:
        session: Chat session
        prompt_text: New system prompt text
    """
    if not prompt_text:
        print("System prompt cannot be empty. No changes made.")
        return
        
    session.system_prompt = prompt_text
    session.clear_history()  # Reset with new system prompt
    print(f"System prompt changed to: \"{prompt_text}\"")
    print("Conversation history has been cleared with the new prompt.")


def save_conversation(session: ChatSession, filepath: str) -> None:
    """Save conversation history to a file.
    
    Args:
        session: Chat session
        filepath: Path to save the conversation
    """
    if not filepath:
        print("Please specify a file path: !save /path/to/file.txt")
        return
        
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            for i, msg in enumerate(session.history):
                if i == 0 and msg["role"] == "system":
                    f.write(f"# System: {msg['content']}\n\n")
                elif msg["role"] == "user":
                    f.write(f"## User:\n{msg['content']}\n\n")
                elif msg["role"] == "assistant":
                    f.write(f"## Assistant:\n{msg['content']}\n\n")
        print(f"Conversation saved to {filepath}")
    except Exception as e:
        print(f"Error saving conversation: {e}")


def load_conversation(session: ChatSession, filepath: str) -> None:
    """Load conversation history from a file.
    
    Currently just a placeholder - would need to implement a parser
    for the saved conversation format.
    
    Args:
        session: Chat session
        filepath: Path to load the conversation from
    """
    print("Loading conversations from files is not yet implemented.")
    # This would require parsing the saved file format and reconstructing 
    # the conversation history - will leave as an exercise for future expansion


def switch_provider(session: ChatSession, config: Dict[str, Any], provider_name: str) -> None:
    """Switch to a different provider.
    
    Args:
        session: Current chat session
        config: Configuration dictionary
        provider_name: Name of provider to switch to
    """
    if not provider_name:
        print("Please specify a provider: !provider deepseek|openai")
        return
        
    try:
        provider_name = provider_name.lower()
        # Update config
        config["provider"] = provider_name
        
        # Set default model for the provider if not specified
        if provider_name == "deepseek":
            if config.get("model", "").startswith("gpt-"):
                config["model"] = "deepseek-chat"
        elif provider_name == "openai":
            if config.get("model", "") == "deepseek-chat":
                config["model"] = "gpt-3.5-turbo"
                
        # Get new provider and recreate session
        provider = get_provider(provider_name)
        new_session = ChatSession(provider, config)
        
        # Copy history if any (except system message)
        if len(session.history) > 1:
            for msg in session.history[1:]:
                new_session.add_message(msg["role"], msg["content"])
                
        # Replace session reference (this is a bit hacky but works for this demo)
        session.__dict__.update(new_session.__dict__)
        
        print(f"Switched to {provider_name} provider with model {config['model']}")
    except ValueError as e:
        print(f"Error: {e}")


def switch_model(session: ChatSession, config: Dict[str, Any], model_name: str) -> None:
    """Switch to a different model.
    
    Args:
        session: Current chat session
        config: Configuration dictionary
        model_name: Name of model to switch to
    """
    if not model_name:
        print("Please specify a model: !model MODEL_NAME")
        return
        
    config["model"] = model_name
    session.model = model_name
    print(f"Switched to model: {model_name}")
    print("Note: History is preserved, but model capabilities may differ")


def read_file_content(file_path: str) -> Tuple[bool, str, str]:
    """Read content from a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Tuple[bool, str, str]: Success status, file content, error message
    """
    try:
        with open(os.path.expanduser(file_path), 'r', encoding='utf-8', errors='replace') as file:
            content = file.read()
        return True, content, ""
    except Exception as e:
        return False, "", f"Error reading file: {e}"


def handle_file_command(args: str, session: ChatSession) -> None:
    """Load files and add their content to the conversation with user prompts.
    
    Args:
        args: Command arguments containing file paths and optional instructions
        session: Chat session
    """
    if not args:
        print("Please specify at least one file path: !file path/to/file.txt [path/to/another.py]")
        return
        
    # Parse args - extract file paths (supporting quoted paths with spaces)
    import shlex
    try:
        paths = shlex.split(args)
    except Exception:
        # Fallback to simple splitting if shlex fails
        paths = args.split()
    
    if not paths:
        print("No valid file paths provided.")
        return
    
    # Read all files
    file_contents = []
    for path in paths:
        print(f"Loading file: {path}")
        success, content, error = read_file_content(path)
        
        if not success:
            print(f"Error: {error}")
            continue
            
        # Get file extension for syntax highlighting
        _, ext = os.path.splitext(path)
        ext = ext[1:] if ext else ""  # Remove leading dot
        
        if not ext:
            file_contents.append(f"# Content of {path}:\n\n{content}\n")
        else:
            file_contents.append(f"# Content of {path}:\n\n```{ext}\n{content}\n```\n")
    
    if not file_contents:
        print("No files were successfully loaded.")
        return
    
    # Combine all file contents
    combined_content = "\n\n".join(file_contents)
    
    # Show a preview
    preview_length = 200
    content_preview = combined_content[:preview_length] + "..." if len(combined_content) > preview_length else combined_content
    print("\nPreview of loaded content:")
    print("-" * 40)
    print(content_preview)
    print("-" * 40)
    
    # Ask user for instructions
    print(f"Loaded {len(file_contents)} file(s). What would you like to ask or instruct about these files?")
    user_prompt = input("\033[1;34mYour prompts: \033[0m").strip()
    
    if not user_prompt:
        user_prompt = "Please analyze these files and provide your observations."
    
    # Create full prompt
    full_prompt = f"{combined_content}\n\n{user_prompt}"
    
    # Add to conversation and get response
    try:
        print("Sending files and instructions to AI...")
        response = session.get_response(full_prompt, stream=True)
        print("\033[1;33mAI: \033[0m", end="", flush=True)
        reply = stream_response(response, session)
        if reply:
            session.add_message("assistant", reply)
    except APIError as e:
        print(f"\n[Error] {e}")
    except KeyboardInterrupt:
        print("\n[Interrupted]")

def handle_special_command(cmd: str, args: str, session: ChatSession, config: Dict[str, Any], config_manager: ConfigManager) -> bool:
    """Handle special commands that start with !.
    
    Args:
        cmd: Command name
        args: Command arguments
        session: Chat session
        config: Configuration dictionary
        config_manager: Configuration manager instance
        
    Returns:
        bool: True if command was handled, False otherwise
    """
    if cmd == "!config":
        show_config(config)
        return True
    elif cmd == "!system":
        change_system_prompt(session, args)
        return True
    elif cmd == "!save":
        save_conversation(session, args)
        return True
    elif cmd == "!load":
        load_conversation(session, args)
        return True
    elif cmd == "!provider":
        switch_provider(session, config, args)
        return True
    elif cmd == "!model":
        switch_model(session, config, args)
        return True
    elif cmd == "!apikey":
        update_api_key(config_manager, config, args)
        return True
    elif cmd == "!bash" or cmd == "!sh" or cmd == "!cmd":
        handle_bash_command(args, session)
        return True
    elif cmd == "!file" or cmd == "!files":
        handle_file_command(args, session)
        return True
    return False


def handle_pipe_input(args: argparse.Namespace, session: ChatSession) -> None:
    """Handle piped input.
    
    Args:
        args: Command line arguments
        session: Chat session
    """
    file_content = sys.stdin.read().strip()
    user_prompt = " ".join(args.prompt).strip() if args.prompt else ""

    if not file_content:
        print("\033[1;33mWarning:\033[0m No input received from pipe. The previous command may have failed or not produced any output.")
        print("If the previous command produced error messages, you can redirect stderr to stdout using:")
        print("  previous_command 2>&1 | agent")
        return
    
    if user_prompt:
        prompt = f"{file_content}\n\n{user_prompt}"
    else:
        prompt = file_content

    if not prompt:
        return

    try:
        response = session.get_response(prompt, stream=True)
        print("\033[1;33mAI: \033[0m", end="", flush=True)
        reply = stream_response(response, session)
        if reply:
            session.add_message("assistant", reply)
    except APIError as e:
        print(f"\n[Error] {e}")
    except KeyboardInterrupt:
        print("\nEntering interactive mode.")
        interactive_mode(session, config_manager)


def interactive_mode(session: ChatSession, config_manager: ConfigManager) -> None:
    """Run interactive chat mode.
    
    Args:
        session: Chat session
        config_manager: Configuration manager instance
    """
    config = session.config  # Get config from session
    # print("Welcome to Agent CLI Chat. Type 'help' for available commands, 'exit' or 'quit' to leave.\n")
    
    while True:
        prompt = get_input_safely()
        
        if not prompt:
            continue
            
        # Handle exit commands
        if prompt.lower() in ["exit", "quit"]:
            print("Session ended.")
            break
            
        # Handle help command
        if prompt.lower() == "help":
            print_help()
            continue
            
        # Handle clear command
        if prompt.lower() == "clear":
            session.clear_history()
            print("Chat history cleared.")
            continue
            
        # Handle special commands (starting with !)
        if prompt.startswith("!"):
            parts = prompt.split(maxsplit=1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            if handle_special_command(cmd, args, session, config, config_manager):
                continue

        # Handle normal prompt
        try:
            response = session.get_response(prompt, stream=True)
            print("\033[1;33mAI: \033[0m", end="", flush=True)
            reply = stream_response(response, session)
            if reply:
                session.add_message("assistant", reply)
        except APIError as e:
            print(f"\n[Error] {e}")
        except KeyboardInterrupt:
            print("\n[Interrupted. You can ask a new question.]")


def main() -> None:
    """Main entry point for the CLI application."""
    parser = argparse.ArgumentParser(description="Agent CLI - Chat with various LLM providers")
    parser.add_argument('--config', type=str, default=None, help='Specify config file path')
    parser.add_argument('--provider', type=str, default=None, help='LLM provider to use (overrides config)')
    parser.add_argument('--model', type=str, default=None, help='Model to use (overrides config)')
    parser.add_argument('--system', type=str, default=None, help='Override system prompt')
    parser.add_argument('--version', action='store_true', help='Show version information')
    parser.add_argument('prompt', nargs='*', help='Prompt text (when used with pipe input)')
    args = parser.parse_args()
    
    try:
        # Show version and exit
        if args.version:
            from agent_cli import __version__
            print(f"Agent CLI version {__version__}")
            return
            
        # Load configuration
        config_manager = ConfigManager()
        config = config_manager.load_config(args.config)
        
        # Store the config path for later use (for API key updates)
        if args.config:
            config_manager.last_config_path = args.config
        else:
            config_manager.last_config_path = (
                "config.json" if os.path.exists("config.json") 
                else config_manager.get_default_config_path()
            )
        
        # Override config from command line
        if args.provider:
            config["provider"] = args.provider
        if args.model:
            config["model"] = args.model
        if args.system:
            config["system_prompt"] = args.system
        
        # Save provider name for later reference
        config_manager.last_provider_name = config["provider"]
        
        # Get provider
        provider = get_provider(config["provider"])
        
        # Create session
        session = ChatSession(provider, config)
        
        # Handle pipe input or start interactive mode
        if not sys.stdin.isatty():
            handle_pipe_input(args, session)
            # After processing pipe input, try to reopen terminal for interactive mode
            reopen_tty()
            interactive_mode(session, config_manager)
        else:
            interactive_mode(session, config_manager)
            
    except AgentCLIError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()