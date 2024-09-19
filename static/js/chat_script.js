const BUSINESS_PHONE_NUMBER_ID = "{{ business_phone_number_id }}";
let currentContact = null;
let socket = new WebSocket("wss://" + window.location.host + "/ws");
let conversations = {};

// Debounce function to prevent multiple calls
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

function loadConversations() {
    const savedConversations = localStorage.getItem('conversations');
    if (savedConversations) {
        conversations = JSON.parse(savedConversations);
        console.log("Loaded conversations:", conversations);
        updateContactList();
    }
}

function saveConversations() {
    localStorage.setItem('conversations', JSON.stringify(conversations));
    console.log("Saved conversations:", conversations);
}

socket.onopen = function(e) {
    console.log("WebSocket connection established");
    loadConversations();
};

socket.onmessage = function(event) {
    console.log("WebSocket message received:", event.data);
    const data = JSON.parse(event.data);
    if (data.type === "new_message") {
        const message = data.message;
        if (!conversations[message.from]) {
            conversations[message.from] = [];
        }
        conversations[message.from].push(message);
        updateContactList();
        if (message.from === currentContact || message.to === currentContact) {
            addMessageToChat(message);
        }
        saveConversations();

        // Check if the message text is "test"
        if (message.text.toLowerCase() === "test") {
            sendAutomatedResponse(message.from);
        }
    } else if (data.type === "status_update") {
        updateMessageStatus(data.status);
    }
};

function updateContactList() {
    console.log("Updating contact list");
    const contactList = $('.chats');
    
    Object.keys(conversations).forEach(contact => {
        const lastMessage = conversations[contact][conversations[contact].length - 1];
        let contactElement = contactList.find(`[data-contact="${contact}"]`);
        
        if (contactElement.length === 0) {
            contactElement = $(`
                <div class="block chat-list" data-contact="${contact}" onclick="selectContact('${contact}')">
                    <div class="imgBox">
                        <img src="{{ url_for('static', path='/images/Avatar-1.png') }}" class="cover">
                    </div>
                    <div class="h-text">
                        <div class="head">
                            <h4 title="${contact}" aria-label="${contact}">${contact}</h4>
                            <p class="time"></p>
                        </div>
                        <div class="message-chat">
                            <div class="chat-text-icon">
                                <span class="thanks"></span>
                            </div>
                        </div>
                    </div>
                </div>
            `);
            contactList.prepend(contactElement);
        }
        
        contactElement.find('.head h4').text(contact);
        contactElement.find('.time').text(new Date(lastMessage.timestamp).toLocaleTimeString());
        contactElement.find('.thanks').text(lastMessage.text);
    });
}

function selectContact(contact) {
    console.log("Selecting contact:", contact);
    
    // Remove active class from all contacts
    $('.chat-list').removeClass('active');
    
    // Add active class to selected contact
    $(`.chat-list[data-contact="${contact}"]`).addClass('active');
    
    currentContact = contact;
    updateChatWindow();
    openRightSide(); // Ensure the right side panel is opened
}

function updateChatWindow() {
    const chatWindow = $('.chat-window');
    chatWindow.empty();
    
    if (currentContact && conversations[currentContact]) {
        conversations[currentContact].forEach(message => {
            addMessageToChat(message);
        });
    }
}

function addMessageToChat(message) {
    const chatWindow = $('.chat-window');
    const messageElement = $(`
        <div class="message">
            <div class="message-content">
                <p>${message.text}</p>
            </div>
        </div>
    `);
    chatWindow.append(messageElement);
    chatWindow.scrollTop(chatWindow.prop("scrollHeight"));
}

