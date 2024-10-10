import logging
from logging.handlers import RotatingFileHandler
import os
from fastapi import FastAPI, Request, Query, HTTPException, Body, Form, WebSocket, UploadFile, File
from fastapi.responses import PlainTextResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pywa import WhatsApp, filters
from pywa.types import Message, Button, CallbackButton, CallbackData, CallbackSelection, FlowCompletion, MessageStatus, TemplateStatus, ChatOpened, Button, MessageStatusType, Command
from fastapi.websockets import WebSocketDisconnect
import datetime
import asyncio
import json
from pywa import errors as pywa_errors
from dataclasses import dataclass
from dotenv import load_dotenv
from aiTools import get_ai_response
from ai_siparis import OrderManager, OrderState
from typing import List, Dict, Any, Optional, Union
from airtable_cargo import check_tracking_number, upload_image_to_airtable
from checker import check_received_media
from mediaActions import handle_image_upload

# Ensure the logs directory exists
os.makedirs('logs', exist_ok=True)

# Logging configuration
def setup_logger(name, log_file, level=logging.INFO):
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Create logs directory if it doesn't exist
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    # Add a stream handler to print logs to console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

# Setup loggers
wa_logger = setup_logger('wa', 'logs/wa.log', level=logging.DEBUG)
main_logger = setup_logger('main', 'logs/main.log', level=logging.DEBUG)

# Use wa_logger for WhatsApp specific logs
# Use main_logger for general application logs

# Load environment variables
load_dotenv()

# Initialize FastAPI application
fastapi_app = FastAPI()

# Mount static files
fastapi_app.mount("/static", StaticFiles(directory="static"), name="static")

# Set up Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Update the WhatsApp client initialization
wa = WhatsApp(phone_id=os.getenv("WHATSAPP_PHONE_ID"),
              token=os.getenv("WHATSAPP_TOKEN"),
              server=fastapi_app,
              callback_url=os.getenv("WHATSAPP_CALLBACK_URL"),
              verify_token=os.getenv("WHATSAPP_VERIFY_TOKEN"),
              app_id=int(os.getenv("WHATSAPP_APP_ID")),
              app_secret=os.getenv("WHATSAPP_APP_SECRET"),
              validate_updates=True,
              continue_handling=True)

BUSINESS_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_ID")

# Update the contacts list with a default contact
contacts = [{"number": "+905330475085", "name": "Default Contact"}]

# Initialize conversations as a dictionary
conversations = {}

# Create a separate log file for conversation logs
conversation_logger = logging.getLogger("conversation")
conversation_handler = logging.FileHandler('logs/conversation.log')
conversation_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
conversation_handler.setFormatter(formatter)
conversation_logger.addHandler(conversation_handler)

# Add this near the top of the file, after the FastAPI app initialization
fastapi_app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Ensure the uploads directory exists
os.makedirs("uploads", exist_ok=True)

# Add this global variable
connected_clients = set()

# Add this to your global variables
users_greeted = set()

# Initialize the OrderManager
order_manager = OrderManager()

# Add a flag to track whether the menu has been sent
menu_sent = {}

# Add this global variable to track processed messages
processed_messages = set()


# Step 1: Define our custom CallbackData
@dataclass(frozen=True, slots=True)
class ButtonAction(CallbackData):
    action: str
    value: str
    image: str = None


# Step 2: Create a function to send a message with buttons
def send_message_with_buttons(client: WhatsApp, to: str):
    buttons = [
        Button(title="Ürünleri Göster",
               callback_data=ButtonAction(action="option",
                                          value="1",
                                          image="1.jpeg")),
        Button(title="Musteri temsicilisi",
               callback_data=ButtonAction(action="option", value="2")),
        Button(title="Kargo Sorgula",
               callback_data=ButtonAction(action="help", value="general"))
    ]

    client.send_message(to=to,
                        text="Başka bir konuda yardımcı olabilir miyim?",
                        buttons=buttons)


