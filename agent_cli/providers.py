"""LLM provider implementations."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Iterator, Optional
from openai import OpenAI
from agent_cli.errors import APIError


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def get_client(self, config: Dict[str, Any]) -> Any:
        """Get a client for the provider.
        
        Args:
            config: Provider configuration

        Returns:
            Any: Provider-specific client
        """
        pass
    
    @abstractmethod
    def create_chat_completion(self, client: Any, messages: List[Dict[str, str]], 
                             stream: bool = True) -> Any:
        """Create a chat completion.
        
        Args:
            client: Provider client
            messages: List of message dictionaries
            stream: Whether to stream the response

        Returns:
            Any: The response from the provider
        """
        pass
        

class DeepseekProvider(LLMProvider):
    """Deepseek API provider."""
    
    def get_client(self, config: Dict[str, Any]) -> OpenAI:
        """Get an OpenAI client configured for Deepseek.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            OpenAI: Configured client
        """
        try:
            return OpenAI(api_key=config['api_key'], base_url=config['base_url'])
        except Exception as e:
            raise APIError(f"Failed to initialize Deepseek client: {e}")
    
    def create_chat_completion(self, client: OpenAI, messages: List[Dict[str, str]], 
                             stream: bool = True) -> Any:
        """Create a chat completion using Deepseek.
        
        Args:
            client: OpenAI client
            messages: List of message dictionaries
            stream: Whether to stream the response
            
        Returns:
            Any: The response from Deepseek
        """
        try:
            return client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                stream=stream
            )
        except Exception as e:
            raise APIError(f"Deepseek API error: {e}")


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""
    
    def get_client(self, config: Dict[str, Any]) -> OpenAI:
        """Get an OpenAI client.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            OpenAI: Configured client
        """
        try:
            return OpenAI(api_key=config['api_key'], base_url=config['base_url'])
        except Exception as e:
            raise APIError(f"Failed to initialize OpenAI client: {e}")
    
    def create_chat_completion(self, client: OpenAI, messages: List[Dict[str, str]], 
                             stream: bool = True, model: Optional[str] = None) -> Any:
        """Create a chat completion using OpenAI.
        
        Args:
            client: OpenAI client
            messages: List of message dictionaries
            stream: Whether to stream the response
            model: Model to use (default: gpt-3.5-turbo)
            
        Returns:
            Any: The response from OpenAI
        """
        try:
            return client.chat.completions.create(
                model=model or "gpt-3.5-turbo",
                messages=messages,
                stream=stream
            )
        except Exception as e:
            raise APIError(f"OpenAI API error: {e}")


def get_provider(provider_name: str) -> LLMProvider:
    """Get a provider instance by name.
    
    Args:
        provider_name: Name of the provider
        
    Returns:
        LLMProvider: The provider instance
        
    Raises:
        ValueError: If provider is unknown
    """
    providers = {
        "deepseek": DeepseekProvider(),
        "openai": OpenAIProvider()
    }
    
    if provider_name.lower() not in providers:
        raise ValueError(f"Unknown provider: {provider_name}")
    
    return providers[provider_name.lower()]