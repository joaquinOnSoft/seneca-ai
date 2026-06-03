"""
setup.py – Minimal setup for editable installation.

Prefer pyproject.toml for new projects; this file is kept for
compatibility with older tooling.
"""

from setuptools import setup, find_packages

setup(
    name="seneca-ai",
    version="0.1.0",
    description=(
        "Seneca-AI – European open-source generative AI assistant"
    ),
    author="Seneca-AI Contributors",
    license="Apache-2.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.10",
    install_requires=[
        "customtkinter>=5.2.2",
        "ctk-markdown>=0.1.4",
        "langchain>=0.3.0",
        "langchain-openai>=0.2.0",
        "langchain-ollama>=0.2.0",
        "langchain-community>=0.3.0",
        "langchain-core>=0.3.0",
        "ollama>=0.3.0",
        "python-dotenv>=1.0.1",
        "Babel>=2.15.0",
        "SpeechRecognition>=3.10.4",
        "pyaudio>=0.2.14",
        "openai>=1.51.0",
        "faster-whisper>=0.12.0",
        "Flask>=2.0.0",
        "openai-whisper>=20231117",
        "Flasgger>=0.9.0",
        "pillow",
        "babel-cli",
        "python-json-logger",
        "waitress",
    ],
    entry_points={
        "console_scripts": [
            "seneca=seneca.ui.main_window:main",
        ],
    },
)