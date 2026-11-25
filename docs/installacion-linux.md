# Seneca AI:  Linux installation (Ubuntu)

To install Seneca AI in Ubuntu, follow these steps:

 - Download the latest version [Seneca AI](https://github.com/joaquinOnSoft/seneca-ai/archive/refs/heads/main.zip)
 - Unzip the zip file, i.e. in a `terminal` execute:

   ```shell
   $ unzip seneca-ai-main.zip
   $ cd Seneca-AI
   ```
   
 - Execute the installer

   ```shell
   $ sudo ./install-ubuntu.sh
   ```

## AI model selection

The installer first chooses the Ollama AI model (`select_ollama_model.sh`). If `OLLAMA_MODEL`
already has a value in `.env`, it is kept and nothing is asked. If it is set as
an environment variable, it is written to `.env` and nothing is asked.
Otherwise the installer detects the RAM and the GPU
of the computer, suggests two models for its tier and writes the chosen one to
`OLLAMA_MODEL` in `.env`:

| Detected RAM | Tier  |
|--------------|-------|
| < 15 GB      | 8 GB  |
| 15 - 30 GB   | 16 GB |
| 31 - 62 GB   | 32 GB |
| >= 63 GB     | 64 GB |

Each tier starts 1 GB below its size, because the operating system reports a
bit less RAM than the installed RAM (e.g. a 32 GB computer may report 31 GB).
The models suggested for each tier are listed in
[Docker containers](containers.md#ollama-container).

> **`sudo` drops your environment variables.** An `OLLAMA_MODEL` exported in
> your shell does not reach the installer when it runs with plain `sudo`, so
> you would be asked for a model anyway. Pass it with one of these commands,
> or set it in `.env`, which always works:
>
> ```shell
> $ sudo -E ./install-ubuntu.sh
> $ sudo OLLAMA_MODEL=qwen2.5:3b ./install-ubuntu.sh
> ```
