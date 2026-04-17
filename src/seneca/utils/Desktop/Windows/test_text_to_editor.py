# -*- coding: utf-8 -*-
"""
Created on Fri Apr 17 18:33:50 2026

@author: NachoWorks
"""

from text_to_editor import (
    save_and_open_with_notepad,
    save_and_open_with_swriter,
)

def test_notepad():
    """Test saving and opening a file with Notepad."""
    print("\n--- Testing Notepad ---")
    text = "This is a test for Notepad. Hello from José's digital twin!"
    file_name = "test_notepad_file"
    success = save_and_open_with_notepad(text, file_name)
    if success:
        print(f"✅ Notepad test passed: File '{file_name}.txt' opened successfully.")
    else:
        print(f"❌ Notepad test failed: Could not open '{file_name}.txt'.")

def test_swriter():
    """Test saving and opening a file with Swriter."""
    print("\n--- Testing Swriter ---")
    text = "This is a test for Swriter. Hello from José's digital twin!"
    file_name = "test_swriter_file"
    # If Swriter is installed in a custom path, pass it as the third argument.
    success = save_and_open_with_swriter(text, file_name)
    if success:
        print(f"✅ Swriter test passed: File '{file_name}.txt' opened successfully.")
    else:
        print(f"❌ Swriter test failed: Could not open '{file_name}.txt'.")

def test_file_creation():
    """Test if files are created correctly."""
    print("\n--- Testing File Creation ---")
    from text_to_editor import save_text_to_file
    from pathlib import Path

    text = "This is a test for file creation."
    file_name = "test_file_creation"
    file_path = save_text_to_file(text, file_name)

    if Path(file_path).exists():
        print(f"✅ File creation test passed: '{file_path}' exists.")
    else:
        print(f"❌ File creation test failed: '{file_path}' does not exist.")

if __name__ == "__main__":
    print("Running tests for text_to_editor module...")
    test_file_creation()
    test_notepad()
    test_swriter()
    print("\n--- All tests completed ---")