# Seneca AI:  Windows installation

To install Seneca AI in Windows, follow these steps:

 - Download the latest version [Seneca AI](https://github.com/joaquinOnSoft/seneca-ai/archive/refs/heads/main.zip)
 - Unzip the zip file
 - In the `Start menu` search, right-click **Terminal** (or **Command Prompt**) and select **Run as administrator**.
 - Execute the installer:

   ```shell
   cd c:\Program Files\Seneca-AI> 
   .\install-win.ps1
   ```
   
## AI model selection

The installer first chooses the Ollama AI model (`select_ollama_model.ps1`). If `OLLAMA_MODEL`
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

> **Set the variable in the administrator terminal.** It is a new session, so
> an `OLLAMA_MODEL` set in another window does not reach the installer. Set it
> there, or in `.env`. The installer stores it in `.env`, so it survives the
> reboot between its two executions:
>
> ```powershell
> $env:OLLAMA_MODEL = "qwen2.5:3b"; .\install-win.ps1
> ```

## Troubleshooting

### Power Shell scrips execution is not enabled

If you see an error message similar to this when running the installer, it is because PowerShell script execution is disabled:

> .\install-win.ps1
> .\install-win.ps1 : File C:\Program Files\Seneca-AI\install-win.ps1 cannot be
> loaded because running scripts is disabled on this system. For more information, see about_Execution_Policies at
> https:/go.microsoft.com/fwlink/?LinkID=135170.
> At line:1 char:1
> + .\install-win.ps1
> + ~~~~~~~~~~~~~~~~~~~~~~~~~
>     + CategoryInfo          : SecurityError: (:) [], PSSecurityException
>     + FullyQualifiedErrorId : UnauthorizedAccess

Follow these steps to complete the installation process:

 1. Start Windows PowerShell with the "Run as Administrator" option. Only members of the Administrators group on the computer can change the execution policy. 
 2. Enable running unsigned scripts by entering:

    ```powershell
    set-executionpolicy Unrestricted
    ```

 > **NOTE**: This will allow running unsigned scripts that you write on your local computer and signed scripts from Internet. 
 > This will change the policy permanently.
 > See: [About Execution Policies](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies?view=powershell-7.6)

 3. Execute the installer:

   ```shell
   c:\Program Files\Seneca-AI> .\install-win.ps1
   ```


4. Restore default execution policy:

    ```powershell
    set-executionpolicy Default
    ```


