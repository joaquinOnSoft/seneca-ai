"""
tests/unit/test_select_ollama_model.py – Ollama model selection scripts.

Runs select_ollama_model.sh (bash) and select_ollama_model.ps1 (pwsh) in a
temporary copy of the project, with the RAM and the GPU faked:

* bash: fake ``awk`` (prints MemTotal in kB) and ``lspci`` commands first in PATH.
* pwsh: a ``Get-CimInstance`` function, which takes precedence over the cmdlet.

Each script is skipped when its shell is not installed.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENV_EXAMPLE = "A=1\nOLLAMA_MODEL=\nB=2\n"

# Detected RAM (GB) -> tier, around each threshold (15, 31 and 63 GB)
TIERS = [(8, 8), (14, 8), (15, 16), (16, 16), (30, 16), (31, 32), (32, 32), (62, 32), (63, 64), (64, 64)]
# Tier -> (recommended, alternative) model without / with GPU
MODELS = {
    (8, False): ("qwen2.5:1.5b", "llama3.2:1b"),
    (8, True): ("qwen2.5:3b", "qwen2.5:1.5b"),
    (16, False): ("qwen2.5:3b", "llama3.2:3b"),
    (16, True): ("mistral:7b", "llama3:8b"),
    (32, False): ("llama3:8b", "gemma2:9b"),
    (32, True): ("qwen2.5:14b", "phi3:14b"),
    (64, False): ("llama3:8b", "command-r:35b"),
    (64, True): ("mixtral:8x7b", "llama3.1:70b"),
}


def _env_model(project: Path) -> str | None:
    env_file = project / ".env"
    if not env_file.exists():
        return None
    lines = [line for line in env_file.read_text().splitlines() if line.startswith("OLLAMA_MODEL=")]
    assert len(lines) <= 1, "OLLAMA_MODEL written more than once"
    return lines[0].split("=", 1)[1] if lines else None


class _Runner:
    """Base: copies the script and .env.example into a temporary project."""

    script = ""

    def __init__(self, tmp_path: Path):
        self.project = tmp_path / "project"
        self.project.mkdir()
        shutil.copy(ROOT / self.script, self.project)
        (self.project / ".env.example").write_text(ENV_EXAMPLE)
        self.env = {k: v for k, v in os.environ.items() if k != "OLLAMA_MODEL"}

    def run(self, ram_gb: int = 16, gpu: bool = False, answer: str = "",
            ollama_model: str | None = None) -> subprocess.CompletedProcess:
        raise NotImplementedError


class BashRunner(_Runner):
    script = "select_ollama_model.sh"

    def __init__(self, tmp_path: Path):
        super().__init__(tmp_path)
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        # The script computes GB as kB / 1000 / 1000
        self._fake("awk", 'echo "$FAKE_RAM_KB"')
        self._fake("lspci", '[ "$FAKE_GPU" = 1 ] && echo "01:00.0 VGA compatible controller: NVIDIA Corporation"; true')

    def _fake(self, name: str, body: str) -> None:
        path = self.bin / name
        path.write_text(f"#!/bin/sh\n{body}\n")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)

    def run(self, ram_gb=16, gpu=False, answer="", ollama_model=None):
        env = dict(self.env, PATH=f"{self.bin}{os.pathsep}{self.env.get('PATH', '')}",
                   FAKE_RAM_KB=str(ram_gb * 1000 * 1000), FAKE_GPU="1" if gpu else "0")
        if ollama_model is not None:
            env["OLLAMA_MODEL"] = ollama_model
        # Sourced, as install-ubuntu.sh does
        return subprocess.run(["bash", "-c", "source ./select_ollama_model.sh"], cwd=self.project, env=env,
                              input=answer + "\n", capture_output=True, text=True, timeout=30, check=True)


class PwshRunner(_Runner):
    script = "select_ollama_model.ps1"

    def run(self, ram_gb=16, gpu=False, answer="", ollama_model=None):
        gpu_name = "NVIDIA GeForce RTX 4070" if gpu else "Microsoft Basic Display Adapter"
        command = (
            "function Get-CimInstance { param([string]$ClassName) "
            f"if ($ClassName -eq 'Win32_ComputerSystem') {{ [pscustomobject]@{{TotalPhysicalMemory = {ram_gb}GB}} }} "
            f"else {{ [pscustomobject]@{{Name = '{gpu_name}'}} }} }}; "
            "& ./select_ollama_model.ps1"
        )
        env = dict(self.env)
        if ollama_model is not None:
            env["OLLAMA_MODEL"] = ollama_model
        return subprocess.run(["pwsh", "-NoProfile", "-Command", command], cwd=self.project,
                              env=env, input=answer + "\n", capture_output=True, text=True, timeout=60, check=True)


RUNNERS = [
    pytest.param(BashRunner, marks=pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed"),
                 id="bash"),
    pytest.param(PwshRunner, marks=pytest.mark.skipif(shutil.which("pwsh") is None, reason="pwsh not installed"),
                 id="pwsh"),
]


@pytest.fixture(params=RUNNERS)
def runner(request, tmp_path) -> _Runner:
    return request.param(tmp_path)


@pytest.mark.parametrize("ram_gb, tier", TIERS)
def test_ram_tier_thresholds(runner, ram_gb, tier):
    out = runner.run(ram_gb=ram_gb).stdout
    assert f"Mapped to {tier} GB tier" in out
    assert _env_model(runner.project) == MODELS[(tier, False)][0]


@pytest.mark.parametrize("tier", [8, 16, 32, 64])
@pytest.mark.parametrize("gpu", [False, True], ids=["no-gpu", "gpu"])
def test_recommended_and_alternative_models(runner, tier, gpu):
    recommended, alternative = MODELS[(tier, gpu)]
    runner.run(ram_gb=tier, gpu=gpu, answer="A")
    assert _env_model(runner.project) == alternative
    runner.project.joinpath(".env").unlink()
    runner.run(ram_gb=tier, gpu=gpu, answer="")
    assert _env_model(runner.project) == recommended


def test_env_file_is_created_from_example(runner):
    runner.run(ram_gb=16, answer="R")
    lines = runner.project.joinpath(".env").read_text().splitlines()
    assert lines == ["A=1", "OLLAMA_MODEL=qwen2.5:3b", "B=2"]


def test_model_in_env_file_is_kept(runner):
    runner.project.joinpath(".env").write_text("OLLAMA_MODEL=kept:1b\n")
    out = runner.run(ollama_model="ignored:1b").stdout
    assert "taken from .env" in out
    assert "HARDWARE DETECTION" not in out
    assert _env_model(runner.project) == "kept:1b"


def test_environment_variable_is_written_to_env_file(runner):
    out = runner.run(ollama_model="hadad/LFM2.5-1.2B:Q4_K_M").stdout
    assert "taken from the environment" in out
    assert "HARDWARE DETECTION" not in out
    lines = runner.project.joinpath(".env").read_text().splitlines()
    assert lines == ["A=1", "OLLAMA_MODEL=hadad/LFM2.5-1.2B:Q4_K_M", "B=2"]


def test_environment_variable_replaces_empty_value(runner):
    runner.project.joinpath(".env").write_text("A=1\nOLLAMA_MODEL=\n")
    runner.run(ollama_model="qwen2.5:3b")
    assert runner.project.joinpath(".env").read_text().splitlines() == ["A=1", "OLLAMA_MODEL=qwen2.5:3b"]


def test_model_is_appended_when_missing(runner):
    runner.project.joinpath(".env").write_text("A=1\n")
    runner.run(ollama_model="qwen2.5:3b")
    assert runner.project.joinpath(".env").read_text().splitlines() == ["A=1", "OLLAMA_MODEL=qwen2.5:3b"]


def test_special_characters_are_written_verbatim(runner):
    runner.project.joinpath(".env").write_text("OLLAMA_MODEL=\n")
    runner.run(ollama_model=r"a|b&c\d")
    assert _env_model(runner.project) == r"a|b&c\d"
