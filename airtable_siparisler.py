import requests
import os
from dotenv import load_dotenv
import logging

# Logging konfigürasyonu
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
    logger.debug(f"create_airtable_record called with: product_id={product_id}, name={name}, address={address}, phone={phone}")
    logger.debug(f"API_KEY: {API_KEY}, BASE_ID: {BASE_ID}, TABLE_NAME: {TABLE_NAME}")
    
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
        logger.debug(f"Sending POST request to Airtable API: {BASE_URL}")
        logger.debug(f"Request headers: {headers}")
        logger.debug(f"Request data: {data}")
        
        response = requests.post(BASE_URL, headers=headers, json=data)
        logger.debug(f"Airtable API response status code: {response.status_code}")
        logger.debug(f"Airtable API response content: {response.text}")
        
        response.raise_for_status()  # This will raise an exception for HTTP errors
        
        if response.status_code == 200:
            record_id = response.json()['records'][0]['id']
            logger.info(f"Successfully created Airtable record with ID: {record_id}")
            return record_id
        else:
            logger.error(f"Unexpected status code from Airtable API: {response.status_code}")
            raise Exception(f"Unexpected status code: {response.status_code}")
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Request to Airtable API failed: {str(e)}", exc_info=True)
        raise
    except KeyError as e:
        logger.error(f"Unexpected response format from Airtable API: {str(e)}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unexpected error while creating Airtable record: {str(e)}", exc_info=True)
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
        logger.error(f"Airtable connection test failed: {str(e)}", exc_info=True)
        return False

# Uncomment the following lines to test the connection when the script is run
# if __name__ == "__main__":
#     test_airtable_connection()