# Installing Ollama

Ollama is an open-source tool designed to run large language models (LLMs) locally on your own machine (macOS, Windows, Linux). It simplifies the process of downloading, configuring, and running models like Llama 3, Mistral, and Gemma, ensuring data privacy and offline capability.

Follow these steps to complete the installations and prerequisites:

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