# Step 5: Define thez callback handler
@wa.on_callback_button(factory=ButtonAction)
async def handle_button_press(client: WhatsApp, btn: CallbackButton[ButtonAction]):
    wa_logger.info(f"Button pressed: {btn.data.action}")
    user_id = btn.from_user.wa_id
    
    try:
        if btn.data.action == "more_options" and btn.data.value == "more":
            wa_logger.info(f"User {user_id} requested more options")
            await send_more_options(client, user_id)
            return
        elif btn.data.action == "main_menu" and btn.data.value == "main":
            wa_logger.info(f"User {user_id} requested main menu")
            await send_menu_buttons(client, user_id)
            return
        elif btn.data.action == "choose_product":
            wa_logger.info(f"User {user_id} selected product: {btn.data.value}")
            order = order_manager.get_or_create_order(user_id)
            order['product_id'] = btn.data.value
            order['state'] = OrderState.COLLECTING_NAME  # Set the state to start collecting information
            response = "Siparişinizi almaya başlıyoruz. Lütfen adınızı ve soyadınızı girin."
        elif btn.data.action == "option":
            if btn.data.value == "1":
                wa_logger.info(f"User {user_id} requested product list")
                await send_product_list(client, user_id)
                return
            elif btn.data.value == "2":
                wa_logger.info(f"User {user_id} requested customer service")
                response = "Lütfen sorunuzu sorun, size yardımcı olmaya çalışacağım."
            else:
                wa_logger.warning(f"Unknown option selected by user {user_id}: {btn.data.value}")
                response = "Bilinmeyen seçenek"
        elif btn.data.action == "help":
            if btn.data.value == "general":
                wa_logger.info(f"User {user_id} requested cargo tracking")
                response = "Lütfen kargo takip numaranızı girin."
            else:
                wa_logger.warning(f"Unknown help option selected by user {user_id}: {btn.data.value}")
                response = "Bilinmeyen yardım seçeneği"
        elif btn.data.action in ["confirm_order_yes", "confirm_order_no"] or btn.data.action.startswith("correct_"):
            wa_logger.info(f"Processing order action for user {user_id}: {btn.data.action}")
            response = order_manager.process_message(user_id, btn.data.action)
            if btn.data.action == "confirm_order_yes":
                # Reset the order state after successful completion
                order_manager.reset_order(user_id)
        elif btn.data.action == "upload_image" and btn.data.value == "cargo":
            wa_logger.info(f"User {user_id} requested to upload an image for cargo")
            response = "Lütfen kargo için bir resim gönderin. Resmi aldıktan sonra takip numarasını soracağım."
            # Set a flag or state to indicate we're waiting for an image
            conversations[user_id] = {"waiting_for": "cargo_image"}
        else:
            wa_logger.warning(f"Unknown button action from user {user_id}: {btn.data.action}")
            response = "Bilinmeyen işlem"

        wa_logger.info(f"Sending response to user {user_id}: {response}")
        if isinstance(response, dict):
            await send_response(client, user_id, response)
        else:
            client.send_message(to=user_id, text=str(response))
    except Exception as e:
        wa_logger.error(f"Error in handle_button_press for user {user_id}: {str(e)}", exc_info=True)
        await send_menu_buttons(client, user_id)


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
        wa_logger.info(f"Received webhook data: {data}")
        response, status_code = await wa.webhook_update_handler(
            update=data,
            raw_body=body,
            hmac_header=request.headers.get("X-Hub-Signature-256"))
        wa_logger.info(f"Webhook handler response: {response}, status: {status_code}")

        # Process the incoming message
        if 'messages' in data['entry'][0]['changes'][0]['value']:
            message = data['entry'][0]['changes'][0]['value']['messages'][0]
            # Log the conversation
            conversation_logger.info(f"Message from {message['from']}: {message['text']}")
            # Broadcast the message to all connected WebSocket clients
            for client in connected_clients:
                await client.send_json(message)

        return PlainTextResponse(content=response, status_code=status_code)
    except Exception as e:
        wa_logger.error(f"Error in receive_webhook: {e}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)


# Serve the home page
@fastapi_app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


# Serve the chat page
@fastapi_app.get("/chat")
async def chat(request: Request):
    return templates.TemplateResponse("chat5.html", {
        "request": request,
        "business_phone_number_id": wa.phone_id
    })


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
        await broadcast_message(
            json.dumps({
                "type": "new_message",
                "message": new_message
            }))
        return JSONResponse(content={"success": True, "message_id": response})
    except Exception as e:
        wa_logger.error(f"Error in send_message: {e}", exc_info=True)
        return JSONResponse(content={
            "success": False,
            "error": str(e)
        },
                            status_code=500)


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


@wa.on_message_status()
def handle_message_status(client: WhatsApp, status: MessageStatus):
    try:
        message_id = status.id
        status_type = status.status.value  # Convert enum to string
        wa_logger.info(
            f"Message status update: {status_type} for message {message_id}")

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
                })))
    except Exception as e:
        wa_logger.error(f"Error in handle_message_status: {e}", exc_info=True)


