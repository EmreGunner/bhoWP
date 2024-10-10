import logging

# Setup logger
checker_logger = logging.getLogger('checker')
checker_logger.setLevel(logging.INFO)
handler = logging.FileHandler('logs/checker.log')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
checker_logger.addHandler(handler)

def check_received_media(message):
    user_id = message.get('from')
    message_type = message.get('type')
    checker_logger.info(f"Received {message_type} message from user {user_id}")

    if message_type == 'image':
        image = message.get('image', {})
        image_id = image.get('id')
        mime_type = image.get('mime_type')
        checker_logger.info(f"Image received - ID: {image_id}, MIME type: {mime_type}")
        return {'type': 'image', 'id': image_id, 'mime_type': mime_type}
    elif message_type == 'video':
        video = message.get('video', {})
        video_id = video.get('id')
        mime_type = video.get('mime_type')
        checker_logger.info(f"Video received - ID: {video_id}, MIME type: {mime_type}")
        return {'type': 'video', 'id': video_id, 'mime_type': mime_type}
    elif message_type == 'text':
        text = message.get('text', {}).get('body', '')
        checker_logger.info(f"Text message received: '{text}'")
        return {'type': 'text', 'content': text}
    elif message_type == 'interactive':
        interactive = message.get('interactive', {})
        checker_logger.info(f"Interactive message received: {interactive}")
        return {'type': 'interactive', 'content': interactive}
    else:
        checker_logger.info(f"Unsupported message type received: {message_type}")
        return {'type': 'unsupported', 'message_type': message_type}
