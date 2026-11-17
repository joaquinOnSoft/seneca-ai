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
        "Babel>=2.18.0",
        "Flask-Limiter>=4.1.1",
        "Flask>=3.1.3",
        "Flasgger>=0.9.7.1",
        "PyJWT>=2.15.1",
        "SpeechRecognition>=3.17.0",
        "babel-cli>=0.3.5",
        "bcrypt>=5.0.0",
        "ctk-markdown>=0.1.4",
        "customtkinter>=6.0.0",
        "faster-whisper>=1.2.1",
        "langchain-community>=0.4.2",
        "langchain-core>=1.8.1",
        "langchain-ollama>=1.1.0",
        "langchain-openai>=1.8.0",
        "langchain>=1.5.0",
        "openai-whisper>=20250625",
        "openai>=3.52.0",
        "ollama>=0.6.3",
        "libpass[bcrypt]>=1.9.4",
        "pillow>=13.0.0",
        "pyaudio>=0.2.14",
        "pymongo>=4.20.0",
        "pytest>=9.2.0",
        "python-dotenv>=1.2.4",
        "python-json-logger>=4.2.0",
        "uvicorn>=0.54.0",
        "waitress>=3.0.2"
    ],
    entry_points={
        "console_scripts": [
            "seneca=seneca.ui.main_window:main",
        ],
    },
)