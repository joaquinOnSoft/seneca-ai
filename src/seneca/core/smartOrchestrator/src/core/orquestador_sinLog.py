# -*- coding: utf-8 -*-
"""
Created on Tue Jun 16 21:53:21 2026

@author: NachoWorks
"""

import ollama
import yaml
from pathlib import Path
from typing import Tuple

# Cargar configuración
CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "ollama_models.yaml"
with open(CONFIG_PATH, "r") as f:
    config = yaml.safe_load(f)

def responder_general(consulta: str, categoria: str = "general") -> str:
    """
    Genera una respuesta general usando el orquestador.
    Args:
        consulta (str): Consulta del usuario.
        categoria (str): Categoría de la consulta (default: "general").
    Returns:
        str: Respuesta general.
    """
    prompt = config["categorias"][categoria]["prompt_general"]
    prompt += f"\nConsulta: {consulta}"

    try:
        response = ollama.generate(
            model=config["modelos"]["orquestador"],
            prompt=prompt,
            options={"temperature": 0.3}
        )
        return response["response"].strip()
    except Exception as e:
        print(f"Error al generar respuesta general: {e}")
        return "No puedo responder ahora. ¿Quieres que intente buscar más información?"

def necesita_escalar(consulta: str, respuesta_general: str) -> bool:
    """
    Pregunta al modelo general si el usuario está pidiendo más información.
    Args:
        consulta (str): Consulta original del usuario.
        respuesta_general (str): Respuesta generada por el orquestador.
    Returns:
        bool: True si el modelo determina que el usuario quiere más detalles.
    """
    prompt = f"""
    Analiza la siguiente consulta y mi respuesta. ¿El usuario está pidiendo más información o detalles?
    - Consulta del usuario: "{consulta}"
    - Mi respuesta: "{respuesta_general}"

    Responde SOLO con "Sí" o "No".
    """

    try:
        response = ollama.generate(
            model=config["modelos"]["orquestador"],
            prompt=prompt,
            options={"temperature": 0.1}  # Baja temperatura para respuestas deterministas
        )
        decision = response["response"].strip().lower()
        return decision == "sí"
    except Exception as e:
        print(f"Error al decidir si escalar: {e}")
        return False  # Por defecto, no escalar si hay error

def clasificar_consulta(consulta: str) -> Tuple[str, str, bool]:
    """
    Clasifica la consulta en una categoría y decide si escalar.
    Args:
        consulta (str): Consulta del usuario.
    Returns:
        Tuple[str, str, bool]: (categoría, respuesta_general, debe_escalar).
    """
    categorias = list(config["categorias"].keys())
    prompt = f"""
    Clasifica esta consulta en UNA de estas categorías: {', '.join(categorias)}.
    Consulta: "{consulta}"
    Responde SOLO con la categoría elegida.
    """

    try:
        # 1. Clasificar la consulta
        response = ollama.generate(
            model=config["modelos"]["orquestador"],
            prompt=prompt,
            options={"temperature": 0.1}
        )
        categoria = response["response"].strip()
        categoria = categoria if categoria in categorias else "general"

        # 2. Generar respuesta general
        respuesta_general = responder_general(consulta, categoria)

        # 3. Decidir si escalar (pregunta al modelo)
        debe_escalar = necesita_escalar(consulta, respuesta_general)  # <-- CAMBIO: Variable renombrada

        return categoria, respuesta_general, debe_escalar
    except Exception as e:
        print(f"Error al clasificar consulta: {e}")
        return "general", "Lo siento, no puedo procesar tu consulta ahora.", False