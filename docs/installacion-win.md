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


