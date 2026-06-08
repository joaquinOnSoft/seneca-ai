# -*- coding: utf-8 -*-
"""
Created on Sat May 30 06:36:37 2026

@author: NachoWorks
"""

import requests

class OllamaClient:
    def __init__(self, base_url="http://localhost:11434"):
        # Initialize the Ollama client with the base URL for the local Ollama server
        self.base_url = base_url

    def generate(self, model: str, prompt: str, context: list = None):
        """
        Generate a response using a specified Ollama model.

        Args:
            model (str): Name of the model to use (e.g., "llama3:8b-instruct").
            prompt (str): Input prompt for the model.
            context (list, optional): Previous conversation context for the model.

        Returns:
            str: Generated response from the model.
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "context": context or []
        }
        response = requests.post(
            f"{self.base_url}/api/generate",
            json=payload
        )
        return response.json().get("response", "")

    def list_models(self):
        """
        List all available models in the Ollama server.

        Returns:
            list: List of model names.
        """
        response = requests.get(f"{self.base_url}/api/tags")
        return response.json().get("models", [])