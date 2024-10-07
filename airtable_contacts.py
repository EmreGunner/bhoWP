import requests
import json
import os
from dotenv import load_dotenv

# Load the environment variables
load_dotenv()
API_KEY = os.getenv("AIRTABLE_API_KEY")
BASE_ID = os.getenv("AIRTABLE_BASE_ID")
TABLE_NAME = "contacts"

BASE_URL = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def print_response(response):
    print(f"Status Code: {response.status_code}")
    print(json.dumps(response.json(), indent=2))

def create_contact(phone_number, name, last_interaction):
    data = {
        "records": [
            {
                "fields": {
                    "phone_number": phone_number,
                    "Name": name,
                    "last_interaction": last_interaction
                }
            }
        ]
    }
    
    response = requests.post(BASE_URL, headers=headers, json=data)
    return response


def get_contacts(formula=None):
    params = {}
    if formula:
        params["filterByFormula"] = formula
    
    response = requests.get(BASE_URL, headers=headers, params=params)
    return response
# Test create_contact function
#print("Testing create_contact function:")
#response = create_contact("+905330475085", "Emre", "2023-05-15T14:30:00Z")
#print_response(response)
#print("\n")

# Test get_contacts function
#print("Testing get_contacts function:")
#response = get_contacts()
#print_response(response)
#print("\n")

# Test get_contacts with a filter
#print("Testing get_contacts function with filter:")
#response = get_contacts("phone_number = '+905330475085'")
#print_response(response)
#print("\n")

def update_contact(record_id, fields):
    data = {
        "records": [
            {
                "id": record_id,
                "fields": fields
            }
        ]
    }
    
    response = requests.patch(BASE_URL, headers=headers, json=data)
    return response

# Test update_contact function
#print("Testing update_contact function:")
#record_id = "rechgiQqzFEy00dEa"  # Replace with an actual record ID
#updated_fields = {
#    "last_interaction": "2023-05-16T10:00:00Z",
#    "last_text" : "test"
#}
#response = update_contact(record_id, updated_fields)
#print_response(response)
#print("\n")
def delete_contact(record_id):
    delete_url = f"{BASE_URL}/{record_id}"
    response = requests.delete(delete_url, headers=headers)
    return response
    