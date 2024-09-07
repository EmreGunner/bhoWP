import logging
from fastapi import FastAPI, Request, Query, HTTPException, Body, Form, WebSocket, UploadFile, File
from fastapi.responses import PlainTextResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pywa import WhatsApp, filters
from pywa.types import Message, CallbackButton, CallbackSelection, FlowCompletion, MessageStatus, TemplateStatus, ChatOpened, Button, MessageStatusType
from fastapi.websockets import WebSocketDisconnect
import datetime
import asyncio
import json
from pywa.errors import (
    BaseError, APIError, HTTPError, NetworkError, ValidationError, 
    AuthenticationError, PermissionError, RateLimitError, NotFoundError, 
    ConflictError, ServerError, TimeoutError, BadRequestError
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI application
fastapi_app = FastAPI()

# Mount static files
fastapi_app.mount("/static", StaticFiles(directory="static"), name="static")

# Set up Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Update the WhatsApp client initialization
wa = WhatsApp(
    phone_id="347058841835061",
    token=
    "EAAOxaNntzsEBOwJwyemOEYo6jHvXatZBpwFTwpOuY8EyEQNNrelEdCAdx7kMo1R7Wx7rHCQNQlV7Nbq8dVsALD8o7PjnZBCLMzDXc2Jpa6FZCTp1LpeZAkNqoLZB6J4fD0jeUJgb2josZCdGKgxsGwareDSqojJxazhkXTSh4NGFJmhErZAk1hoCjswFJoq9CiEK0PH8Nce6tAciIiZCwuUZD",
    server=fastapi_app,
    callback_url=
    "https://49ae544d-ebdc-4b20-9445-aa092113c69a-00-1cr1zoiat6wtd.sisko.replit.dev",
    verify_token="randomstring",
    app_id=1039488821087937,
    app_secret="eda6cba58fa6404a8198b205face33aa",
    validate_updates=True,
    continue_handling=True)

# Add this line near the top of the file, after the imports
BUSINESS_PHONE_NUMBER_ID = "347058841835061"

# Update the webhook verification endpoint
@fastapi_app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


@fastapi_app.get("/webhook/verify")
async def verify_webhook(request: Request,
                         hub_mode: str = Query(..., alias="hub.mode"),
                         hub_verify_token: str = Query(
                             ..., alias="hub.verify_token"),
                         hub_challenge: str = Query(...,
                                                    alias="hub.challenge")):
    try:
        challenge, status_code = await wa.webhook_challenge_handler(
            vt=hub_verify_token, ch=hub_challenge)
        return PlainTextResponse(content=challenge, status_code=status_code)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)


# Update the message receiving endpoint
@fastapi_app.post("/")
@fastapi_app.post("/webhook/messages")
async def receive_webhook(request: Request):
    try:
        body = await request.body()
        data = await request.json()
        logger.info(f"Received webhook data: {data}")
        response, status_code = await wa.webhook_update_handler(
            update=data,
            raw_body=body,
            hmac_header=request.headers.get("X-Hub-Signature-256"))
        logger.info(
            f"Webhook handler response: {response}, status: {status_code}")

        # Process the incoming message
        if 'messages' in data['entry'][0]['changes'][0]['value']:
            message = data['entry'][0]['changes'][0]['value']['messages'][0]
            # Broadcast the message to all connected WebSocket clients
            for client in connected_clients:
                await client.send_json(message)

        return PlainTextResponse(content=response, status_code=status_code)
    except Exception as e:
        logger.error(f"Error in receive_webhook: {e}", exc_info=True)


# Serve the home page
@fastapi_app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


# Serve the chat page
@fastapi_app.get("/chat")
async def chat(request: Request):
    return templates.TemplateResponse("chat2.html", {"request": request, "business_phone_number_id": wa.phone_id})


# Serve the send message page
@fastapi_app.get("/send_message")
async def send_message_page(request: Request):
    return templates.TemplateResponse("send_message.html",
                                      {"request": request})


