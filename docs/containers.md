# Seneca AI: Docker containers

Seneca uses Docker containers to run the various services that make up its architecture

> [**Docker**](https://www.docker.com/) is a platform designed to help developers build, share, and run container applications. 
> It handle the tedious setup, so you can focus on the code.

## Ollama container

Container that runs [Ollama](https://ollama.com/), a free open-source tool that allows you to install and run 
artificial intelligence models (such as Llama 3, DeepSeek or Gemma) directly on your own computer. 
Instead of relying on cloud services like ChatGPT, it processes everything locally.

The AI model/s installed depends on the hardware available in your PC/laptop and the user choice.
These are the models suggested during the installation:

| Ram   | GPU	  | Modelo IA                   |
|-------| ------ | --------------------------- |
| 8 Gb	 | No	  | qwen2.5:1.5b o llama3.2:1b  |
| 8 Gb	 | Yes	  | qwen2.5:3b o qwen2.5:1.5b   |
| 16 Gb | No	  | qwen2.5:3b o llama3.2:3b    |
| 16 Gb | Yes	  | mistral:7b o llama3:8b      |
| 32 Gb | No	  | llama3:8b o gemma2:9b       |
| 32 Gb | Yes	  | qwen2.5:14b o phi3:14b      |
| 64 Gb | No	  | llama3:8b o command-r:35b   |
| 64 Gb | Yes	  | mixtral:8x7b o llama3.1:70b |

## API container

Container that exposes a REST API used by Seneca AI:

 - `GET` **/senecaai/v1/health** Health Check Endpoint
 - `POST` **/senecaai/v1/stt** Speech-to-Text (STT) Endpoint
 - `GET` **/senecaai/v1/stt/languages** Get Supported STT Languages
 - `POST` **/senecaai/v1/auth/login**, **/auth/refresh**, **/auth/logout** Authentication (JWT)
 - `GET`, `POST` **/senecaai/v1/conversations** List / create conversations
 - `GET`, `PATCH`, `DELETE` **/senecaai/v1/conversations/{id}** Get / update / delete a conversation
 - `POST` **/senecaai/v1/conversations/{id}/messages** Append messages to a conversation

A Postman collection with all the methods is available in `assets/api/Seneca AI.postman_collection.json`.

### Secrets

The containers receive their secrets as Docker secrets (files mounted in `/run/secrets`).
**None of these files is versioned.** `generate_secrets.sh` (Linux) and `generate_secrets.ps1`
(Windows) create the missing ones with random values. The install and redeploy scripts
(`install-ubuntu.sh`, `install-win.ps1`, `redeploy.sh`, `redeploy.bat`) call them automatically.

| Secret                     | Host file                               | Generated value / notes                                          |
|----------------------------|-----------------------------------------|------------------------------------------------------------------|
| `seneca_ai_api_key_secret` | `docker/api/seneca_ai_api_key.txt`      | 48 hex characters. Value expected in the `X-SENECA-AI-API-KEY` header. Also copied to `SENECA_AI_API_KEY` in `.env` for the desktop app |
| `jwt_secret_key`           | `docker/api/jwt_secret_key.txt`         | 64 hex characters. Signs the JWT tokens                          |
| `mongo_root_username`      | `docker/mongo/mongo_root_username.txt`  | `senecaai_admin`. MongoDB root user (authenticated against `admin`) |
| `mongo_root_password`      | `docker/mongo/mongo_root_password.txt`  | 48 hex characters. MongoDB root password                         |

To create them by hand, run from the project root:

```bash
./generate_secrets.sh                                                       # Linux
powershell -NoProfile -ExecutionPolicy Bypass -File generate_secrets.ps1   # Windows
```

> **Existing secrets are never overwritten.** MongoDB only applies the root user and
> password the first time it starts with an **empty** data directory
> (`/opt/senecaai/volumes/mongo`). If you delete or change the Mongo files while the
> database already has data, the `api` container can no longer connect. To change the
> password, change it in MongoDB first (`db.changeUserPassword(...)` in the `admin`
> database) and then update the file. Regenerating the JWT secret logs every user out.
>
> On Linux, the Mongo files are created with mode `644` because the `mongo` image reads
> them as the `mongodb` user, not as root. The API files use mode `600`.

> **First start and VPNs:** on its first start the API container downloads the Whisper
> model from Hugging Face. VPNs with a small MTU (e.g. WireGuard, MTU 1280) can make the
> HTTPS downloads from the Docker bridge network hang, and the API never opens port 1414.
> Disconnect the VPN during the first start.

To see the Swagger API documentation, access to [http://localhost:1414/apidocs](http://localhost:1414/apidocs)
when Seneca AI is running:

![Swagger Seneca AI REST API documentation](images/swagger-seneca-ai-rest-api.png)

## MongoDB container (Coming soon)

Container that runs MongoDB to maintain the historic of chats between Seneca AI and the user.

> **What is MongoDB?**
> 
> MongoDB is a document database that offers high scalability and flexibility, 
> as well as an advanced query and indexing model.