# -*- coding: utf-8 -*-
"""
Created on Sun Jul  5 07:00:52 2026

@author: NachoWorks
"""

import ollama
import yaml
from pathlib import Path
from typing import Optional

# Cargar configuración
CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "ollama_models.yaml"
with open(CONFIG_PATH, "r") as f:
    config = yaml.safe_load(f)

def generar_respuesta_experto(
    categoria: str,
    consulta: str,
    contexto: Optional[str] = None,
    datos_externos: Optional[dict] = None
) -> str:
    """
    Genera una respuesta experta con contexto y datos externos.
    Args:
        categoria (str): Categoría de la consulta.
        consulta (str): Consulta original del usuario.
        contexto (str): Contexto adicional (ej: "El usuario quiere datos exactos").
        datos_externos (dict): Datos de APIs externas.
    Returns:
        str: Respuesta del modelo experto.
    """
    modelo = config["categorias"][categoria]["modelo"]
    prompt = config["categorias"][categoria]["prompt_experto"]
    prompt += f"\nConsulta original: {consulta}"

    if contexto:
        prompt += f"\nContexto adicional: {contexto}"

    if datos_externos:
        prompt += f"\nDatos externos: {datos_externos}"

    try:
        response = ollama.generate(
            model=modelo,
            prompt=prompt,
            options={"temperature": 0.2}
        )
        return response["response"]
    except Exception as e:
        print(f"Error al generar respuesta experta con {modelo}: {e}")
        return "Lo siento, no puedo generar una respuesta experta ahora."