#Ai Related Funtions.

from openai import OpenAI
from dotenv import load_dotenv
import os
import json
import time

# Load environment variables
load_dotenv()

# Set up OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_KEY"))

# Assistant ID
ASSISTANT_ID = "asst_c0fmvtw3HZfUYXooiPim6WBF"

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

        # Wait for the run to complete
        while run.status in ["queued", "in_progress"]:
            run = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            time.sleep(0.5)

        # Retrieve the messages
        messages = client.beta.threads.messages.list(thread_id=thread.id)

        # Get the last assistant message
        for message in messages.data:
            if message.role == "assistant":
                return message.content[0].text.value

        return "No response from the assistant."

    except Exception as e:
        print(f"Error in get_ai_response: {e}")
        return "Sorry, I couldn't process your question. Please try again later."