# Update the get_contacts route
@fastapi_app.get("/get_contacts")
async def get_contacts():
    main_logger.info(f"Returning contacts: {contacts}")
    return JSONResponse(content=contacts)


# Add a new route to add contacts
@fastapi_app.post("/add_contact")
async def add_contact(number: str = Form(...), name: str = Form(...)):
    new_contact = {"number": number, "name": name}
    contacts.append(new_contact)
    main_logger.info(f"New contact added: {new_contact}")
    return JSONResponse(content={"success": True, "contact": new_contact})


# Modify the get_messages_for_contact route
@fastapi_app.get("/get_messages/{contact_id}")
async def get_messages_for_contact(contact_id: str):
    if contact_id not in conversations:
        conversations[contact_id] = []
    main_logger.info(
        f"Returning messages for contact {contact_id}: {conversations[contact_id]}"
    )
    return JSONResponse(content={"messages": conversations[contact_id]})


# Add this global variable to keep track of processed message IDs
processed_message_ids = set()


# Update the handle_raw_update function
@wa.on_raw_update()
def handle_raw_update(client: WhatsApp, update: dict):
    wa_logger.info(f"Received raw update: {update}")
    try:
        if 'entry' in update and len(update['entry']) > 0:
            changes = update['entry'][0].get('changes', [])
            for change in changes:
                if 'value' in change:
                    value = change['value']
                    if 'messages' in value:
                        for message in value['messages']:
                            message_id = message['id']
                            if message_id in processed_message_ids:
                                wa_logger.info(f"Skipping already processed message: {message_id}")
                                continue
                            processed_message_ids.add(message_id)

                            from_id = message['from']
                            
                            media_info = check_received_media(message)
                            
                            if from_id not in conversations:
                                conversations[from_id] = {"messages": []}
                            
                            new_message = {
                                "id": message_id,
                                "from": from_id,
                                "to": BUSINESS_PHONE_NUMBER_ID,
                                "timestamp": datetime.datetime.now().isoformat(),
                                "status": "received",
                                "type": media_info['type']
                            }

                            if media_info['type'] == 'text':
                                new_message["text"] = media_info['content']
                                conversations[from_id]["messages"].append(new_message)
                            elif media_info['type'] in ['image', 'video']:
                                new_message[media_info['type']] = {
                                    "id": media_info['id'],
                                    "mime_type": media_info['mime_type']
                                }
                                # Don't append image messages to conversations
                                wa_logger.info(f"Received {media_info['type']} message from {from_id}")
                            elif media_info['type'] == 'interactive':
                                new_message["interactive"] = media_info['content']
                                conversations[from_id]["messages"].append(new_message)
                            else:
                                conversations[from_id]["messages"].append(new_message)

                            asyncio.create_task(
                                broadcast_message(
                                    json.dumps({
                                        "type": "new_message",
                                        "message": new_message
                                    })))

                            # Handle the message
                            asyncio.create_task(handle_message(client, new_message))

                    elif 'statuses' in value:
                        for status in value['statuses']:
                            wa_logger.info(f"Received status update: {status}")
                            asyncio.create_task(
                                broadcast_message(
                                    json.dumps({
                                        "type": "status_update",
                                        "status": status
                                    })))
    except Exception as e:
        wa_logger.error(f"Unexpected error in handle_raw_update: {str(e)}", exc_info=True)


