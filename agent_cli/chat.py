"""Chat session management."""

from typing import Dict, Any, List, Optional
from agent_cli.providers import LLMProvider


class ChatSession:
    """Manages a chat session with an LLM provider."""
    
    def __init__(self, provider: LLMProvider, config: Dict[str, Any]):
        """Initialize a chat session.
        
        Args:
            provider: LLM provider
            config: Configuration dictionary
        """
        self.provider = provider
        self.client = provider.get_client(config)
        self.config = config
        self.history: List[Dict[str, str]] = []
        self.system_prompt = config.get("system_prompt", "You are a helpful assistant. Answer in Chinese.")
        self.model = config.get("model")
        self.initialize_history()
        
    def initialize_history(self) -> None:
        """Initialize or reset the chat history."""
        self.history = [{"role": "system", "content": self.system_prompt}]
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message to the chat history.
        
        Args:
            role: The role of the message sender (user, assistant, system)
            content: The message content
        """
        self.history.append({"role": role, "content": content})
    
    def get_response(self, prompt: str, stream: bool = True) -> Any:
        """Get a response from the LLM.
        
        Args:
            prompt: The user prompt
            stream: Whether to stream the response
            
        Returns:
            Any: The response from the provider
        """
        self.add_message("user", prompt)
        return self.provider.create_chat_completion(
            self.client, 
            self.history, 
            stream=stream
        )
    
    def clear_history(self) -> None:
        """Clear the chat history, keeping only the system prompt."""
        self.initialize_history()