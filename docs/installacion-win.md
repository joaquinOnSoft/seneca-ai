# Seneca AI:  Windows installation

To install Seneca AI in Windows, follow these steps:

 - Download the latest version [Seneca AI](https://github.com/joaquinOnSoft/seneca-ai/archive/refs/heads/main.zip)
 - Unzip the zip file
 - In the `Start menu` search, right-click **Terminal** (or **Command Prompt**) and select **Run as administrator**.
 - Execute the installer:

   ```shell
   c:\Program Files\Seneca-AI> .\install-win.ps1
   ```
   
## Troubleshooting

### Power Shell scrips execution is not enabled

 1. Start Windows PowerShell with the "Run as Administrator" option. Only members of the Administrators group on the computer can change the execution policy. 
 2. Enable running unsigned scripts by entering:

    ```powershell
    set-executionpolicy remotesigned
    ```

This will allow running unsigned scripts that you write on your local computer and signed scripts from Internet. 
This will change the policy permanently.