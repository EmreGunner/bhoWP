import logging
from airtable_cargo import upload_image_to_airtable

# Setup logger
media_logger = logging.getLogger('media_actions')
media_logger.setLevel(logging.INFO)
handler = logging.FileHandler('logs/media_actions.log')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
media_logger.addHandler(handler)

def handle_image_upload(client, user_id, image_id, conversations):
    media_logger.info(f"Handling image upload for user {user_id}")
    if user_id in conversations and conversations[user_id].get("waiting_for") == "cargo_image":
        media_logger.info(f"User {user_id} is uploading a cargo image")
        try:
            image_data = client.download_media(image_id)
            if image_data:
                media_logger.info(f"Successfully downloaded image for user {user_id}")
                tracking_number = conversations[user_id].get("tracking_number")
                if tracking_number:
                    media_logger.info(f"Uploading image to Airtable for tracking number: {tracking_number}")
                    result = upload_image_to_airtable(tracking_number, image_data)
                    return result
                else:
                    media_logger.warning(f"No tracking number found for user {user_id}")
                    return "Lütfen önce kargo takip numarasını girin."
            else:
                media_logger.error(f"Failed to download image for user {user_id}")
                return "Resim indirilemedi. Lütfen tekrar deneyin."
        except Exception as e:
            media_logger.error(f"Error handling image upload: {str(e)}", exc_info=True)
            return "Resim yüklenirken bir hata oluştu. Lütfen tekrar deneyin."
    else:
        media_logger.info(f"Received unexpected image from user {user_id}")
        return "Resim alındı, ancak şu anda kargo resmi beklenmiyordu. Lütfen önce 'Resim Yükle' seçeneğini kullanın."
