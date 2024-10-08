import requests
import os
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler

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
airtable_logger = setup_logger('airtable_siparisler', 'logs/airtable_siparisler.log')

load_dotenv()

API_KEY = os.getenv("AIRTABLE_API_KEY")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
TABLE_NAME = "Siparisler"

BASE_URL = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def create_airtable_record(product_id: str, name: str, address: str, phone: str, text: str) -> str:
    airtable_logger.debug(f"create_airtable_record called with: product_id={product_id}, name={name}, address={address}, phone={phone}, text={text}")
    
    data = {
        "fields": {
            "urunNo": product_id,
            "AdSoyad": name,
            "Adres": address,
            "telefonNo": phone,
            "UrunMetni": text,
            "SiparisNo": ""  # This will be updated after record creation
        }
    }
    
    try:
        airtable_logger.debug(f"Sending POST request to Airtable API: {BASE_URL}")
        airtable_logger.debug(f"Request headers: {headers}")
        airtable_logger.debug(f"Request data: {json.dumps(data)}")
        
        response = requests.post(BASE_URL, headers=headers, json=data)
        airtable_logger.debug(f"Airtable API response status code: {response.status_code}")
        airtable_logger.debug(f"Airtable API response content: {response.text}")
        
        if response.status_code == 200:
            record_id = response.json()['id']
            
            # Update the record with the SiparisNo
            update_data = {
                "fields": {
                    "SiparisNo": record_id
                }
            }
            update_response = requests.patch(f"{BASE_URL}/{record_id}", headers=headers, json=update_data)
            
            if update_response.status_code == 200:
                airtable_logger.info(f"Successfully created and updated Airtable record with ID: {record_id}")
                return record_id
            else:
                airtable_logger.warning(f"Failed to update SiparisNo. Status code: {update_response.status_code}")
                return record_id  # Return the original record ID even if update fails
        else:
            airtable_logger.error(f"Failed to create Airtable record. Status code: {response.status_code}")
            airtable_logger.error(f"Response content: {response.text}")
            return "ERROR"  # Return a default error value
    
    except requests.exceptions.RequestException as e:
        airtable_logger.error(f"Request to Airtable API failed: {str(e)}", exc_info=True)
        return "ERROR"  # Return a default error value
    except Exception as e:
        airtable_logger.error(f"Unexpected error while creating Airtable record: {str(e)}", exc_info=True)
        return "ERROR"  # Return a default error value

# Test function to verify the Airtable connection
def test_airtable_connection():
    airtable_logger.info("Testing Airtable connection...")
    try:
        response = requests.get(BASE_URL, headers=headers)
        response.raise_for_status()
        airtable_logger.info("Airtable connection test successful!")
        return True
    except Exception as e:
        airtable_logger.error(f"Airtable connection test failed: {str(e)}", exc_info=True)
        return False

# Uncomment the following lines to test the connection when the script is run
# if __name__ == "__main__":
#     test_airtable_connection()