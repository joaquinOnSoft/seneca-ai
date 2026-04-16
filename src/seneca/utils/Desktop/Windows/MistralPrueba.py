# -*- coding: utf-8 -*-
"""
Created on Mon Apr 13 10:48:02 2026

@author: NachoWorks
"""


import subprocess

import time

from langchain_ollama import OllamaLLM

def abrir_fichero_notepad(texto, nombre_archivo):
    try:
        # 1. Intentar escribir el archivo
        with open(nombre_archivo, "w", encoding="utf-8") as archivo:
            archivo.write(texto)

        # 2. Intentar abrir Notepad
        subprocess.Popen(["notepad.exe", nombre_archivo])
        print(f"Archivo '{nombre_archivo}' abierto en Notepad.")
        time.sleep(2)

    except PermissionError:
        print(f"Error: No tienes permisos para escribir en '{nombre_archivo}'.")
    except FileNotFoundError as e:
        if "notepad.exe" in str(e):
            print("Error: Notepad no está disponible. ¿Estás en Windows?")
        else:
            print(f"Error: No se pudo encontrar el archivo o ruta: {e}")
    except Exception as e:
        print(f"Error inesperado: {e}")
        
def abrir_fichero_swriter(texto, nombre_archivo):
    try:
        # 1. Intentar escribir el archivo
        with open(nombre_archivo, "w", encoding="utf-8") as archivo:
            archivo.write(texto)

        # 2. Intentar abrir Notepad
        rutaSWriter=r"C:\Program Files (x86)\OpenOffice 4\program\swriter.exe"
        subprocess.Popen([rutaSWriter, nombre_archivo])
        print(f"Archivo '{nombre_archivo}' abierto en Swriter.")
        time.sleep(2)

    except PermissionError:
        print(f"Error: No tienes permisos para escribir en '{nombre_archivo}'.")
    except FileNotFoundError as e:
        if "notepad.exe" in str(e):
            print("Error: Notepad no está disponible. ¿Estás en Windows?")
        else:
            print(f"Error: No se pudo encontrar el archivo o ruta: {e}")
    except Exception as e:
        print(f"Error inesperado: {e}")



# Carga el modelo local (ej: mistral:7b)
llm = OllamaLLM(model="mistral:7b")
#llm = OllamaLLM(model="gemma:2b")
texto = input("Por favor, introduce una consulta: ")

# Usa el modelo con un prompt
response = llm.invoke(texto)

# Uso de Notepad

abrir_fichero_notepad(response, "salidaNotepad.txt")
abrir_fichero_swriter(response, "salidaSwriter.txt")


"""
with open("datos.txt", "a") as archivo:
    archivo.write(response)
   

#os.system("Notepad")
procesoNotepad = subprocess.Popen(["notepad", "datos.txt"])
time.sleep(2) # Give user time to focus Notepad
rutaSWriter=r"C:\Program Files (x86)\OpenOffice 4\program\swriter.exe"
procesoSWriter = subprocess.Popen([rutaSWriter, "datos.txt"])

"""
