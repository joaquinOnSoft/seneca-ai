# gpt-oss-safeguard

[gpt-oss-safeguard-20b](https://ollama.com/library/gpt-oss-safeguard) and 
[gpt-oss-safeguard-120b](https://ollama.com/library/gpt-oss-safeguard) are safety 
reasoning models built-upon `gpt-oss` 

This model is designed to fit into **GPUs with 16GB of VRAM**. (21B parameters with 3.6B active parameters).

## Prerequisites

See [Installing Ollama](/docs/models-info/ollama.mdfo/ollama.md)

## Get started

### 20B:

```shell
ollama run gpt-oss-safeguard:20b
```

This model is designed to fit into GPUs with 16GB of VRAM. (21B parameters with 3.6B active parameters).

## Highlights

 - **Trained to reason about safety** : Trained and tuned for safety reasoning to accommodate use cases like LLM input-output filtering, online content labeling and offline labeling for Trust and Safety use cases. 
 - **Bring your own policy**: Interprets your written policy, so it generalizes across products and use cases with minimal engineering. 
 - **Reasoned decisions, not just scores**: Gain complete access to the model’s reasoning process, facilitating easier debugging and increased trust in policy decisions. Keep in mind Raw CoT is meant for developers and safety practitioners. It’s not intended for exposure to general users or use cases outside of safety contexts.
 - **Configurable reasoning effort**: Easily adjust the reasoning effort (low, medium, high) based on your specific use case and latency needs.
 - **Permissive Apache 2.0 license**: Build freely without copyleft restrictions or patent risk—ideal for experimentation, customization, and commercial deployment.

