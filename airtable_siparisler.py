import requests
import os
from dotenv import load_dotenv
import logging

# Logging konfigürasyonu
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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

def create_airtable_record(product_id: str, name: str, address: str, phone: str) -> str:
    logger.info(f"Attempting to create Airtable record for product_id: {product_id}, name: {name}")
    
    data = {
        "records": [
            {
                "fields": {
                    "urunNo": product_id,
                    "AdSoyad": name,
                    "Adres": address,
                    "telefonNo": phone
                }
            }
        ]
    }
    
    try:
        logger.info(f"Sending POST request to Airtable API: {BASE_URL}")
        response = requests.post(BASE_URL, headers=headers, json=data)
        response.raise_for_status()  # This will raise an exception for HTTP errors
        
        logger.info(f"Airtable API response status code: {response.status_code}")
        logger.info(f"Airtable API response content: {response.text}")
        
        if response.status_code == 200:
            record_id = response.json()['records'][0]['id']
            logger.info(f"Successfully created Airtable record with ID: {record_id}")
            return record_id
        else:
            logger.error(f"Unexpected status code from Airtable API: {response.status_code}")
            raise Exception(f"Unexpected status code: {response.status_code}")
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Request to Airtable API failed: {str(e)}")
        raise
    except KeyError as e:
        logger.error(f"Unexpected response format from Airtable API: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error while creating Airtable record: {str(e)}")
        raise

# Test function to verify the Airtable connection
def test_airtable_connection():
    logger.info("Testing Airtable connection...")
    try:
        response = requests.get(BASE_URL, headers=headers)
        response.raise_for_status()
        logger.info("Airtable connection test successful!")
        return True
    except Exception as e:
        logger.error(f"Airtable connection test failed: {str(e)}")
        return False

# Uncomment the following lines to test the connection when the script is run
# if __name__ == "__main__":
#     test_airtable_connection()