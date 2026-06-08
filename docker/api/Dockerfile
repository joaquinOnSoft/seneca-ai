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
    # ALSA Advanced Linux Sound Architecture \
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
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Python packages ────────────────────────────────────────────
# pip, setuptools and wheel are already included in the official
# Python image; just upgrade and install project dependencies.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

WORKDIR /app

# Copy requirements.txt and install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the application source code
COPY src /app/src

# Add /app/src to PYTHONPATH so Python can find the 'seneca' module
ENV PYTHONPATH=/app/src

# ── Default ALSA configuration ─────────────────────────────────
# Adjust hw:0,0 to match the card number shown by `aplay -l` on the host
RUN printf 'pcm.!default {\n  type hw\n  card 0\n}\nctl.!default {\n  type hw\n  card 0\n}\n' \
    > /etc/asound.conf

# ── Non-root user with api group access ──────────────────────
RUN groupadd -r api \
    && groupadd -r appuser \
    && useradd -r -g appuser -G api appuser

# Expose the port the Flask app will run on
EXPOSE 1414

# Set the Flask application entry point (not strictly needed for waitress when run directly, but good for consistency)
ENV FLASK_APP=src/seneca/api/api.py

# Command to run the Flask application using Waitress
CMD ["python", "src/seneca/api/api.py"]