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
> $ sudo OLLAMA_MODEL=hadad/LFM2.5-1.2B:Q4_K_M ./install-ubuntu.sh
> ```

## Uninstall

Run the uninstaller from the project folder:

```shell
$ sudo ./uninstall-ubuntu.sh
```

1. It removes the Seneca AI containers, their network and their images.
2. It asks whether to delete the data volumes (folders under
   `/opt/senecaai/volumes`). **This deletes all the conversations, the
   long-term memory and the downloaded AI models, and cannot be undone.**
   The default answer is no: the data is kept and a new installation
   reuses it.
3. It asks whether to uninstall Docker (default: no). Docker may be used by
   other applications; if you uninstall it, it also asks whether to delete
   the images, containers and volumes of all of them
   (`/var/lib/docker`, `/var/lib/containerd`).

The project folder, with `.env` and the secrets in `docker/`, is kept:
delete it by hand when you no longer need it. To see what the uninstaller
would do without changing anything, run `sudo ./uninstall-ubuntu.sh --dry-run`.
