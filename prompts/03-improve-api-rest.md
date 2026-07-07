# Security in the REST API

You are an expert Backend developer in Python. The requirements 
for improving the Seneca AI REST API are set out below. 

Improve the prompt to create a more secure REST API that follows market best practice.
If you have a better approach you can suggest it instead of follow literally these instructions.


Prompt:


## Authentication   

Below are the different mechanisms to authenticate with Seneca AI using Seneca AI REST API:

 - **Basic**: Invoke POST method on `/senecaai/v1/sessions` resource with user credentials. 
   Seneca AI will validate user credentials, against mongodb, and creates a session.
   Credentials 

For all the subsequent requests to Seneca AI with REST Services, except 
the '/senecaai/v1/health', '/apidocs', '/apispec_1.json', '/flasgger_static'.

    1. Set SESSIONID cookie in all the HTTP requests. (or)
    2. Set user message digest as a header (X-SENECA-AI-TOKEN) in all the HTTP requests. 
      You can find the user message digest in the response of the /senecaai/v1/sessions request. 
      Eg: X-SENECA-AI-TOKEN: 3dba7a9383964e759b3427378d338febc4dc0485 . 

The token is valid for an hour since is generated.

Seneca AI must validate if the cookie or the header token is set to answer the client, except
for those excluded methods previously enumerated.

## [POST] /senecaai/v1/sessions (New API method)

 - **POST** `/senecaai/v1/sessions` Create a Session
 - **Description**: Create a security Session in Seneca AI. It returns a valid Security Session object if the provided credentials are valid.
 - **Request body**: application/x-www-form-urlencoded 
   - **Params**: 
     - **user_name**: Required (string) UserName/UserId 
     - **password**: Required (string)
 - **Response**: 
   - 200: The request has been completed successfully
   
     ```json
     {
      "user_name": "string", 
      "user_full_name": "string",
      "user_id": "string",
      "x-seneca-ai-token": "string"
     }
     ```
   
   - 400: A required parameter is not specified or has null or invalid value
   - 401: Unauthorized access to the resource 
   - 500: An internal server error occurred, refer to the response for more information

## [POST] /senecaai/v1/sessions/token

 - **POST** `/senecaai/v1/sessions/token` Refresh an access token
 - **Description**: Refresh an access token. Extends the token expiration date in one hour
 - **Parameters**: No parameters 
 - **Request body**: application/x-www-form-urlencoded
   - **Params**: 
      - user_name: (Required if password is present) string. Username. 
      - password: (Required if user_name is present) string. Password. 
      - user_id: (Required if X-SENECA-AI-API-KEY is present) string. User identifier.
      - X-SENECA-AI-API-KEY: (Required if user_id is present) string. User API key (secret).
 - **Response**: 
   - 200: The request has been completed successfully

```json
   {
      "x-seneca-ai-token": "string",
      "expiry_time": "2026-07-01T20:58:55.835Z"
   }
```
   - 400: A required parameter is not specified or has null or invalid value 
   - 500: An internal server error occurred, refer to the response for more information

## Tasks

- Apply the changes to the REST API methods
- Apply the changes to the REST API unit test
- Modify de "Dockerfile" for the `api` container to create a collection with the user info:
 
```json
   {
      "user_name": "string", 
      "user_full_name": "string",
      "user_id": "string",
      "x-seneca-ai-api-key": "string",
      "sessions": [
         {
            "x-seneca-ai-token": "string",
            "expiry_time": "2026-07-01T20:58:55.835Z"   
         } 
      ]   
  }
```
