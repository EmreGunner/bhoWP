#Ai Related Funtions.

from openai import OpenAI
from dotenv import load_dotenv
import os
from typing_extensions import override
from openai import AssistantEventHandler
from openai.types.beta.threads import Text, TextDelta

# Load environment variables
load_dotenv()

# Set up OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_KEY"))

# Assistant ID
ASSISTANT_ID = "asst_c0fmvtw3HZfUYXooiPim6WBF"

class EventHandler(AssistantEventHandler):
    def __init__(self):
        self.full_response = ""

    @override
    def on_text_created(self, text: Text) -> None:
        pass

    @override
    def on_text_delta(self, delta: TextDelta, snapshot: Text):
        self.full_response += delta.value

    @override
    def on_end(self):
        pass

def get_ai_response(question: str) -> str:
    try:
        # Create a thread
        thread = client.beta.threads.create()

        # Add a message to the thread
        client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=question
        )

        # Create a run
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID
        )

        # Initialize the event handler
        handler = EventHandler()

        # Stream the response
        with client.beta.threads.runs.stream(
            thread_id=thread.id,
            run_id=run.id,
            event_handler=handler,
        ) as stream:
            stream.until_done()

        # Return the full response
        return handler.full_response.strip()

    except Exception as e:
        print(f"Error in get_ai_response: {e}")
        return "Sorry, I couldn't process your question. Please try again later."