# ──────────────────────────────────────────────
#  Container 1 · Ollama + model LFM2.5-1.2B
#  Exposed port: 11434
# ──────────────────────────────────────────────
FROM ollama/ollama:latest

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# A model that can be configured without modifying the Dockerfile
ENV OLLAMA_MODEL="hadad/LFM2.5-1.2B:Q4_K_M" \
    OLLAMA_KEEP_ALIVE="300"

# The downloaded models remain in this volume
VOLUME ["/root/.ollama"]

COPY entrypoint.sh /entrypoint.sh
#RUN chmod +x /entrypoint.sh
RUN sed -i 's/\r//' /entrypoint.sh && chmod +x /entrypoint.sh


EXPOSE 11434

HEALTHCHECK --interval=20s --timeout=5s --start-period=90s --retries=5 \
    CMD curl -sf http://localhost:11434/api/version || exit 1

ENTRYPOINT ["/entrypoint.sh"]
