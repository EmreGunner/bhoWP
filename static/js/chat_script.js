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
    
    // Update header
    $('.rightSide .header .imgText h4').text(contact);
    $('.rightSide .header .imgText span').text('online'); // You might want to make this dynamic
    $('.rightSide .header .imgText img').attr('src', `{{ url_for('static', path='/images/Avatar-1.png') }}`);
    
    // Show right side and hide intro
    $('#rightSide').show();
    $('#Intro-Left').hide();
    
    // Reset message input
    $('#message-input').val('').attr('placeholder', `Type a message to ${contact}`);
    
    // Update chat
    updateChat();
}

function updateChat() {
    console.log("Updating chat for contact:", currentContact);
    const chatBox = $('.chatBox');
    if (chatBox.length === 0) {
        console.error("Chat box not found");
        return;
    }
    chatBox.empty();
    if (conversations[currentContact]) {
        conversations[currentContact].forEach(addMessageToChat);
    }
    chatBox.scrollTop(chatBox[0].scrollHeight);

    // Fetch new messages from the server
    $.get(`/get_messages/${currentContact}`, function(data) {
        data.messages.forEach(function(msg) {
            if (!conversations[currentContact]) {
                conversations[currentContact] = [];
            }
            if (!conversations[currentContact].some(m => m.id === msg.id)) {
                conversations[currentContact].push(msg);
                addMessageToChat(msg);
            }
        });
        saveConversations();
    });
}

function addMessageToChat(message) {
    console.log("Adding message to chat:", message);
    const isReceived = message.from !== BUSINESS_PHONE_NUMBER_ID;
    let messageContent;

    if (message.image_url) {
        // If the message contains an image URL, create an image element
        messageContent = `<img src="${message.image_url}" alt="Image" class="chat-image">`;
    } else {
        // Otherwise, use the text content
        messageContent = `<span>${message.text}</span>`;
    }

    const messageElement = $(`
        <div class="chat__date-wrapper"><span class="chat__date">${new Date(message.timestamp).toLocaleDateString()}</span></div>
        <p class="chatMessage ${isReceived ? 'frnd-chat' : 'my-chat'}">
            ${messageContent}
            <span class="chat__msg-filler"> </span>
            <span class="msg-footer">
                <span>${new Date(message.timestamp).toLocaleTimeString()}</span>
                ${!isReceived ? `<div class="message-status status-${message.status || 'sent'}"></div>` : ''}
            </span>
        </p>
    `);
    $('.chatBox').append(messageElement);
    $('.chatBox').scrollTop($('.chatBox')[0].scrollHeight);
}

function updateMessageStatus(status) {
    console.log("Updating message status:", status);
    if (conversations[currentContact]) {
        const message = conversations[currentContact].find(m => m.id === status.id);
        if (message) {
            message.status = status.status;
            $(`.message[data-message-id="${status.id}"] .message-status`)
                .removeClass()
                .addClass(`message-status status-${status.status.toLowerCase()}`);
            saveConversations();
        }
    }
}

$('#send-button').click(debounce(sendMessage, 300));

$('#message-input').keypress(function(e) {
    if(e.which == 13) {
        console.log("Enter key pressed in message input");
        e.preventDefault();
        debounce(sendMessage, 300)();
    }
});

function sendMessage() {
    console.log("sendMessage function called");
    const messageInput = document.getElementById('message-input');
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

let isUploading = false;

document.addEventListener('DOMContentLoaded', function() {
    let imageUploadButton = document.querySelector('#image-upload');
    if (!imageUploadButton) {
        imageUploadButton = document.createElement('input');
        imageUploadButton.type = 'file';
        imageUploadButton.id = 'image-upload';
        imageUploadButton.style.display = 'none';
        imageUploadButton.accept = 'image/*,video/mp4,video/3gpp,video/quicktime';
        document.body.appendChild(imageUploadButton);
    }

    const photosVideosButton = document.querySelector('.popopIcons[title="Photos & Videos"]');
    if (photosVideosButton) {
        // Remove any existing click event listeners
        photosVideosButton.removeEventListener('click', photosVideosClickHandler);
        // Add a new click event listener
        photosVideosButton.addEventListener('click', photosVideosClickHandler);
    } else {
        console.error('Photos & Videos button not found');
    }

    // Remove any existing change event listeners
    imageUploadButton.removeEventListener('change', imageUploadHandler);
    // Add a new change event listener
    imageUploadButton.addEventListener('change', imageUploadHandler);

    // Remove the onclick attribute from the SVG element
    const svgElement = document.querySelector('svg[viewBox="0 0 53 53"]');
    if (svgElement) {
        svgElement.removeAttribute('onclick');
    }
});

function photosVideosClickHandler(e) {
    e.preventDefault();
    if (!isUploading) {
        console.log('Image button clicked');
        document.querySelector('#image-upload').click();
    }
}

function imageUploadHandler() {
    if (this.files && this.files[0] && !isUploading) {
        isUploading = true;
        sendImage(this.files[0]).then(() => {
            isUploading = false;
            this.value = ''; // Clear the input
        }).catch(() => {
            isUploading = false;
            this.value = ''; // Clear the input even if there's an error
        });
    }
}

function sendImage(imageFile) {
    return new Promise((resolve, reject) => {
        const formData = new FormData();
        formData.append('to', currentContact);
        formData.append('image', imageFile);

        $.ajax({
            url: '/send_image',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                if (response.success) {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        const newMessage = {
                            id: response.message_id,
                            from: BUSINESS_PHONE_NUMBER_ID,
                            to: currentContact,
                            image_url: e.target.result,
                            timestamp: new Date().toISOString(),
                            status: 'sent'
                        };
                        addMessageToConversation(newMessage);
                        resolve();
                    }
                    reader.readAsDataURL(imageFile);
                } else {
                    console.error('Failed to send image:', response.error);
                    reject();
                }
            },
            error: function(jqXHR, textStatus, errorThrown) {
                console.error('Error sending image:', textStatus, errorThrown);
                reject();
            }
        });
    });
}

function addMessageToConversation(message) {
    if (!conversations[currentContact]) {
        conversations[currentContact] = [];
    }
    conversations[currentContact].push(message);
    addMessageToChat(message);
    $('#message-input').val('');
    $('#image-upload').val('');
    updateContactList(message);
    saveConversations();
}

$(document).ready(function() {
    console.log("Document ready, loading conversations");
    loadConversations();
});

window.addEventListener('beforeunload', saveConversations);

function openRightSide() {
    document.getElementById('rightSide').style.display = 'block';
    document.getElementById('Intro-Left').style.display = 'none';
}
