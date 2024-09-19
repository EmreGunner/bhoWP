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
from pywa import errors as pywa_errors
import os

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
    token="EAAOxaNntzsEBO36pkDY4rgkQYIW5vSmMUOZAHx1h2ZBGkgwe9TerLdYGdaQn8POhvq6ioGjYyQgRg1M0gRgxYAwlMYeb9Jul8G4WfaXMCwL87DABwgW7BZCSM9bHlJBgKDwT6qujgVK9Ev2U6juzeZBcrUkn27DeafwOz6ZBYQMnfUXZCEp7RzYpz3kumiiKVZBMlJhA35nwI0I6rGwwRcnbRKKjtAZD",
    server=fastapi_app,
    callback_url="https://49ae544d-ebdc-4b20-9445-aa092113c69a-00-1cr1zoiat6wtd.sisko.replit.dev",
    verify_token="randomstring",
    app_id=1039488821087937,
    app_secret="eda6cba58fa6404a8198b205face33aa",
    validate_updates=True,
    continue_handling=True
)

# Add this line near the top of the file, after the imports
BUSINESS_PHONE_NUMBER_ID = "347058841835061"

# Update the contacts list with a default contact
contacts = [{"number": "+905330475085", "name": "Default Contact"}]

# Create a dictionary to store conversations
conversations = {}

# Add this near the top of the file, after the FastAPI app initialization
fastapi_app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Ensure the uploads directory exists
os.makedirs("uploads", exist_ok=True)

# Add this global variable
connected_clients = set()

# Update the webhook verification endpoint
@fastapi_app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

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
            "messages": [
                {"id": 1, "text": "Past message 1", "timestamp": "2023-05-01T10:00:00Z"},
                {"id": 2, "text": "Past message 2", "timestamp": "2023-05-01T11:00:00Z"},
                {"id": 3, "text": "Real-time message", "timestamp": "2023-05-01T12:00:00Z"}
            ]
        }
    )

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
        asyncio.create_task(
            broadcast_message(
                json.dumps({
                    "type": "status_update",
                    "status": {
                        "id": message_id,
                        "status": status_type,
                        "timestamp": status.timestamp.isoformat()
                    }
                })
            )
        )
    except Exception as e:
        logger.error(f"Error in handle_message_status: {e}", exc_info=True)

@wa.on_template_status()
def handle_template_status(client: WhatsApp, status: TemplateStatus):
    try:
        print(f"Template status update: {status.event} for template {status.template_name}")
    except Exception as e:
        print(f"Error in handle_template_status: {e}")

@wa.on_chat_opened()
def handle_chat_opened(client: WhatsApp, chat: ChatOpened):
    try:
        client.send_message(to=chat.from_user.wa_id, text="Welcome! How can I assist you today?")
    except Exception as e:
        print(f"Error in handle_chat_opened: {e}")

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
    logger.info(f"Returning messages for contact {contact_id}: {conversations[contact_id]}")
    return JSONResponse(content={"messages": conversations[contact_id]})

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
                                asyncio.create_task(
                                    broadcast_message(
                                        json.dumps({
                                            "type": "new_message",
                                            "message": new_message
                                        })
                                    )
                                )
                    elif 'statuses' in value:
                        for status in value['statuses']:
                            logger.info(f"Received status update: {status}")
                            asyncio.create_task(
                                broadcast_message(
                                    json.dumps({
                                        "type": "status_update",
                                        "status": status
                                    })
                                )
                            )
    except pywa_errors.ValidationError as e:
        logger.error(f"Validation error in handle_raw_update: {e}")
    except KeyError as e:
        logger.error(f"Key error in handle_raw_update: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in handle_raw_update: {e}", exc_info=True)

# Add the send_and_broadcast_message function
async def send_and_broadcast_message(to: str, message: str):
    try:
        # Send the message using the WhatsApp client
        response = wa.send_message(to=to, text=message)
        
        # Create a new message object
        new_message = {
            "id": response,
            "from": BUSINESS_PHONE_NUMBER_ID,
            "to": to,
            "text": message,
            "timestamp": datetime.datetime.now().isoformat(),
            "status": "sent"
        }
        
        # Add the message to the conversations dictionary
        if to not in conversations:
            conversations[to] = []
        conversations[to].append(new_message)
        
        # Broadcast the message to all connected WebSocket clients
        await broadcast_message(json.dumps({
            "type": "new_message",
            "message": new_message
        }))
        
        return new_message
    except Exception as e:
        logger.error(f"Error in send_and_broadcast_message: {e}", exc_info=True)
        raise

# Update the send_message endpoint to use the new function
@fastapi_app.post("/send_message")
async def send_message(to: str = Form(...), message: str = Form(...)):
    try:
        new_message = await send_and_broadcast_message(to, message)
        return JSONResponse(content={"success": True, "message_id": new_message["id"]})
    except Exception as e:
        logger.error(f"Error in send_message endpoint: {e}", exc_info=True)
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)

# Update the send_welcome_message function
async def send_welcome_message(client: WhatsApp, from_id: str, text: str):
    logger.info(f"Sending welcome message to {from_id}")
    try:
        await send_and_broadcast_message(from_id, "Welcome! How can I assist you today?")
    except Exception as e:
        logger.error(f"Error in send_welcome_message: {e}", exc_info=True)

# Update the handle_greeting function
@wa.on_message(filters.regex(r"(?i)^(hello|hi|hey)$"))
async def handle_greeting(client: WhatsApp, message: Message):
    await send_and_broadcast_message(message.from_user.wa_id, "Hello! How can I help you today?")

# Ensure the broadcast_message function exists
async def broadcast_message(message: str):
    for client in connected_clients:
        try:
            await client.send_text(message)
        except Exception as e:
            logger.error(f"Error broadcasting message to client: {e}")

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
    except Exception as e:
        logger.error(f"Unexpected WebSocket error: {e}", exc_info=True)
    finally:
        connected_clients.remove(websocket)

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
# wa.add_handlers(MessageHandler(hello, filters.matches("Hello", "Hi")),
#     CallbackButtonHandler(click_me, filters.startswith("id"))
# )

@fastapi_app.post("/send_image")
async def send_image(to: str = Form(...), image: UploadFile = File(...)):
    try:
        # Save the image
        file_location = f"uploads/{image.filename}"
        with open(file_location, "wb+") as file_object:
            file_object.write(await image.read())

        # Send the image using PyWa
        response = wa.send_image(to=to, image=file_location, caption="Sent from BirHediyenOlsun Wp")

        # Generate the URL for the uploaded image
        image_url = f"{fastapi_app.url_path_for('static', path=image.filename)}"

        return JSONResponse(content={
            "success": True,
            "message_id": response,
            "image_url": image_url
        })
    except Exception as e:
        logger.error(f"Error sending image: {e}", exc_info=True)
        return JSONResponse(content={
            "success": False,
            "error": str(e)
        }, status_code=500)




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
    except Exception as e:
        logger.error(f"Unexpected WebSocket error: {e}", exc_info=True)
    finally:
        connected_clients.remove(websocket)