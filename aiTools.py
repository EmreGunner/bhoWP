#Ai Related Funtions.

from openai import OpenAI
from dotenv import load_dotenv
import os
import json
import time

# Load environment variables
load_dotenv()

# Set up OpenAI client
api_key = "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"
client = OpenAI(api_key=api_key)

# Assistant ID
ASSISTANT_ID = "asst_c0fmvtw3HZfUYXooiPim6WBF"

# Dictionary to store user threads
user_threads = {}

def get_or_create_thread(user_id: str):
    if user_id not in user_threads:
        user_threads[user_id] = client.beta.threads.create()
    return user_threads[user_id]

def get_ai_response(user_id: str, question: str) -> str:
    try:
        # Get or create a thread for the user
        thread = get_or_create_thread(user_id)

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
        max_retries = 5
        retry_count = 0
        while run.status in ["queued", "in_progress"] and retry_count < max_retries:
            run = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            time.sleep(1)
            retry_count += 1

        if run.status != "completed":
            raise Exception(f"Run did not complete. Status: {run.status}")

        # Retrieve the messages
        messages = client.beta.threads.messages.list(thread_id=thread.id)

        # Get the last assistant message
        for message in messages.data:
            if message.role == "assistant":
                return message.content[0].text.value

        return "Üzgünüm, şu anda bir cevap üretemiyorum. Lütfen daha sonra tekrar deneyin."

    except Exception as e:
        print(f"Error in get_ai_response: {e}")
        return "Üzgünüm, sorunuzu şu anda işleyemiyorum. Lütfen daha sonra tekrar deneyin veya müşteri hizmetleriyle iletişime geçin."

print(f"API Key: {os.getenv('OPENAI_API_KEY')}")