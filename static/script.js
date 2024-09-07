document.addEventListener('DOMContentLoaded', function() {
    const messagesList = document.getElementById('messages-list');

    function addMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message');
        messageElement.innerHTML = `
            <p><strong>ID:</strong> ${message.id}</p>
            <p><strong>Text:</strong> ${message.text}</p>
            <p><strong>Timestamp:</strong> ${message.timestamp}</p>
        `;
        messagesList.appendChild(messageElement);
    }

    async function fetchAllMessages() {
        try {
            const response = await fetch('/get_all_messages');
            const data = await response.json();
            messagesList.innerHTML = ''; // Clear existing messages
            data.messages.forEach(addMessage);
        } catch (error) {
            console.error('Error fetching messages:', error);
        }
    }

    // Fetch messages initially
    fetchAllMessages();

    // Fetch new messages every 5 seconds
    setInterval(fetchAllMessages, 5000);
});