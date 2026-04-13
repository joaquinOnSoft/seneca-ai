# Using llama 4 in Pycharm

Using Llama 4 in PyCharm can be achieved by integrating local inference tools (like Ollama) or by using plugins that support API connections to the model. The most popular approach to use it locally in PyCharm is via the Ollama integration, which offers local autocomplete and chat functionality. 

Here is a step-by-step guide to setting up Llama 4 in PyCharm:

 - [IDEs & Editors JetBrains](https://docs.ollama.com/integrations/jetbrains)
 - [Cool! In PyCharm’s new AI Chat, there is native integration with Ollama and LMStudio.](https://www.linkedin.com/posts/eden-yavin-497416135_cool-in-pycharms-new-ai-chat-there-is-activity-7350427378969382914-ADI5/)
 - [Step-by-Step Guide to Using Ollama: Local LLM Inference Made ](https://shekhar14.medium.com/step-by-step-guide-to-using-ollama-local-llm-inference-made-easy-afba037f7a94#:~:text=How%20Ollama%20Works.%20At%20a%20high%20level%2C,interact%20with%20them%20via%20terminal%20or%20HTTP.)

## Prerequisites

1. **Install Ollama**: Download and install Ollama from [ollama.com](ollama.com).

```shell
$ curl -fsSL https://ollama.com/install.sh | sh
>>> Installing ollama to /usr/local
[sudo: authenticate] Password:         
>>> Downloading ollama-linux-amd64.tar.zst
######################################################################## 100.0%                                         ##O=#  #                  
>>> Creating ollama user...
>>> Adding ollama user to render group...
>>> Adding ollama user to video group...
>>> Adding current user to ollama group...
>>> Creating ollama systemd service...
>>> Enabling and starting ollama service...
Created symlink '/etc/systemd/system/default.target.wants/ollama.service' → '/etc/systemd/system/ollama.service'.
>>> The Ollama API is now available at 127.0.0.1:11434.
>>> Install complete. Run "ollama" from the command line.

```
2. **Pull Llama 4**: Open your terminal and run `ollama pull llama4` (replace llama4 with the specific Llama 4 model tag provided by Meta, such as an 8B or 70B variant).

```shell
$ ollama pull llama4 
pulling manifest 
pulling 9d507a36062c: 100% ▕████████████████████████████████████████████████████████████████████████████████████▏  67 GB                         
pulling 399a8a5a36db: 100% ▕████████████████████████████████████████████████████████████████████████████████████▏ 7.8 KB                         
pulling 24ca191a372b: 100% ▕████████████████████████████████████████████████████████████████████████████████████▏ 6.0 KB                         
pulling 161e5d878840: 100% ▕████████████████████████████████████████████████████████████████████████████████████▏ 3.7 KB                         
pulling fc1ffc71ab8e: 100% ▕████████████████████████████████████████████████████████████████████████████████████▏ 1.6 KB                         
pulling bee89e20d457: 100% ▕████████████████████████████████████████████████████████████████████████████████████▏   31 B                         
pulling f7ce8f326f5d: 100% ▕████████████████████████████████████████████████████████████████████████████████████▏ 1.1 KB                         
verifying sha256 digest 
writing manifest 
success 
```

3. **Install Python Interpreter**: Ensure a Python interpreter is set up in your PyCharm project. 

References:

   - [Running Llama on Mac](https://www.llama.com/docs/llama-everywhere/running-meta-llama-on-mac/)
   - [Running Llama on Windows](https://www.llama.com/docs/llama-everywhere/running-meta-llama-on-windows/)
   - [How do I setup a python code to access llama 3.3 model](https://www.llama.com/docs/llama-everywhere/running-meta-llama-on-windows/)

## Method 1: Using JetBrains AI Assistant (Recommended)

If you have the JetBrains AI Assistant plugin installed (part of PyCharm Professional), you can use Llama 4 locally
(see [ What’s New in PyCharm 2024.1.1](https://www.jetbrains.com/pycharm/whatsnew/2024-1-1/)): 

1. **Go to Settings**: Navigate to **Tools > AI Assistant > Third-party AI providers**.
2. **Select Ollama**: Choose **Ollama** as the provider.
3. **Select Model**: Under local models, select your pulled `llama4` model.
3. Use: You can now use the AI Assistant chat and code completion within PyCharm, powered by your local Llama 4 model. 

References:
   - [Help with Using JetBrains AI Locally with Ollama Integration](https://www.reddit.com/r/pycharm/comments/1ibphdp/help_with_using_jetbrains_ai_locally_with_ollama/)
   - [Use third-party and local models](https://www.jetbrains.com/help/ai-assistant/use-custom-models.html)


## Method 2: Using the CodeGPT Plugin (Community/Pro)
For an open-source alternative, you can use the CodeGPT plugin 
(see [Best local LLM Setup for IntelliJ / coding assistance?](https://www.reddit.com/r/LocalLLaMA/comments/1gvztnn/best_local_llm_setup_for_intellij_coding/)): 

1. **Install Plugin**: Go to **File > Settings > Plugins** and search for **CodeGPT**.
2. **Configure**: Open the CodeGPT settings, select **Ollama** as the provider, and choose `llama4` as the model.
3. **Use**: You can now chat and get code suggestions in a side panel. 


## Method 3: Running Llama 4 in a Python Script

You can interact with Llama 4 directly within a PyCharm Python file using llama-cpp-python or the ollama library: 

1. **Install Library**: Run `pip install ollama` in the PyCharm terminal.
2. **Create Script**:
    
```python
    import ollama

    response = ollama.chat(model='llama4', messages=[
        {
            'role': 'user',
            'content': 'Write a Python function to sort a list.',
        },
    ])
    print(response['message']['content'])
```
3. **Run**: Execute the script directly in PyCharm to generate code. 

See:
 - [PyCharm Plugin](https://www.reddit.com/r/LocalLLaMA/comments/164iz75/pycharm_plugin/)
 - [Llama.cpp and Ollama servers + plugins for VS Code / VS Codium and IntelliJ (AI)](https://discuss.linuxcontainers.org/t/llama-cpp-and-ollama-servers-plugins-for-vs-code-vs-codium-and-intellij-ai/19744)
 - [Run AI Models Locally: A Step-by-Step Guide to Deepseek, Ollama, and Seamless IDE Integration](https://medium.com/justeattakeaway-tech/run-ai-models-locally-a-step-by-step-guide-to-deepseek-ollama-and-seamless-ide-integration-904811e64ad9)


## Best Practices for Local Use


 - **Hardware Requirements**: Running Llama 4 locally requires a decent GPU (NVIDIA with CUDA or Apple Silicon M-series) for fast responses.
   > NOTE: A minimum of 64.0 GiB are required to run Llama 4 locally
 - **Quantization**: Ollama pulls quantized models, which helps run larger models with less VRAM.
 - **Offline Access**: Ensure the Ollama server is running (usually at 
   [http://localhost:11434](http://localhost:11434http://localhost:11434) to use the model without an internet connection. 