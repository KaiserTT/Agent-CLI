"""Configuration management for Agent CLI."""

import os
import json
from typing import Dict, Any, Optional


class ConfigManager:
    """Manages configuration for the Agent CLI."""

    def __init__(self):
        """Initialize the config manager."""
        self.config = {}

    def get_default_config_path(self) -> str:
        """Get the default configuration file path.

        Returns:
            str: The path to the default configuration file.
        """
        home = os.path.expanduser("~")
        config_dir = os.path.join(home, ".agent_cli")
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        return os.path.join(config_dir, "config.json")

    def interactive_config_write(self, config_path: str) -> Dict[str, Any]:
        """Interactively create configuration file.

        Args:
            config_path: Path to write the configuration file to.

        Returns:
            Dict[str, Any]: The created configuration.
        """
        print(f"\nNo valid config file found. Let's create one.")
        
        # Get provider
        print("\nAvailable providers:")
        print("1. Deepseek")
        print("2. OpenAI")
        provider_choice = input("Select provider [1]: ").strip() or "1"
        
        if provider_choice == "1":
            provider = "deepseek"
            default_url = "https://api.deepseek.com"
            api_key_prompt = "Please enter your Deepseek API key: "
            base_url_prompt = f"Please enter your Deepseek API base URL [{default_url}]: "
        elif provider_choice == "2":
            provider = "openai"
            default_url = "https://api.openai.com/v1"
            api_key_prompt = "Please enter your OpenAI API key: "
            base_url_prompt = f"Please enter your OpenAI API base URL [{default_url}]: "
        else:
            print("Invalid choice. Using Deepseek as default.")
            provider = "deepseek"
            default_url = "https://api.deepseek.com"
            api_key_prompt = "Please enter your Deepseek API key: "
            base_url_prompt = f"Please enter your Deepseek API base URL [{default_url}]: "
            
        # Get API key
        api_key = input(api_key_prompt).strip()
        while not api_key or api_key.lower().startswith("please"):
            print("Invalid API key. Please try again.")
            api_key = input(api_key_prompt).strip()
            
        # Get base URL
        base_url = input(base_url_prompt).strip()
        if not base_url:
            base_url = default_url
            
        # Get default model
        if provider == "deepseek":
            default_model = "deepseek-chat"
        else:
            default_model = "gpt-3.5-turbo"
        
        model = input(f"Please enter the model to use [{default_model}]: ").strip()
        if not model:
            model = default_model
            
        # Get system prompt
        default_system_prompt = "You are a helpful assistant. Answer in Chinese."
        system_prompt = input(f"Enter system prompt [{default_system_prompt}]: ").strip()
        if not system_prompt:
            system_prompt = default_system_prompt
            
        config = {
            "provider": provider,
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
            "system_prompt": system_prompt
        }
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        
        print(f"Configuration saved to {config_path}.\n")
        return config

    def load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """Load configuration from file.

        Args:
            config_path: Optional path to configuration file. If None, will try to find config.

        Returns:
            Dict[str, Any]: The loaded configuration.
        """
        # Try to find config file
        if config_path and os.path.exists(config_path):
            config_file = config_path
        elif os.path.exists("config.json"):
            config_file = "config.json"
        else:
            default_path = self.get_default_config_path()
            if os.path.exists(default_path):
                config_file = default_path
            else:
                return self.interactive_config_write(default_path)
        
        # Load config file
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            # Validate config
            required_keys = ["api_key", "base_url"]
            if not all(key in config for key in required_keys) or not config.get("api_key") or config.get("api_key").lower().startswith("please"):
                print(f"Invalid configuration in {config_file}")
                return self.interactive_config_write(config_file)
                
            # Set defaults
            if "provider" not in config:
                config["provider"] = "deepseek"
            if "model" not in config:
                config["model"] = "deepseek-chat" if config["provider"] == "deepseek" else "gpt-3.5-turbo"
            if "system_prompt" not in config:
                config["system_prompt"] = "You are a helpful assistant. Answer in Chinese."
                
            return config
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading config file: {e}")
            return self.interactive_config_write(self.get_default_config_path())