# New endpoint to send a message
@fastapi_app.post("/send_message")
async def send_message(to: str = Form(...), message: str = Form(...)):
    try:
        response = wa.send_message(to=to, text=message)
        new_message = {
            "id": response,
            "from": BUSINESS_PHONE_NUMBER_ID,
            "to": to,
            "text": message,
            "timestamp": datetime.datetime.now().isoformat(),
            "status": "sent"
        }
        if to not in conversations:
            conversations[to] = []
        conversations[to].append(new_message)
        await broadcast_message(json.dumps({"type": "new_message", "message": new_message}))
        return JSONResponse(content={"success": True, "message_id": response})
    except AuthenticationError as e:
        logger.error(f"Authentication error: {e}")
        return JSONResponse(content={"success": False, "error": "Authentication failed"}, status_code=401)
    except PermissionError as e:
        logger.error(f"Permission error: {e}")
        return JSONResponse(content={"success": False, "error": "Permission denied"}, status_code=403)
    except RateLimitError as e:
        logger.error(f"Rate limit error: {e}")
        return JSONResponse(content={"success": False, "error": "Rate limit exceeded"}, status_code=429)
    except NotFoundError as e:
        logger.error(f"Not found error: {e}")
        return JSONResponse(content={"success": False, "error": "Resource not found"}, status_code=404)
    except BadRequestError as e:
        logger.error(f"Bad request error: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=400)
    except ServerError as e:
        logger.error(f"Server error: {e}")
        return JSONResponse(content={"success": False, "error": "Server error occurred"}, status_code=500)
    except TimeoutError as e:
        logger.error(f"Timeout error: {e}")
        return JSONResponse(content={"success": False, "error": "Request timed out"}, status_code=504)
    except BaseError as e:
        logger.error(f"WhatsApp API error: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)
    except Exception as e:
        logger.error(f"Unexpected error in send_message: {e}", exc_info=True)
        return JSONResponse(content={"success": False, "error": "An unexpected error occurred"}, status_code=500)


# Create a global variable to store received messages
received_messages = []


# New endpoint to get new messages
@fastapi_app.get("/get_messages")
async def get_messages():
    global received_messages
    messages = [{"text": msg, "from": "unknown"} for msg in received_messages]
    received_messages = []  # Clear the messages after sending
    return JSONResponse(content={"messages": messages})


# New endpoint to get all messages (both past and real-time)
@fastapi_app.get("/get_all_messages")
async def get_all_messages():
    # In a real application, you would fetch messages from your database
    # For this example, we'll return some dummy data
    return JSONResponse(
        content={
            "messages": [{
                "id": 1,
                "text": "Past message 1",
                "timestamp": "2023-05-01T10:00:00Z"
            }, {
                "id": 2,
                "text": "Past message 2",
                "timestamp": "2023-05-01T11:00:00Z"
            }, {
                "id": 3,
                "text": "Real-time message",
                "timestamp": "2023-05-01T12:00:00Z"
            }]
        })


@wa.on_callback_button(filters.startswith("id"))
def click_me(client: WhatsApp, clb: CallbackButton):
    try:
        clb.reply_text("You clicked me!")
    except Exception as e:
        print(f"Error in click_me handler: {e}")


@wa.on_callback_selection()
def handle_selection(client: WhatsApp, selection: CallbackSelection):
    try:
        selection.reply_text(f"You selected: {selection.title}")
    except Exception as e:
        print(f"Error in handle_selection: {e}")


@wa.on_flow_completion()
def handle_flow_completion(client: WhatsApp, completion: FlowCompletion):
    try:
        completion.reply_text("Thank you for completing the flow!")
    except Exception as e:
        print(f"Error in handle_flow_completion: {e}")


@wa.on_message_status()
def handle_message_status(client: WhatsApp, status: MessageStatus):
    try:
        message_id = status.id
        status_type = status.status.value  # Convert enum to string
        logger.info(f"Message status update: {status_type} for message {message_id}")
        
        # Broadcast the status update to all connected WebSocket clients
        asyncio.create_task(broadcast_message(json.dumps({
            "type": "status_update",
            "status": {
                "id": message_id,
                "status": status_type,
                "timestamp": status.timestamp.isoformat()
            }
        })))
    except Exception as e:
        logger.error(f"Error in handle_message_status: {e}", exc_info=True)


@wa.on_template_status()
def handle_template_status(client: WhatsApp, status: TemplateStatus):
    try:
        print(
            f"Template status update: {status.event} for template {status.template_name}"
        )
    except Exception as e:
        print(f"Error in handle_template_status: {e}")


@wa.on_chat_opened()
def handle_chat_opened(client: WhatsApp, chat: ChatOpened):
    try:
        client.send_message(to=chat.from_user.wa_id,
                            text="Welcome! How can I assist you today?")
    except Exception as e:
        print(f"Error in handle_chat_opened: {e}")


# Update the contacts list with a default contact
contacts = [
    {"number": "+905330475085", "name": "Default Contact"}
]

# Update the get_contacts route
@fastapi_app.get("/get_contacts")
async def get_contacts():
    logger.info(f"Returning contacts: {contacts}")
    return JSONResponse(content=contacts)

# Add a new route to add contacts
@fastapi_app.post("/add_contact")
async def add_contact(number: str = Form(...), name: str = Form(...)):
    new_contact = {"number": number, "name": name}
    contacts.append(new_contact)
    logger.info(f"New contact added: {new_contact}")
    return JSONResponse(content={"success": True, "contact": new_contact})

# Modify the get_messages_for_contact route
@fastapi_app.get("/get_messages/{contact_id}")
async def get_messages_for_contact(contact_id: str):
    if contact_id not in conversations:
        conversations[contact_id] = []
    return JSONResponse(content={"messages": conversations[contact_id]})

# Add this import at the top of the file
import json

# ... (rest of the code remains the same)

# Create a dictionary to store conversations
conversations = {}

# Modify the get_messages_for_contact route
@fastapi_app.get("/get_messages/{contact_id}")
async def get_messages_for_contact(contact_id: str):
    if contact_id not in conversations:
        conversations[contact_id] = []
    return JSONResponse(content={"messages": conversations[contact_id]})

# Modify the send_message endpoint
@fastapi_app.post("/send_message")
async def send_message(to: str = Form(...), message: str = Form(...)):
    try:
        response = wa.send_message(to=to, text=message)
        new_message = {
            "id": response,
            "from": BUSINESS_PHONE_NUMBER_ID,
            "to": to,
            "text": message,
            "timestamp": datetime.datetime.now().isoformat(),
            "status": "sent"
        }
        if to not in conversations:
            conversations[to] = []
        conversations[to].append(new_message)
        await broadcast_message(json.dumps({"type": "new_message", "message": new_message}))
        return JSONResponse(content={"success": True, "message_id": response})
    except AuthenticationError as e:
        logger.error(f"Authentication error: {e}")
        return JSONResponse(content={"success": False, "error": "Authentication failed"}, status_code=401)
    except PermissionError as e:
        logger.error(f"Permission error: {e}")
        return JSONResponse(content={"success": False, "error": "Permission denied"}, status_code=403)
    except RateLimitError as e:
        logger.error(f"Rate limit error: {e}")
        return JSONResponse(content={"success": False, "error": "Rate limit exceeded"}, status_code=429)
    except NotFoundError as e:
        logger.error(f"Not found error: {e}")
        return JSONResponse(content={"success": False, "error": "Resource not found"}, status_code=404)
    except BadRequestError as e:
        logger.error(f"Bad request error: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=400)
    except ServerError as e:
        logger.error(f"Server error: {e}")
        return JSONResponse(content={"success": False, "error": "Server error occurred"}, status_code=500)
    except TimeoutError as e:
        logger.error(f"Timeout error: {e}")
        return JSONResponse(content={"success": False, "error": "Request timed out"}, status_code=504)
    except BaseError as e:
        logger.error(f"WhatsApp API error: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)
    except Exception as e:
        logger.error(f"Unexpected error in send_message: {e}", exc_info=True)
        return JSONResponse(content={"success": False, "error": "An unexpected error occurred"}, status_code=500)

# Add this global variable to keep track of processed message IDs
processed_message_ids = set()

@wa.on_raw_update()
def handle_raw_update(client: WhatsApp, update: dict):
    logger.info(f"Received raw update: {update}")
    try:
        if 'entry' in update and len(update['entry']) > 0:
            changes = update['entry'][0].get('changes', [])
            for change in changes:
                if 'value' in change:
                    value = change['value']
                    if 'messages' in value:
                        for message in value['messages']:
                            if message['type'] == 'text':
                                message_id = message['id']
                                if message_id in processed_message_ids:
                                    logger.info(f"Skipping already processed message: {message_id}")
                                    continue
                                processed_message_ids.add(message_id)
                                
                                text = message['text']['body']
                                from_id = message['from']
                                logger.info(f"Received message: '{text}' from {from_id}")
                                new_message = {
                                    "id": message_id,
                                    "from": from_id,
                                    "to": BUSINESS_PHONE_NUMBER_ID,
                                    "text": text,
                                    "timestamp": datetime.datetime.now().isoformat(),
                                    "status": "received"
                                }
                                if from_id not in conversations:
                                    conversations[from_id] = []
                                    send_welcome_message(client, from_id, text)
                                conversations[from_id].append(new_message)
                                asyncio.create_task(broadcast_message(json.dumps({
                                    "type": "new_message",
                                    "message": new_message
                                })))
                    elif 'statuses' in value:
                        for status in value['statuses']:
                            logger.info(f"Received status update: {status}")
                            asyncio.create_task(broadcast_message(json.dumps({
                                "type": "status_update",
                                "status": status
                            })))
    except ValidationError as e:
        logger.error(f"Validation error in handle_raw_update: {e}")
    except KeyError as e:
        logger.error(f"Key error in handle_raw_update: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in handle_raw_update: {e}", exc_info=True)

# Update the send_welcome_message function with better error handling
def send_welcome_message(client: WhatsApp, from_id: str, text: str):
    logger.info(f"Sending welcome message to {from_id}")
    try:
        response = client.send_message(
            to=from_id,
            text="Welcome! How can I assist you today?"
        )
        logger.info(f"Sent welcome response: {response}")
    except AuthenticationError as e:
        logger.error(f"Authentication error in send_welcome_message: {e}")
    except PermissionError as e:
        logger.error(f"Permission error in send_welcome_message: {e}")
    except RateLimitError as e:
        logger.error(f"Rate limit error in send_welcome_message: {e}")
    except NotFoundError as e:
        logger.error(f"Not found error in send_welcome_message: {e}")
    except BadRequestError as e:
        logger.error(f"Bad request error in send_welcome_message: {e}")
    except ServerError as e:
        logger.error(f"Server error in send_welcome_message: {e}")
    except TimeoutError as e:
        logger.error(f"Timeout error in send_welcome_message: {e}")
    except BaseError as e:
        logger.error(f"WhatsApp API error in send_welcome_message: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in send_welcome_message: {e}", exc_info=True)

# Add this global variable
connected_clients = set()

# Update the WebSocket endpoint
@fastapi_app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"Received WebSocket message: {data}")
            await broadcast_message(data)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except ConnectionClosedError as e:
        logger.error(f"WebSocket connection closed unexpectedly: {e}")
    except Exception as e:
        logger.error(f"Unexpected WebSocket error: {e}", exc_info=True)
    finally:
        connected_clients.remove(websocket)

async def broadcast_message(message):
    logger.info(f"Broadcasting message: {message}")
    disconnected_clients = set()
    for client in connected_clients:
        try:
            await client.send_text(message)
        except ConnectionClosedError as e:
            logger.error(f"Error sending message to client (connection closed): {e}")
            disconnected_clients.add(client)
        except WebSocketDisconnect:
            logger.error("Error sending message to client (WebSocket disconnected)")
            disconnected_clients.add(client)
        except Exception as e:
            logger.error(f"Unexpected error sending message to client: {e}", exc_info=True)
            disconnected_clients.add(client)
    
    for client in disconnected_clients:
        connected_clients.remove(client)

def echo_message(client: WhatsApp, from_id: str, text: str):
    logger.info(f"Echoing message: {text} to {from_id}")
    try:
        response = client.send_message(to=from_id, text=f"Echo: {text}")
        logger.info(f"Sent echo response: {response}")

        # Add more detailed logging
        logger.info(f"Response details: {response}")

        # Verify the response
        if isinstance(response, str) and response.startswith("wamid."):
            logger.info("Message sent successfully")
        else:
            logger.error(f"Unexpected response format: {response}")
    except Exception as e:
        logger.error(f"Error in echo_message: {e}", exc_info=True)

        # Add more detailed error logging
        if hasattr(e, 'response'):
            logger.error(f"Error response: {e.response.text}")


# Modify the hello function to accept raw data
def hello(client: WhatsApp, from_id: str, text: str):
    logger.info(f"Received message: {text} from {from_id}")
    try:
        response = client.send_message(
            to=from_id,
            text=f"Hello there! You said: {text}",
            buttons=[Button(title="Click me!", callback_data="id:123")])
        logger.info(f"Sent response: {response}")
    except Exception as e:
        logger.error(f"Error in hello handler: {e}", exc_info=True)


# Error handler
@fastapi_app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail},
    )


# Global exception handler
@fastapi_app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "message": "An unexpected error occurred.",
            "error": str(exc)
        },
    )


# If you want to use Handler objects instead of decorators, you can do:
# from pywa.handlers import MessageHandler, CallbackButtonHandler
# wa.add_handlers(
#     MessageHandler(hello, filters.matches("Hello", "Hi")),
#     CallbackButtonHandler(click_me, filters.startswith("id"))
# )


def send_welcome_message(client: WhatsApp, from_id: str, text: str):
    logger.info(f"Sending welcome message to {from_id}")
    try:
        response = client.send_message(
            to=from_id,
            text="Welcome! How can I assist you today?"
        )
        logger.info(f"Sent welcome response: {response}")
    except Exception as e:
        logger.error(f"Error in send_welcome_message: {e}", exc_info=True)