# Update the handle_message function
@wa.on_message()
async def handle_message(client: WhatsApp, message: Union[dict, Message]):
    if isinstance(message, Message):
        user_id = message.from_user.wa_id
        message_type = message.type
        message_id = message.id
    else:
        user_id = message['from']
        message_type = message['type']
        message_id = message['id']

    wa_logger.info(f"Processing message from {user_id} - Type: {message_type}, ID: {message_id}")

    if message_type == 'image':
        wa_logger.info(f"Processing image message from user {user_id}")
        image_id = message['image']['id'] if isinstance(message, dict) else message.image.id
        if image_id:
            wa_logger.info(f"Image ID: {image_id}")
            result = handle_image_upload(client, user_id, image_id, conversations)
            client.send_message(to=user_id, text=result)
        else:
            wa_logger.warning(f"Received image message without image ID from user {user_id}")
            client.send_message(to=user_id, text="Resim alınamadı. Lütfen tekrar deneyin.")
        await send_menu_buttons(client, user_id)
        return

    elif message_type == 'text':
        text = message['text'] if isinstance(message, dict) else message.text
        wa_logger.info(f"Processing text message from user {user_id}: {text}")
        # ... (rest of the existing code for handling text messages)

    elif message_type == 'interactive':
        wa_logger.info(f"Processing interactive message from user {user_id}")
        interactive = message['interactive'] if isinstance(message, dict) else message.interactive
        if interactive['type'] == 'button_reply':
            button_id = interactive['button_reply']['id']
            wa_logger.info(f"Button pressed: {button_id}")
            # Handle button press
            if button_id == '1~upload_image~cargo~¤':
                wa_logger.info(f"User {user_id} requested to upload an image for cargo")
                conversations[user_id]["waiting_for"] = "cargo_image"
                client.send_message(to=user_id, text="Lütfen kargo için bir resim gönderin. Resmi aldıktan sonra takip numarasını soracağım.")
            # ... (handle other button presses)

    else:
        wa_logger.info(f"Received unsupported message type from user {user_id}: {message_type}")
        client.send_message(to=user_id, text="Üzgünüm, bu mesaj türünü işleyemiyorum.")
        await send_menu_buttons(client, user_id)


# Update the WebSocket endpoint
@fastapi_app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            wa_logger.info(f"Received WebSocket message: {data}")
            await broadcast_message(data)
    except WebSocketDisconnect:
        wa_logger.info("WebSocket disconnected")
    except Exception as e:
        wa_logger.error(f"Unexpected WebSocket error: {e}", exc_info=True)
    finally:
        connected_clients.remove(websocket)


async def broadcast_message(message):
    wa_logger.info(f"Broadcasting message: {message}")
    disconnected_clients = set()
    for client in connected_clients:
        try:
            await client.send_text(message)
        except Exception as e:
            wa_logger.error(f"Error sending message to client: {e}",
                         exc_info=True)
            disconnected_clients.add(client)

    for client in disconnected_clients:
        connected_clients.remove(client)


async def send_welcome_message(client: WhatsApp, to: str):
    wa_logger.info(f"Sending welcome message to {to}")
    welcome_text = "Merhaba! Hoş geldiniz. Size nasıl yardımcı olabilirim?"
    client.send_message(to=to, text=welcome_text)
    await send_menu_buttons(client, to)


@fastapi_app.post("/send_image")
async def send_image(to: str = Form(...), image: UploadFile = File(...)):
    try:
        # Save the image
        file_location = f"uploads/products/{image.filename}"
        with open(file_location, "wb+") as file_object:
            file_object.write(await image.read())

        # Send the image using PyWa
        response = wa.send_image(to=to,
                                 image=file_location,
                                 caption="Sent from BirHediyenOlsun Wp")

        # Generate the URL for the uploaded image
        image_url = f"{fastapi_app.url_path_for('static', path=image.filename)}"

        return JSONResponse(content={
            "success": True,
            "message_id": response,
            "image_url": image_url
        })
    except Exception as e:
        wa_logger.error(f"Error sending image: {e}", exc_info=True)
        return JSONResponse(content={
            "success": False,
            "error": str(e)
        },
                            status_code=500)


