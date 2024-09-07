const chatMessages = document.getElementById('chat-messages');
const messageForm = document.getElementById('message-form');
const messageInput = document.getElementById('message-input');

// Function to add a message to the chat
function addMessage(message, isReceived = false) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message');
    messageElement.classList.add(isReceived ? 'received' : 'sent');
    messageElement.textContent = message;
    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Function to send a message
async function sendMessage(message) {
    try {
        const response = await fetch('/send_message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: message }),
        });
        const data = await response.json();
        if (data.success) {
            addMessage(message);
        } else {
            console.error('Failed to send message:', data.error);
        }
    } catch (error) {
        console.error('Error sending message:', error);
    }
}

// Event listener for form submission
messageForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const message = messageInput.value.trim();
    if (message) {
        sendMessage(message);
        messageInput.value = '';
    }
});

// Function to fetch new messages
async function fetchNewMessages() {
    try {
        const response = await fetch('/get_messages');
        const data = await response.json();
        data.messages.forEach(message => {
            addMessage(message.text, true);
        });
    } catch (error) {
        console.error('Error fetching messages:', error);
    }
}

// Fetch new messages every 5 seconds
setInterval(fetchNewMessages, 5000);

// Initial fetch of messages
fetchNewMessages();