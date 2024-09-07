import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from pywa import WhatsApp, filters
from pywa.types import Message, CallbackButton, CallbackSelection, FlowCompletion, MessageStatus, TemplateStatus, ChatOpened, Button
from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse

# Initialize FastAPI application
fastapi_app = FastAPI()

# Update the WhatsApp client initialization
wa = WhatsApp(
    phone_id="347058841835061",  # Update this to match the incoming messages
    token="EAAOxaNntzsEBOwJwyemOEYo6jHvXatZBpwFTwpOuY8EyEQNNrelEdCAdx7kMo1R7Wx7rHCQNQlV7Nbq8dVsALD8o7PjnZBCLMzDXc2Jpa6FZCTp1LpeZAkNqoLZB6J4fD0jeUJgb2josZCdGKgxsGwareDSqojJxazhkXTSh4NGFJmhErZAk1hoCjswFJoq9CiEK0PH8Nce6tAciIiZCwuUZD",
    server=fastapi_app,
    callback_url="https://49ae544d-ebdc-4b20-9445-aa092113c69a-00-1cr1zoiat6wtd.sisko.replit.dev",
    verify_token="randomstring",
    app_id=1039488821087937,
    app_secret="eda6cba58fa6404a8198b205face33aa",
    validate_updates=True,
    continue_handling=True
)

# Webhook verification endpoint
@fastapi_app.get("/webhook/verify")
async def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
    hub_challenge: str = Query(..., alias="hub.challenge")
):
    try:
        challenge, status_code = await wa.webhook_challenge_handler(
            vt=hub_verify_token,
            ch=hub_challenge
        )
        return PlainTextResponse(content=challenge, status_code=status_code)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)

# Endpoint to receive messages from WhatsApp
@fastapi_app.post("/webhook/messages")
async def receive_webhook(request: Request):
    try:
        body = await request.body()
        data = await request.json()
        logger.info(f"Received webhook data: {data}")
        response, status_code = await wa.webhook_update_handler(
            update=data,
            raw_body=body,
            hmac_header=request.headers.get("X-Hub-Signature-256")
        )
        logger.info(f"Webhook handler response: {response}, status: {status_code}")
        return PlainTextResponse(content=response, status_code=status_code)
    except Exception as e:
        logger.error(f"Error in receive_webhook: {e}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)

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
        # Use 'id' instead of 'message_id', and handle the case where it might not exist
        message_id = getattr(status, 'id', None) or getattr(status, 'message_id', 'Unknown')
        logger.info(f"Message status update: {status.status} for message {message_id}")
        logger.info(f"Full status object: {status}")
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

@wa.on_raw_update()
def handle_raw_update(client: WhatsApp, update: dict):
    logger.info(f"Received raw update: {update}")
    try:
        # Check if it's a text message
        if 'messages' in update['entry'][0]['changes'][0]['value']:
            message = update['entry'][0]['changes'][0]['value']['messages'][0]
            if message['type'] == 'text':
                text = message['text']['body']
                from_id = message['from']
                logger.info(f"Extracted text message: '{text}' from {from_id}")
                
                # Check if it's a question and send welcome message, otherwise echo
                if '?' in text:
                    send_welcome_message(client, from_id, text)
                else:
                    echo_message(client, from_id, text)
        # Handle status updates
        elif 'statuses' in update['entry'][0]['changes'][0]['value']:
            status = update['entry'][0]['changes'][0]['value']['statuses'][0]
            handle_message_status(client, MessageStatus(**status))
    except Exception as e:
        logger.error(f"Error in handle_raw_update: {e}", exc_info=True)

def echo_message(client: WhatsApp, from_id: str, text: str):
    logger.info(f"Echoing message: {text} to {from_id}")
    try:
        response = client.send_message(
            to=from_id,
            text=f"Echo: {text}"
        )
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
            buttons=[Button(title="Click me!", callback_data="id:123")]
        )
        logger.info(f"Sent response: {response}")
    except Exception as e:
        logger.error(f"Error in hello handler: {e}", exc_info=True)

# Root path handler
@fastapi_app.get("/")
async def root():
    return {"message": "Welcome to the WhatsApp webhook server"}

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
        content={"message": "An unexpected error occurred.", "error": str(exc)},
    )

# If you want to use Handler objects instead of decorators, you can do:
# from pywa.handlers import MessageHandler, CallbackButtonHandler
# wa.add_handlers(
#     MessageHandler(hello, filters.matches("Hello", "Hi")),
#     CallbackButtonHandler(click_me, filters.startswith("id"))
# )

def send_welcome_message(client: WhatsApp, from_id: str, text: str):
    logger.info(f"Sending welcome message for question: {text} to {from_id}")
    try:
        response = client.send_message(
            to=from_id,
            text=f"Welcome! Thank you for your question: '{text}'. How can I assist you today?"
        )
        logger.info(f"Sent welcome response: {response}")
    except Exception as e:
        logger.error(f"Error in send_welcome_message: {e}", exc_info=True)