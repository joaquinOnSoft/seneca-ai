Eres un desarrador experto de backen en python. A continuación se detallan los requisitos para ampliar el API REST de Seneca AI. Mejora el prompt para obtener unos métodos API que sigan las mejores prácticas de APIs rest y sean consisetentes con los métodos ya existentes:


Prompt:

	Quiero crear un api REST para gestionar las conversaciones de Seneca AI que se almacenarán en una base de datos mongodb.

	Utiliza Flask para la implementación de los nuevos métodos del API en src/seneca/api/api.py

	Añade la documentación en formato Swagger de los nuevos métodos.

	Añade los test unitarios en test/seneca/api/test_api.py


	Las conversaciones se almacenan en MongoDB en una collección llamada "conversations"
	El usuario y contraseña de mongodb se lee del fichero .env del contendor.


	Las converaciones se representan en formato JSON. Tienen este aspecto:


	```json
	{
	  "conversation_id": "conv_78901",
	  "title": "Solicitud de Día Libre",
	  "created_at": "2023-10-27T15:59:50+00:00",
	  "messages": [
	    {
	      "role": "user",
	      "content": "Hola Gemini, ¿puedes ayudarme a escribir un correo electrónico?",
	      "timestamp": "2023-10-27T16:00:00+00:00"
	    },
	    {
	      "role": "assistant",
	      "content": "¡Claro! Dime de qué se trata el correo y a quién va dirigido.",
	      "timestamp": "2023-10-27T16:00:15+00:00"
	    },
	    {
	      "role": "user",
	      "content": "Es para mi jefe, pidiendo un día libre el próximo viernes.",
	      "timestamp": "2023-10-27T16:00:30+00:00"
	    }
	  ]
	}
	``` 

	Todas las llamadas deben incluir el parametro X-SENECA-AI-API-KEY en la cabecera para tener permiso para poder relizar la 
	llamada al método del API.

	Los métodos que me gustaría crear son los siguientes:

	 - **[GET]** `/senecaai/v1/chat` : Recupera todos los chats de un usuario. Por defecto devuelve las últimas conversaciones. Un usuario solo puede recuperar sus propias conversaciones
	 	Parámetros:
	 		- convPerPage: (Opcional) Conversaiones por página. Valor por defecto 20
	 		- numPage: (Optional) Número de página.  Valor por defecto 1
		Retorno:
	 		Array de conversaciones (en formato JSON)


	 - **[GET]** `/senecaai/v1/chat/{$id}` : Recupera el chat de un usuario con el idetificador {$id} . Un usuario solo puede recuperar sus propias conversaciones

	 	Parámetros:
	 		- id: Identificador de la conversacion que se quiere recuper
	 	Retorno:
	 		Conversacion que corresponde el id especificado como parametro de entrada (en formato JSON)


	 - **[POST]** `/senecaai/v1/chat/` : Crea una nueva conversacion
	 	Body:
	 		Conversación en formato JSON que se quiere dar de alta
	 	Retorno:
	 		(sugiere valor de retorno)


	 - **[PATCH]** `/senecaai/v1/chat/{$id}`
	  	Parámetros:
			 - id: Identificador de la conversacion a modificar
	 	Body:
	 		Conversación en formato JSON que se quiere modificar
	 	Retorno:
			(sugiere valor de retorno)