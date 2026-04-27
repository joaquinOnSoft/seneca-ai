# hadad / LFM2.5-1.2B

LFM2.5 is a new family of hybrid models designed for on-device deployment.  
It builds on the LFM2 architecture with extended pre-training and reinforcement learning.

> ollama run hadad/LFM2.5-1.2B:Q4_K_M


## Models

| Name               |  Size   | Context |  Input |
|:-------------------|:-------:|--------:|-------:|
| LFM2.5-1.2B:Q4_K_M |  731MB  |    125K |   Text |
| LFM2.5-1.2B:Q8_0   |  1.2GB  |    125K |   Text |
| LFM2.5-1.2B:F16    |  2.3GB  |    125K |   Text |
| LFM2.5-1.2B:BF16   | 2.3GB   |  125K   | Text   |

## LFM2.5-1.2B-Instruct

LFM2.5 is a new family of hybrid models designed for on-device deployment. It builds on the LFM2 architecture with extended pre-training and reinforcement learning.

  - **Best-in-class performance**: A 1.2B model rivaling much larger models, bringing high-quality AI to your pocket.
  - **Fast edge inference**: 239 tok/s decode on AMD CPU, 82 tok/s on mobile NPU. Runs under 1GB of memory with day-one support for llama.cpp, MLX, and vLLM.
  - **Scaled training**: Extended pre-training from 10T to 28T tokens and large-scale multi-stage reinforcement learning.
