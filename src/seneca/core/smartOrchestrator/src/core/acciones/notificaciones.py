# -*- coding: utf-8 -*-
"""
Created on Sun Jul  5 08:01:48 2026

@author: NachoWorks
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import smtplib
import yaml
from pathlib import Path
from email.mime.text import MIMEText
import time

# Cargar configuración
CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config" / "apis.yaml"
with open(CONFIG_PATH, "r") as f:
    config = yaml.safe_load(f)

def enviar_whatsapp(mensaje: str, numero: str = "+34XXXXXXXXX") -> bool:
    """
    Envía un mensaje por WhatsApp Web.
    Args:
        mensaje (str): Mensaje a enviar.
        numero (str): Número de teléfono (con código de país).
    Returns:
        bool: True si se envió correctamente.
    """
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        driver = webdriver.Chrome(
            executable_path=config["notificaciones"]["whatsapp"]["driver_path"],
            options=options
        )

        driver.get(f"https://web.whatsapp.com/send?phone={numero}")
        print(f"Escanea el QR para {numero} en {config['notificaciones']['whatsapp']['qr_timeout']} segundos...")
        time.sleep(config["notificaciones"]["whatsapp"]["qr_timeout"])

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//div[@contenteditable='true']"))
        )

        input_box = driver.find_element(By.XPATH, "//div[@contenteditable='true']")
        input_box.send_keys(mensaje)
        driver.find_element(By.XPATH, "//span[@data-icon='send']").click()
        driver.quit()
        return True
    except Exception as e:
        print(f"Error al enviar mensaje por WhatsApp: {e}")
        return False

def enviar_email(asunto: str, cuerpo: str, destino: str) -> bool:
    """
    Envía un email usando SMTP.
    Args:
        asunto (str): Asunto del email.
        cuerpo (str): Cuerpo del email.
        destino (str): Email del destinatario.
    Returns:
        bool: True si se envió correctamente.
    """
    try:
        msg = MIMEText(cuerpo)
        msg["Subject"] = asunto
        msg["From"] = config["notificaciones"]["email"]["username"]
        msg["To"] = destino

        with smtplib.SMTP(
            config["notificaciones"]["email"]["smtp_server"],
            config["notificaciones"]["email"]["smtp_port"]
        ) as server:
            server.starttls()
            server.login(
                config["notificaciones"]["email"]["username"],
                config["notificaciones"]["email"]["password"]
            )
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Error al enviar email: {e}")
        return False