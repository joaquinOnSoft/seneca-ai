# -*- coding: utf-8 -*-
"""
Created on Wed Jun  3 06:39:11 2026

@author: NachoWorks
"""

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

# Define el modelo para el cuerpo de la solicitud
class QueryRequest(BaseModel):
    query: str
    user_id: str = "default"  # Valor por defecto si no se proporciona

@app.post("/query")
async def handle_query(request: QueryRequest):
    from orchestrator.router import QueryRouter
    from orchestrator.context_manager import ContextManager

    router = QueryRouter()
    context_manager = ContextManager()

    # Obtén el modelo que se usará para esta consulta
    model_used = router.select_model(request.query)  # Nuevo método para seleccionar el modelo

    context = context_manager.get_context(request.user_id)
    response = router.route_query(request.query, context)
    context_manager.update_context(request.user_id, request.query, response)

    # Devuelve la respuesta junto con el modelo usado
    return {
        "response": response,
        "model_used": model_used  # Nombre del modelo que generó la respuesta
    }