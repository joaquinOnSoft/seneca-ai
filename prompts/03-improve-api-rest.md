You are an expert Backend developer in Python. The requirements 
for improving the Seneca AI REST API are set out below. 

Improve the prompt to create a more secure REST API that follows best practice.


Prompt:

## Authentication   

Below are the different mechanisms to authenticate with Seneca AI using Seneca AI REST API:

 - **Basic**: Invoke POST method on `/senecaai/v1/sessions` resource with user credentials. 
   Seneca AI will validate user credentials, against mongodb, and creates a session.

For all the subsequent requests to Seneca AI with REST Services.

    1. Set JSESSIONID cookie in all the HTTP requests. (or)
    2. Set user message digest as a header(otmmauthtoken) in all the HTTP requests. You can find the user message digest in the response of the /v6/sessions request. 
    Eg: otmmauthtoken: 3dba7a9383964e759b3427378d338febc4dc0485 . (or)
    3. Set OAuth2.0 access token as a Authorization header in all the HTTP requests. Eg: Authorization: Basic [access_token]

The following code snippet demonstrates how to perform basic authentication to OTMM that uses Jersey Client API to communicate with REST services.

Client client = ClientBuilder.newClient();
client.register(MOXyContextResolver.class);
client.register(JsonMoxyConfigurationContextResolver.class);
client.register(MultiPartFeature.class);
rootTarget = client.target("http://localhost:11090/otmmapi");

Form form = new Form();
form.param("username", username);
form.param("password", password);

// Making POST request on session resource to authenticate
Response response = rootTarget.path("/v6/sessions").request().post(Entity.entity(form, MediaType.APPLICATION_FORM_URLENCODED), Response.class);

 Map<String, NewCookie> cookieMap = response.getCookies();
// Getting jsessionId from cookie
String jsessionId = cookieMap.get("JSESSIONID");
SessionRepresentation sessionRepresentation = response.readEntity(SessionRepresentation.class);
// Getting user authentication token from response
string otmmauthtoken = sessionRepresentation.getSession().getMessageDigest();

Below is code snippet to logout from OTMM

// How to set JSESSIONID cookie into request
rootTarget.path("/v6/sessions").request().cookie(jsessionId).delete();

// How to set otmm authentication token into request 
rootTarget.path("/v6/sessions").request().header("otmmauthtoken",otmmauthtoken).delete()
    