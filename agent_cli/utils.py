"""Utility functions for Agent CLI."""

import os
import sys
from typing import Any, Dict, Optional

def stream_response(response: Any, session: Any) -> str:
    """Process and display a streaming response.
    
    Args:
        response: The streaming response
        session: Chat session
        
    Returns:
        str: The complete response text
    """
    full_response = ""
    try:
        for chunk in response:
            if hasattr(chunk.choices[0], "delta"):
                delta = chunk.choices[0].delta
                if hasattr(delta, "content") and delta.content:
                    content = delta.content
                    print(content, end="", flush=True)
                    full_response += content
        print()  # Add newline
        return full_response
    except KeyboardInterrupt:
        print("\n[Interrupted]")
        return full_response


def get_input_safely() -> str:
    """Get user input safely, handling potential input errors.
    
    Returns:
        str: The input text
    """
    try:
        return input("\033[1;34mYou: \033[0m").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye!")
        sys.exit(0)
    except Exception:
        print("\nError reading input. Please try again.")
        return ""


def reopen_tty():
    """Try to reopen the terminal for interactive mode after pipe input."""
    if not sys.stdin.isatty():
        try:
            sys.stdin = open('/dev/tty')
        except Exception:
            print("[Warning] Failed to reopen /dev/tty, interactive mode may not work as expected.")