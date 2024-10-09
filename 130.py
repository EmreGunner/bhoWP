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
from typing import List, Dict, Any

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

# Create a dictionary to store conversations
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
        Button(title="Ürünleri Göster", callback_data=ButtonAction(action="option", value="1", image="1.jpeg")),
        Button(title="Musteri temsilcisi", callback_data=ButtonAction(action="option", value="2")),
        Button(title="Kargo Sorgula", callback_data=ButtonAction(action="help", value="general"))
    ]
    client.send_message(to=to, text="Başka bir konuda yardımcı olabilir miyim?", buttons=buttons)


# Step 5: Define thez callback handler
@wa.on_callback_button(factory=ButtonAction)
async def handle_button_press(client: WhatsApp, btn: CallbackButton[ButtonAction]):
    wa_logger.info(f"Button pressed: {btn.data.action}")
    user_id = btn.from_user.wa_id
    
    try:
        if btn.data.action == "choose_product":
            product_id = btn.data.value
            wa_logger.info(f"User {user_id} selected product: {product_id}")
            order = order_manager.get_or_create_order(user_id)
            order['product_id'] = product_id  # Set the product_id directly in the order
            response = order_manager.process_message(user_id, "start_order")
        elif btn.data.action == "option":
            if btn.data.value == "1":
                image_files = [f for f in os.listdir("uploads/products") if f.endswith(".jpeg")]
                for i, image_file in enumerate(image_files):
                    send_image_button(client, user_id, image_file, f"Ürün ID: {i+1}")
                return
            elif btn.data.value == "2":
                response = {"text": "Lütfen sorunuzu sorun, size yardımcı olmaya çalışacağım.", "buttons": []}
            else:
                response = {"text": "Bilinmeyen seçenek", "buttons": []}
        elif btn.data.action in ["confirm_order_yes", "confirm_order_no"] or btn.data.action.startswith("correct_"):
            response = order_manager.process_message(user_id, btn.data.action)
        else:
            response = {"text": "Bilinmeyen işlem", "buttons": []}

        await send_response(client, user_id, response)
    except Exception as e:
        wa_logger.error(f"Error in handle_button_press: {str(e)}", exc_info=True)
        send_menu_buttons(client, user_id)


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
                            if message['type'] == 'text':
                                message_id = message['id']
                                if message_id in processed_message_ids:
                                    wa_logger.info(
                                        f"Skipping already processed message: {message_id}"
                                    )
                                    continue
                                processed_message_ids.add(message_id)

                                text = message['text']['body']
                                from_id = message['from']
                                wa_logger.info(
                                    f"Received message: '{text}' from {from_id}"
                                )
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
                                conversations[from_id].append(new_message)
                                asyncio.create_task(
                                    broadcast_message(
                                        json.dumps({
                                            "type": "new_message",
                                            "message": new_message
                                        })))

                                # Handle the message
                                handle_message(client, from_id, text)
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
        wa_logger.error(f"Unexpected error in handle_raw_update: {e}",
                     exc_info=True)


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
    try:
        welcome_text = (
            "Merhaba! BirHediyenOlsun'a hoş geldiniz. "
            "Size nasıl yardımcı olabiliriz? "
            "Aşağıdaki seçeneklerden birini seçebilir veya doğrudan sorunuzu yazabilirsiniz."
        )
        client.send_message(to=to, text=welcome_text)
        wa_logger.info(f"Sent welcome message to {to}")
        
        # Now send the menu buttons
        send_menu_buttons(client, to)
    except Exception as e:
        wa_logger.error(f"Error in send_welcome_message: {e}", exc_info=True)


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
    try:
        with open(f"uploads/products/{image_file}", "rb") as image:
            await client.send_image(
                to=to,
                image=image,
                caption=caption,
                buttons=[
                    Button(title="Ürünü Seç", callback_data=ButtonAction(action="choose_product", value=image_file))
                ]
            )
        wa_logger.info(f"Image sent successfully: {image_file}")
    except Exception as e:
        wa_logger.error(f"Error sending image: {str(e)}", exc_info=True)


