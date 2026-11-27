# -*- coding: utf-8 -*-
"""
Created on Sun Jul  5 07:02:45 2026

@author: NachoWorks
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import time  # Módulo para medir el tiempo
from src.core.orquestador import clasificar_consulta
from src.core.modelos_expertos import generar_respuesta_experto
from src.core.acciones.api_banco import buscar_interes_hipoteca, simular_cuota
from src.core.acciones.notificaciones import enviar_whatsapp, enviar_email
import yaml
from pathlib import Path

# Cargar configuración
CONFIG_PATH = Path(__file__).parent.parent / "gemelo_digital_avanzado" / "config" / "ollama_models.yaml"
with open(CONFIG_PATH, "r") as f:
    config = yaml.safe_load(f)

app = FastAPI(title="Gemelo Digital con Orquestación Inteligente")

class Consulta(BaseModel):
    texto: str
    origen: str = "whatsapp"
    destino: Optional[str] = None
    contexto: Optional[str] = None

@app.post("/consulta")
async def procesar_consulta(consulta: Consulta):
    """
    Procesa una consulta del usuario:
    1. Responde de forma general con el orquestador.
    2. Pregunta al modelo si el usuario quiere más detalles.
    3. Si es "Sí", escala al modelo experto.
    """
    # Iniciar medición de tiempo
    inicio_tiempo = time.time()

    # 1. Clasificar consulta y obtener respuesta general + decisión de escalado
    categoria, respuesta_general, debe_escalar = clasificar_consulta(consulta.texto)

    # Modelo utilizado (por defecto, el orquestador)
    modelo_utilizado = config["modelos"]["orquestador"]

    # 2. Si no debe escalar, enviar respuesta general
    if not debe_escalar:
        if consulta.origen == "whatsapp":
            enviar_whatsapp(respuesta_general, consulta.destino)
        elif consulta.origen == "email":
            enviar_email("Respuesta a tu consulta", respuesta_general, consulta.destino)

        # Calcular tiempo de respuesta
        tiempo_respuesta = time.time() - inicio_tiempo

        return {
            "respuesta": respuesta_general,
            "categoria": categoria,
            "escalado": False,
            "modelo_utilizado": modelo_utilizado,
            "tiempo_respuesta_segundos": tiempo_respuesta,  # Tiempo en segundos
            "mensaje": "Si necesitas más detalles, dime y buscaré información precisa."
        }

    # 3. Si debe escalar, obtener datos externos y responder con experto
    datos_externos = None
    contexto_escalado = f"Consulta original: '{consulta.texto}'. El usuario quiere más detalles."

    # Acciones específicas por categoría
    if categoria == "finanzas":
        if "interés" in consulta.texto.lower() or "hipoteca" in consulta.texto.lower():
            datos_externos = buscar_interes_hipoteca(tipo="100%")
        elif "cuota" in consulta.texto.lower():
            datos_externos = simular_cuota(monto=200000, plazo=30)

    # Generar respuesta experta
    respuesta_experta = generar_respuesta_experto(
        categoria=categoria,
        consulta=consulta.texto,
        contexto=contexto_escalado,
        datos_externos=datos_externos
    )

    # Modelo experto utilizado
    modelo_utilizado = config["categorias"][categoria]["modelo"]

    # Enviar respuesta experta
    if consulta.origen == "whatsapp":
        enviar_whatsapp(respuesta_experta, consulta.destino)
    elif consulta.origen == "email":
        enviar_email("Respuesta detallada a tu consulta", respuesta_experta, consulta.destino)

    # Calcular tiempo de respuesta
    tiempo_respuesta = time.time() - inicio_tiempo

    return {
        "respuesta": respuesta_experta,
        "categoria": categoria,
        "escalado": True,
        "modelo_utilizado": modelo_utilizado,
        "tiempo_respuesta_segundos": tiempo_respuesta,  # Tiempo en segundos
        "datos_externos": datos_externos
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)