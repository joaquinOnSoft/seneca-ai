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
    """
    prompt = config["categorias"][categoria]["prompt_general"]
    prompt += f"\nConsulta: {consulta}"

    print(f"💬 Generando respuesta general para categoría '{categoria}'...")  # Log

    try:
        response = ollama.generate(
            model=config["modelos"]["orquestador"],
            prompt=prompt,
            options={"temperature": 0.3}
        )
        return response["response"].strip()
    except Exception as e:
        print(f"❌ Error al generar respuesta general: {e}")  # Log de error
        return "No puedo responder ahora. ¿Quieres que intente buscar más información?"

def necesita_escalar(consulta: str, respuesta_general: str) -> bool:
    """
    Pregunta al modelo general si el usuario está pidiendo más información.
    """
    print("❓ Decidiendo si escalar...")  # Log

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
            options={"temperature": 0.1}
        )
        decision = response["response"].strip().lower()
        print(f"   Decisión: {decision}")  # Log
        return decision == "sí"
    except Exception as e:
        print(f"❌ Error al decidir si escalar: {e}")  # Log de error
        return False

def clasificar_consulta(consulta: str) -> Tuple[str, str, bool]:
    """
    Clasifica la consulta en una categoría y decide si escalar.
    """
    print("🔍 Clasificando consulta...")  # Log

    categorias = list(config["categorias"].keys())
    print(f"📌 Categorías disponibles: {categorias}")

    # Prompt optimizado con ejemplos y restricciones claras
    prompt = f"""
    Eres un clasificador de consultas. Dí cual es tu clasificación y después asigna la consulta a UNA de estas categorías en base al contexto: {', '.join(categorias)}.

    **Instrucciones estrictas:**
    - Analiza el significado de la consulta y elige la categoría más relevante.
    - Responde SOLO con el nombre de la categoría (en minúsculas y sin acentos).
    - No añadas explicaciones, ejemplos ni texto adicional.
    - Las ramas que se engloban dentro de las humanidades son filosofía, historía, literatura, lingüistica, arte, antropología, ética
    - Si la consulta no pertenece claramente en ninguna categoría, responde 'general.

    **Ejemplos de clasificación:**
    - "¿Qué intereses tiene una hipoteca?" → finanzas
    - "¿Cómo funciona un préstamo bancario?" → finanzas
    - "¿Cómo implementar quicksort en C?" → programacion
    - "¿Qué es un bucle for en Python?" → programacion
    - "¿Qué es la fotosíntesis?" → general
    - "Necesito un código para ordenar números" → programacion
    - "IA o intelegencia artificial" → programacion
    - "¿Cuál es el tipo de interés actual?" → finanzas
    - "¿Qué es la ética?" → humanidades
    - "¿Quienes fueron Sócrates, Epicteto y Séneca?" → humanidades
    - "¿Quién escribió la Odisea?" → humanidades
    - "¿Como se cura un catarro, gripe?, etc. " → salud
    - "¿cuales con los síntomas de una determinada enfermedad o dolencia?" → salud

    **Consulta a clasificar:**
    "{consulta}"
    """

    try:
        response = ollama.generate(
            model=config["modelos"]["orquestador"],
            prompt=prompt,
            options={"temperature": 0.1}
        )
        categoria = response["response"].strip()
       
        
        categoria = categoria if categoria in categorias else "general"

        print(f"   Categoría asignada: '{categoria}'")  # Log

        # Generar respuesta general
        respuesta_general = responder_general(consulta, categoria)

        # Decidir si escalar
        debe_escalar = necesita_escalar(consulta, respuesta_general)

        return categoria, respuesta_general, debe_escalar
    except Exception as e:
        print(f"❌ Error al clasificar consulta: {e}")  # Log de error
        return "general", "Lo siento, no puedo procesar tu consulta ahora.", False