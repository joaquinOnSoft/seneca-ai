# ──────────────────────────────────────────────────────────────
#  Container 2 · Python 3.11 + ALSA + JACK + PyAudio
#
#  Base: python:3.11-slim-bookworm (Debian)
#  ALSA, JACK and PortAudio packages are available in Debian
#  Bookworm repos — no need to use a full Ubuntu base image.
# ──────────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# ── System packages ────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # ALSA — Advanced Linux Sound Architecture
    alsa-utils \
    alsa-oss \
    alsa-tools \
    libasound2-dev \
    libasound2-plugins \
    # JACK Audio Connection Kit
    jackd2 \
    libjack-jackd2-dev \
    # PortAudio (required by PyAudio)
    portaudio19-dev \
    # C extension build tools (PyAudio compiles a native extension)
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# ── Python packages ────────────────────────────────────────────
# pip, setuptools and wheel are already included in the official
# Python image; just upgrade and install project dependencies.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

RUN pip install --no-cache-dir \
    pyaudio \
    numpy \
    sounddevice \
    soundfile \
    requests

# ── Default ALSA configuration ─────────────────────────────────
# Adjust hw:0,0 to match the card number shown by `aplay -l` on the host
RUN printf 'pcm.!default {\n  type hw\n  card 0\n}\nctl.!default {\n  type hw\n  card 0\n}\n' \
    > /etc/asound.conf

# ── Non-root user with audio group access ──────────────────────
RUN groupadd -r appuser \
    && useradd -r -g appuser -G audio appuser

WORKDIR /app

# Smoke-test: verifies PyAudio imports and detects PortAudio correctly
CMD ["python3", "-c", \
     "import pyaudio; p = pyaudio.PyAudio(); print('PyAudio OK —', pyaudio.get_portaudio_version_text()); p.terminate()"]
