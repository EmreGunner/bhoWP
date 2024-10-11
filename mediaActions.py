import logging
import os
from pywa import WhatsApp
from pywa.types import MediaUrlResponse, Image

# Setup logger
media_logger = logging.getLogger('media_actions')
media_logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('logs/media_actions.log')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
media_logger.addHandler(handler)

async def handle_image_upload(client: WhatsApp, user_id: str, image_id: str, conversations: dict):
    media_logger.info(f"Starting image upload process for user {user_id} with image ID {image_id}")
    try:
        # Step 1: Get media URL
        media_logger.debug(f"Getting media URL for image ID: {image_id}")
        media_url_response = client.get_media_url(image_id)
        media_logger.info(f"Media URL Response: {media_url_response}")

        if not isinstance(media_url_response, MediaUrlResponse):
            media_logger.error(f"Unexpected media_url_response format: {type(media_url_response)}")
            return "Failed to retrieve image information. Please try again."

        # Step 2: Download the image
        media_logger.debug(f"Downloading image from URL: {media_url_response.url}")
        image = await client.download_media(media_url_response)

        if not isinstance(image, Image):
            media_logger.error(f"Unexpected image format: {type(image)}")
            return "Failed to process the image. Please try again."

        # Step 3: Save the image
        os.makedirs("uploads", exist_ok=True)
        file_path = os.path.join("uploads", f"{image_id}{image.extension}")
        media_logger.debug(f"Saving image to: {file_path}")
        
        # Use the download method
        image.download(path="uploads", filename=f"{image_id}{image.extension}")

        media_logger.info(f"Successfully downloaded and saved image for user {user_id}: {file_path}")
        return f"Image successfully uploaded and saved: {file_path}"

    except Exception as e:
        media_logger.exception(f"Error handling image upload: {str(e)}")
        return f"An error occurred while processing the image: {str(e)}. Please try again."
