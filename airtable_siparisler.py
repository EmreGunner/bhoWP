import requests
import os
from dotenv import load_dotenv
import logging
import json

# Logging configuration
logging.basicConfig(
    filename='logs/airtable_siparisler.log',  # Log file for this module
    level=logging.INFO,  # Change this from DEBUG to INFO
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
    logger.debug(f"create_airtable_record called with: product_id={product_id}, name={name}, address={address}, phone={phone}, text={text}")
    
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
        logger.debug(f"Sending POST request to Airtable API: {BASE_URL}")
        logger.debug(f"Request headers: {headers}")
        logger.debug(f"Request data: {json.dumps(data)}")
        
        response = requests.post(BASE_URL, headers=headers, json=data)
        logger.debug(f"Airtable API response status code: {response.status_code}")
        logger.debug(f"Airtable API response content: {response.text}")
        
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
                logger.info(f"Successfully created and updated Airtable record with ID: {record_id}")
                return record_id
            else:
                logger.warning(f"Failed to update SiparisNo. Status code: {update_response.status_code}")
                return record_id  # Return the original record ID even if update fails
        else:
            logger.error(f"Failed to create Airtable record. Status code: {response.status_code}")
            logger.error(f"Response content: {response.text}")
            return "ERROR"  # Return a default error value
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Request to Airtable API failed: {str(e)}", exc_info=True)
        return "ERROR"  # Return a default error value
    except Exception as e:
        logger.error(f"Unexpected error while creating Airtable record: {str(e)}", exc_info=True)
        return "ERROR"  # Return a default error value

# Test function to verify the Airtable connection
def test_airtable_connection():
    logger.info("Testing Airtable connection...")
    try:
        response = requests.get(BASE_URL, headers=headers)
        response.raise_for_status()
        logger.info("Airtable connection test successful!")
        return True
    except Exception as e:
        logger.error(f"Airtable connection test failed: {str(e)}", exc_info=True)
        return False

# Uncomment the following lines to test the connection when the script is run
# if __name__ == "__main__":
#     test_airtable_connection()