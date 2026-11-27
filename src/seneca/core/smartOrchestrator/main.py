# -*- coding: utf-8 -*-
"""
Created on Sun Jul  5 07:02:45 2026

@author: NachoWorks
"""

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
import time
from src.core.orquestador import clasificar_consulta
from src.core.modelos_expertos import generar_respuesta_experto
from src.core.acciones.api_banco import buscar_interes_hipoteca, simular_cuota
from src.core.acciones.notificaciones import enviar_whatsapp, enviar_email
import yaml
from pathlib import Path

# Cargar configuración
CONFIG_PATH = Path(__file__).parent.parent / "smartOrchestrator" / "config" / "ollama_models.yaml"
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
    # Log de la petición recibida
    print("\n" + "="*50)
    print(f"📥 Petición recibida: '{consulta.texto}'")
    print(f"   Origen: {consulta.origen}, Destino: {consulta.destino}")
    print("="*50 + "\n")

    # Iniciar medición de tiempo
    inicio_tiempo = time.time()

    # 1. Clasificar consulta y obtener respuesta general + decisión de escalado
    print("🔍 Clasificando consulta...")
    categoria, respuesta_general, debe_escalar = clasificar_consulta(consulta.texto)

    # Log de la categorización
    print(f"📌 Categorización: '{categoria}'")
    print(f"   Escalado: {'Sí' if debe_escalar else 'No'}")

    # Modelo utilizado (por defecto, el orquestador)
    modelo_utilizado = config["modelos"]["orquestador"]
    print(f"🤖 Modelo utilizado (orquestador): '{modelo_utilizado}'")

    # 2. Si no debe escalar, enviar respuesta general
    if not debe_escalar:
        print("✅ No se requiere escalado. Usando respuesta general.")

        if consulta.origen == "whatsapp":
            print("📱 Enviando respuesta por WhatsApp...")
            enviar_whatsapp(respuesta_general, consulta.destino)
        elif consulta.origen == "email":
            print("📧 Enviando respuesta por email...")
            enviar_email("Respuesta a tu consulta", respuesta_general, consulta.destino)

        # Calcular tiempo de respuesta
        tiempo_respuesta = time.time() - inicio_tiempo
        print(f"⏱️  Tiempo de respuesta: {tiempo_respuesta:.2f} segundos\n")

        return {
            "respuesta": respuesta_general,
            "categoria": categoria,
            "escalado": False,
            "modelo_utilizado": modelo_utilizado,
            "tiempo_respuesta_segundos": tiempo_respuesta,
            "mensaje": "Si necesitas más detalles, dime y buscaré información precisa."
        }

    # 3. Si debe escalar, obtener datos externos y responder con experto
    print("🔄 Escalando a modelo experto...")
    datos_externos = None
    contexto_escalado = f"Consulta original: '{consulta.texto}'. El usuario quiere más detalles."

    # Acciones específicas por categoría
    if categoria == "finanzas":
        if "interés" in consulta.texto.lower() or "hipoteca" in consulta.texto.lower():
            print("🏦 Consultando API del banco (intereses)...")
            datos_externos = buscar_interes_hipoteca(tipo="100%")
        elif "cuota" in consulta.texto.lower():
            print("💰 Simulando cuota...")
            datos_externos = simular_cuota(monto=200000, plazo=30)

    # Modelo experto utilizado
    modelo_utilizado = config["categorias"][categoria]["modelo"]
    print(f"🤖 Modelo experto seleccionado: '{modelo_utilizado}'")

    # Generar respuesta experta
    print("🧠 Generando respuesta experta...")
    respuesta_experta = generar_respuesta_experto(
        categoria=categoria,
        consulta=consulta.texto,
        contexto=contexto_escalado,
        datos_externos=datos_externos
    )

    # Enviar respuesta experta
    if consulta.origen == "whatsapp":
        print("📱 Enviando respuesta experta por WhatsApp...")
        enviar_whatsapp(respuesta_experta, consulta.destino)
    elif consulta.origen == "email":
        print("📧 Enviando respuesta experta por email...")
        enviar_email("Respuesta detallada a tu consulta", respuesta_experta, consulta.destino)

    # Calcular tiempo de respuesta
    tiempo_respuesta = time.time() - inicio_tiempo
    print(f"⏱️  Tiempo de respuesta: {tiempo_respuesta:.2f} segundos\n")

    return {
        "respuesta": respuesta_experta,
        "categoria": categoria,
        "escalado": True,
        "modelo_utilizado": modelo_utilizado,
        "tiempo_respuesta_segundos": tiempo_respuesta,
        "datos_externos": datos_externos
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)