async def send_image_button(client: WhatsApp, to: str, image_file: str, caption: str):
    wa_logger.info(f"Sending image button to {to}")
    try:
        image_path = f"uploads/products/{image_file}"
        if os.path.exists(image_path):
            with open(image_path, "rb") as image:
                client.send_image(
                    to=to,
                    image=image,
                    caption=caption,
                    buttons=[
                        Button(title="Sipariş Ver", callback_data=ButtonAction(action="choose_product", value=image_file.split('.')[0]))
                    ],
                    mime_type="image/jpeg"
                )
            wa_logger.info(f"Image sent successfully: {image_file}")
        else:
            wa_logger.error(f"Image file not found: {image_path}")
            client.send_message(to=to, text="Üzgünüm, istediğiniz ürün resmi bulunamadı.")
    except Exception as e:
        wa_logger.error(f"Error sending image for user {to}: {str(e)}", exc_info=True)
        client.send_message(to=to, text="Ürün resmini gönderirken bir hata oluştu. Lütfen daha sonra tekrar deneyin.")


async def send_response(client: WhatsApp, to: str, response: Dict[str, Any]):
    try:
        if isinstance(response, dict):
            message_text = response.get('text', '')
            buttons = response.get('buttons', [])
            
            if buttons:
                # Ensure we don't exceed the maximum number of buttons
                buttons = buttons[:3]
                client.send_message(to=to, text=message_text, buttons=[
                    Button(title=b['title'], callback_data=ButtonAction(action=b['callback_data'], value="")) for b in buttons
                ])
            else:
                client.send_message(to=to, text=message_text)
        else:
            client.send_message(to=to, text=str(response))
    except Exception as e:
        wa_logger.error(f"Error in send_response: {str(e)}", exc_info=True)
        # Send a simple text message if there's an error with buttons
        client.send_message(to=to, text="Üzgünüm, bir hata oluştu. Lütfen tekrar deneyin.")


async def send_menu_buttons(client: WhatsApp, to: str):
    buttons = [
        Button(title="Ürünleri Göster", callback_data=ButtonAction(action="option", value="1")),
        Button(title="Musteri temsilcisi", callback_data=ButtonAction(action="option", value="2")),
        Button(title="Diğer İşlemler", callback_data=ButtonAction(action="more_options", value="more"))
    ]
    client.send_message(to=to, text="Lütfen bir seçenek belirleyin:", buttons=buttons)


# Add a new function to handle the "Diğer İşlemler" button
async def send_more_options(client: WhatsApp, to: str):
    buttons = [
        Button(title="Kargo Sorgula", callback_data=ButtonAction(action="help", value="general")),
        Button(title="Resim Yükle", callback_data=ButtonAction(action="upload_image", value="cargo")),
        Button(title="Ana Menü", callback_data=ButtonAction(action="main_menu", value="main"))
    ]
    client.send_message(to=to, text="Diğer işlemler:", buttons=buttons)


# Error handler
@fastapi_app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    main_logger.error(f"HTTP Exception: {exc.detail}", exc_info=True)
    return JSONResponse(status_code=exc.status_code,
                        content={"message": exc.detail})

# Global exception handler
@fastapi_app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    main_logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(status_code=500,
                        content={
                            "message": "An unexpected error occurred.",
                            "error": str(exc)
                        })

async def send_product_list(client: WhatsApp, to: str):
    wa_logger.info(f"Sending product list to user {to}")
    try:
        image_files = [f for f in os.listdir("uploads/products") if f.endswith(".jpeg")]
        wa_logger.info(f"Found {len(image_files)} product images")
        for i, image_file in enumerate(image_files):
            wa_logger.info(f"Sending product image {i+1}: {image_file}")
            await send_image_button(client, to, image_file, f"Ürün ID: {i+1}")
        if not image_files:
            wa_logger.warning("No product images found")
            client.send_message(to=to, text="Üzgünüm, şu anda gösterilecek ürün bulunmamaktadır.")
    except Exception as e:
        wa_logger.error(f"Error in send_product_list for user {to}: {str(e)}", exc_info=True)
        client.send_message(to=to, text="Ürünleri gösterirken bir hata oluştu. Lütfen daha sonra tekrar deneyin.")