@wa.on_message()
async def handle_message(client: WhatsApp, message: Message):
    wa_logger.info(f"Received message from {message.from_user.wa_id}: {message.text}")
    
    # Check if this message has already been processed
    if message.id in processed_messages:
        wa_logger.info(f"Skipping already processed message: {message.id}")
        return
    
    processed_messages.add(message.id)
    
    user_id = message.from_user.wa_id
    text = message.text
    lower_text = text.lower()

    try:
        # Sipariş süreci devam ediyorsa
        order = order_manager.get_or_create_order(user_id)
        wa_logger.debug(f"Current order state for user {user_id}: {order['state']}")
        if order['state'] != OrderState.IDLE:
            wa_logger.info(f"Continuing order process for user {user_id}, current state: {order['state']}")
            response = order_manager.process_message(user_id, text)
            wa_logger.info(f"Order response for ongoing order: {response}")
            await send_response(client, user_id, response)
            return

        if user_id not in users_greeted:
            wa_logger.info(f"Sending welcome message to new user: {user_id}")
            await send_welcome_message(client, user_id)
            users_greeted.add(user_id)
            return

        if lower_text == "/menu":
            wa_logger.info(f"Sending menu buttons to user: {user_id}")
            send_menu_buttons(client, user_id)
            return

        # Reset menu_sent flag when a new conversation starts
        menu_sent[user_id] = False

        automated_responses = {
            "test": "test1",
            "merhaba": "Merhaba! Nasıl yardımcı olabilirim?",
            "yardim": "Musteri temsilcisi yonlendiriyorum",
        }

        if lower_text in automated_responses:
            wa_logger.info(f"Sending automated response for '{lower_text}' to user: {user_id}")
            client.send_message(to=user_id, text=automated_responses[lower_text])
        elif lower_text in ["fiyat nedir?", "fiyat nedir"]:
            wa_logger.info(f"Sending catalog link to user: {user_id}")
            catalog_link = "ornekcataloglink.wp.com"
            response = f"Ürünlerimizin fiyatları hakkında detaylı bilgi için lütfen kataloğumuzu inceleyin: {catalog_link}"
            client.send_message(to=user_id, text=response)
        else:
            wa_logger.info(f"Getting AI response for user: {user_id}")
            ai_response = get_ai_response(text)
            client.send_message(to=user_id, text=ai_response)

        wa_logger.info(f"Sending menu buttons after response to user: {user_id}")
        send_menu_buttons(client, user_id)
    except Exception as e:
        wa_logger.error(f"Error in handle_message: {str(e)}", exc_info=True)


async def send_response(client: WhatsApp, to: str, response: Dict[str, Any]):
    try:
        if isinstance(response, dict):
            message_text = response.get('text', '')
            buttons = response.get('buttons', [])
            
            if buttons:
                # Ensure we don't exceed the maximum number of buttons
                buttons = buttons[:3]
                await client.send_message(to=to, text=message_text, buttons=[
                    Button(title=b['title'], callback_data=ButtonAction(action=b['callback_data'], value="")) for b in buttons
                ])
            else:
                await client.send_message(to=to, text=message_text)
        else:
            await client.send_message(to=to, text=str(response))
    except Exception as e:
        wa_logger.error(f"Error in send_response: {str(e)}", exc_info=True)
        # Send a simple text message if there's an error with buttons
        await client.send_message(to=to, text="Üzgünüm, bir hata oluştu. Lütfen tekrar deneyin.")


async def send_menu_buttons(client: WhatsApp, to: str):
    buttons = [
        Button(title="Ürünleri Göster", callback_data=ButtonAction(action="option", value="1", image="1.jpeg")),
        Button(title="Musteri temsilcisi", callback_data=ButtonAction(action="option", value="2")),
        Button(title="Kargo Sorgula", callback_data=ButtonAction(action="help", value="general"))
    ]
    await client.send_message(to=to, text="Lütfen bir seçenek belirleyin:", buttons=buttons)


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