# -*- coding: utf-8 -*-
"""
Created on Fri Apr 17 18:11:07 2026

@author: NachoWorks
"""

import subprocess
import os
from pathlib import Path
from typing import Optional

def save_text_to_file(text: str, file_name: str) -> str:
    """
    Saves text to a file with UTF-8 encoding.

    Args:
        text: Text to save.
        file_name: File name (with or without extension).

    Returns:
        str: Absolute path of the saved file.

    Raises:
        PermissionError: If write permission is denied.
        Exception: For other unexpected errors.
    """
    file_path = Path(file_name)
    if not file_path.suffix:
        file_path = file_path.with_suffix(".txt")

    with open(file_path, "w", encoding="utf-8") as file:
        file.write(text)

    return str(file_path)

def open_with_notepad(file_path: str) -> bool:
    """
    Opens a file with Notepad (Windows only).

    Args:
        file_path: Path of the file to open.

    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        if os.name == "nt":
            subprocess.Popen(["notepad.exe", file_path])
            print(f"File '{file_path}' opened in Notepad.")
            return True
        else:
            print("Warning: Notepad is only available on Windows.")
            return False
    except FileNotFoundError:
        print("Error: Notepad not found. Are you on Windows?")
        return False
    except Exception as e:
        print(f"Unexpected error opening Notepad: {e}")
        return False

def open_with_swriter(file_path: str, swriter_path: Optional[str] = None) -> bool:
    """
    Opens a file with LibreOffice Writer (Swriter).

    Args:
        file_path: Path of the file to open.
        swriter_path: Custom path to swriter.exe. If None, uses default path.

    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        if swriter_path is None:
            swriter_path = r"C:\Program Files (x86)\OpenOffice 4\program\swriter.exe"

        if not os.path.exists(swriter_path):
            print(f"Error: Swriter not found at '{swriter_path}'. Check the path.")
            return False

        subprocess.Popen([swriter_path, file_path])
        print(f"File '{file_path}' opened in Swriter.")
        return True
    except Exception as e:
        print(f"Unexpected error opening Swriter: {e}")
        return False

def save_and_open_with_notepad(text: str, file_name: str) -> bool:
    """
    Saves text to a file and opens it with Notepad.

    Args:
        text: Text to save.
        file_name: File name.

    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        file_path = save_text_to_file(text, file_name)
        return open_with_notepad(file_path)
    except Exception as e:
        print(f"Error saving or opening file: {e}")
        return False

def save_and_open_with_swriter(text: str, file_name: str, swriter_path: Optional[str] = None) -> bool:
    """
    Saves text to a file and opens it with Swriter.

    Args:
        text: Text to save.
        file_name: File name.
        swriter_path: Custom path to swriter.exe.

    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        file_path = save_text_to_file(text, file_name)
        return open_with_swriter(file_path, swriter_path)
    except Exception as e:
        print(f"Error saving or opening file: {e}")
        return False