function sendMessage() {
    const messageInput = document.querySelector('.send-message');
    const message = messageInput.value.trim();
    
    if (message === '') {
        console.log("Message is empty, not sending");
        return;
    }

    if (!currentContact) {
        console.log("No contact selected");
        alert('Please select a contact first');
        return;
    }

    console.log("Sending message:", message, "to:", currentContact);
    messageInput.value = ''; // Clear the input field immediately

    $.post('/send_message', { to: currentContact, message: message }, function(response) {
        if (response.success) {
            console.log("Message sent successfully:", response);
            const newMessage = {
                id: response.message_id,
                from: BUSINESS_PHONE_NUMBER_ID,
                to: currentContact,
                text: message,
                timestamp: new Date().toISOString(),
                status: 'sent'
            };
            if (!conversations[currentContact]) {
                conversations[currentContact] = [];
            }
            conversations[currentContact].push(newMessage);
            addMessageToChat(newMessage);
            updateContactList();
            saveConversations();
        } else {
            console.error('Failed to send message:', response.error);
        }
    }).fail(function(jqXHR, textStatus, errorThrown) {
        console.error('Error sending message:', textStatus, errorThrown);
    });
}

$(document).ready(function() {
    console.log("Document ready, loading conversations");
    loadConversations();

    // Add event listener for image upload button
    $('#uploadImageButton').on('click', function() {
        $('#imageInput').click();
    });

    // Handle image input change
    $('#imageInput').on('change', function() {
        const file = this.files[0];
        if (file) {
            uploadImage(file);
        }
    });
});

window.addEventListener('beforeunload', saveConversations);

function openRightSide() {
    document.getElementById('rightSide').style.display = 'block';
    document.getElementById('Intro-Left').style.display = 'none';
}

// Add this code to the existing JavaScript file

// Add event listener for Enter key
document.addEventListener('DOMContentLoaded', function() {
    const messageInput = document.querySelector('.send-message');
    if (messageInput) {
        messageInput.addEventListener('keypress', function(e) {
            if (e.which == 13) {
                console.log("Enter key pressed in message input");
                e.preventDefault();
                debounce(sendMessage, 300)();
            }
        });
    } else {
        console.error("Message input field not found");
    }
});

function sendAutomatedResponse(to) {
    const automatedMessage = "Yes, the test is received. How can I help?";
    console.log("Sending automated response:", automatedMessage, "to:", to);

    $.post('/send_message', { to: to, message: automatedMessage }, function(response) {
        if (response.success) {
            console.log("Automated response sent successfully:", response);
            const newMessage = {
                id: response.message_id,
                from: BUSINESS_PHONE_NUMBER_ID,
                to: to,
                text: automatedMessage,
                timestamp: new Date().toISOString(),
                status: 'sent'
            };
            if (!conversations[to]) {
                conversations[to] = [];
            }
            conversations[to].push(newMessage);
            if (to === currentContact) {
                addMessageToChat(newMessage);
            }
            updateContactList();
            saveConversations();
        } else {
            console.error('Failed to send automated response:', response.error);
        }
    }).fail(function(jqXHR, textStatus, errorThrown) {
        console.error('Error sending automated response:', textStatus, errorThrown);
    });
}

function uploadImage(file) {
    const formData = new FormData();
    formData.append('to', currentContact);
    formData.append('image', file);

    $.ajax({
        url: '/send_image',
        type: 'POST',
        data: formData,
        processData: false,
        contentType: false,
        success: function(response) {
            if (response.success) {
                console.log("Image sent successfully:", response);
                const newMessage = {
                    id: response.message_id,
                    from: BUSINESS_PHONE_NUMBER_ID,
                    to: currentContact,
                    text: 'Image',
                    timestamp: new Date().toISOString(),
                    status: 'sent',
                    image_url: response.image_url
                };
                if (!conversations[currentContact]) {
                    conversations[currentContact] = [];
                }
                conversations[currentContact].push(newMessage);
                addMessageToChat(newMessage);
                updateContactList();
                saveConversations();
            } else {
                console.error('Failed to send image:', response.error);
            }
        },
        error: function(jqXHR, textStatus, errorThrown) {
            console.error('Error sending image:', textStatus, errorThrown);
        }
    });
}
