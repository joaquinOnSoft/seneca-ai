# -*- coding: utf-8 -*-
"""
Created on Sun Jul  5 08:00:34 2026

@author: NachoWorks
"""

import requests
import yaml
from pathlib import Path

# Cargar configuración
CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config" / "apis.yaml"
with open(CONFIG_PATH, "r") as f:
    config = yaml.safe_load(f)

def buscar_interes_hipoteca(tipo: str = "100%") -> dict:
    """
    Consulta el interés actual de una hipoteca en el banco.
    Args:
        tipo (str): Tipo de hipoteca (ej: "100%").
    Returns:
        dict: Datos del interés (ej: {"interes": 3.5, "fecha": "2026-06-16"}).
    """
    url = f"{config['banco']['base_url']}{config['banco']['endpoints']['intereses_hipoteca']}"
    headers = {"Authorization": f"Bearer {config['banco']['auth']['token']}"}
    params = {"tipo": tipo}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error al consultar API del banco: {e}")
        return {"error": str(e)}

def simular_cuota(monto: float, plazo: int = 30) -> dict:
    """
    Simula la cuota de una hipoteca.
    Args:
        monto (float): Monto del préstamo.
        plazo (int): Plazo en años.
    Returns:
        dict: Cuota mensual y detalles.
    """
    url = f"{config['banco']['base_url']}{config['banco']['endpoints']['simulador_cuota']}"
    headers = {"Authorization": f"Bearer {config['banco']['auth']['token']}"}
    data = {"monto": monto, "plazo": plazo}

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error al simular cuota: {e}")
        return {"error": str(e)}