import requests
import os
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
import base64

# Load environment variables
load_dotenv()
API_KEY = os.getenv("AIRTABLE_API_KEY")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
TABLE_NAME = "Kargo"

BASE_URL = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Logging configuration
def setup_logger(name, log_file, level=logging.INFO):
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger

# Setup logger
cargo_logger = setup_logger('airtable_cargo', 'logs/airtable_cargo.log')

def check_tracking_number(tracking_number):
    cargo_logger.info(f"Checking tracking number: {tracking_number}")
    
    # Construct the filter formula
    filter_formula = f"{{Takip Numarası}} = '{tracking_number}'"
    
    # Make the API request
    response = requests.get(
        BASE_URL,
        headers=headers,
        params={
            "filterByFormula": filter_formula
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        records = data.get('records', [])
        
        if records:
            # Tracking number found
            record = records[0]['fields']
            tracking_number = record.get('Takip Numarası', '')
            cargo_company = record.get('Kargo Firması', '')
            status = record.get('Kargo Durumu', '')
            
            cargo_logger.info(f"Tracking number found: {tracking_number}")
            return f"{tracking_number} numaralı kargonuz {cargo_company} firmasında, durumu {status} olarak görünmektedir."
        else:
            # Tracking number not found
            cargo_logger.warning(f"Tracking number not found: {tracking_number}")
            return "Bu takip numarasına ait kargo bulunamadı. Lütfen müşteri temsilcisi ile iletişime geçin."
    else:
        # API request failed
        cargo_logger.error(f"API request failed with status code: {response.status_code}")
        return "Kargo bilgilerini kontrol ederken bir hata oluştu. Lütfen daha sonra tekrar deneyin."

def upload_image_to_airtable(tracking_number, image_data):
    cargo_logger.info(f"Uploading image for tracking number: {tracking_number}")
    
    # Construct the filter formula
    filter_formula = f"{{Takip Numarası}} = '{tracking_number}'"
    
    # First, find the record with the given tracking number
    response = requests.get(
        BASE_URL,
        headers=headers,
        params={
            "filterByFormula": filter_formula
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        records = data.get('records', [])
        
        if records:
            record_id = records[0]['id']
            
            # Encode the image data
            encoded_image = base64.b64encode(image_data).decode('utf-8')
            
            # Now, update the record with the image
            update_data = {
                "fields": {
                    "Image": [{
                        "filename": f"{tracking_number}_image.jpg",
                        "content": encoded_image
                    }]
                }
            }
            
            update_response = requests.patch(
                f"{BASE_URL}/{record_id}",
                headers=headers,
                json=update_data
            )
            
            if update_response.status_code == 200:
                cargo_logger.info(f"Image uploaded successfully for tracking number: {tracking_number}")
                return f"Resim başarıyla yüklendi ve {tracking_number} numaralı kargo kaydına eklendi."
            else:
                cargo_logger.error(f"Failed to upload image for tracking number: {tracking_number}. Status code: {update_response.status_code}")
                return "Resim yüklenirken bir hata oluştu. Lütfen daha sonra tekrar deneyin."
        else:
            cargo_logger.warning(f"Tracking number not found: {tracking_number}")
            return "Bu takip numarasına ait kargo bulunamadı. Lütfen müşteri temsilcisi ile iletişime geçin."
    else:
        cargo_logger.error(f"API request failed with status code: {response.status_code}")
        return "Kargo bilgilerini kontrol ederken bir hata oluştu. Lütfen daha sonra tekrar deneyin."

# Example usage
if __name__ == "__main__":
    test_tracking_numbers = ["YK-987654321", "MG-123456789", "AK-112233445", "INVALID-NUMBER"]
    
    for number in test_tracking_numbers:
        result = check_tracking_number(number)
        print(f"Tracking Number: {number}")
        print(f"Result: {result}")
        print()