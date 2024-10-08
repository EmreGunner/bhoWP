import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("AIRTABLE_API_KEY")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")

BASE_URL = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def create_airtable_record(product_id: str, name: str, address: str, phone: str) -> str:
    data = {
        "records": [
            {
                "fields": {
                    "Ürün Numarası": product_id,
                    "İsim Soyisim": name,
                    "Adres": address,
                    "Telefon Numarası": phone
                }
            }
        ]
    }
    
    response = requests.post(BASE_URL, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()['records'][0]['id']
    else:
        raise Exception(f"Failed to create Airtable record: {response.text}")