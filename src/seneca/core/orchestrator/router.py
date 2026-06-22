# -*- coding: utf-8 -*-
"""
Created on Sat May 30 06:41:30 2026

@author: NachoWorks
"""

from typing import Dict

from orchestrator.ollama_client import OllamaClient


class QueryRouter:
    def __init__(self):
        self.client = OllamaClient()
        self.model_routes = {
            "general": "hadad/LFM2.5-1.2B:Q4_K_M",
            "code": "starcoder2:3b",
            "lightweight": "gemma:2b",
            "reasoning": "phi4:latest",
            "creative": "gemma4:e2b",
            "tiny": "hadad/LFM2.5-1.2B:Q4_K_M"
        }

    def select_model(self, query: str) -> str:
        """
        Selecciona el modelo adecuado según la consulta, sin generar la respuesta.
        Devuelve el nombre del modelo.
        """
        query_lower = query.lower()

        if any(keyword in query_lower for keyword in ["código", "script", "python", "java", "function", "algorithm"]):
            return self.model_routes["code"]
        elif any(keyword in query_lower for keyword in ["whatsapp", "email", "mensaje", "reserva", "tarea"]):
            return self.model_routes["lightweight"]
        elif any(keyword in query_lower for keyword in ["explica", "razona", "analiza", "compara"]):
            return self.model_routes["reasoning"]
        elif any(keyword in query_lower for keyword in ["escribe", "crea", "historia", "poema", "canción"]):
            return self.model_routes["creative"]
        elif any(keyword in query_lower for keyword in ["abrir", "ejecuta", "automatiza"]):
            return self.model_routes["tiny"]
        else:
            return self.model_routes["general"]

    def route_query(self, query: str, context: Dict = None) -> str:
        """
        Enruta la consulta al modelo adecuado y devuelve la respuesta.
        """
        model = self.select_model(query)  # Usa el mismo método para seleccionar el modelo
        response = self.client.generate(
            model=model,
            prompt=query,
            context=context.get("history", []) if context else None
        )
        return response