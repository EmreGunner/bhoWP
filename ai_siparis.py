from enum import Enum
from typing import Dict, Optional
from airtable_siparisler import create_airtable_record
from pyairtable import Api
import logging

logger = logging.getLogger(__name__)

class OrderState(Enum):
    IDLE = 0
    COLLECTING_NAME = 1
    COLLECTING_ADDRESS = 2
    COLLECTING_PHONE = 3
    CONFIRMING = 4
    COMPLETED = 5

class OrderManager:
    def __init__(self):
        self.orders: Dict[str, Dict] = {}

    def get_or_create_order(self, user_id: str) -> Dict:
        if user_id not in self.orders:
            self.orders[user_id] = {
                "state": OrderState.IDLE,
                "name": "",
                "address": "",
                "phone": "",
                "product_id": ""
            }
        return self.orders[user_id]

    def process_message(self, user_id: str, message: str, product_id: Optional[str] = None) -> str:
        order = self.get_or_create_order(user_id)
        logger.info(f"Processing message for user {user_id}, current state: {order['state']}, message: {message}, product_id: {product_id}")

        if product_id:
            order["product_id"] = product_id
            order["state"] = OrderState.COLLECTING_NAME
            return "Siparişiniz için teşekkür ederiz. Lütfen adınızı ve soyadınızı girin."

        if order["state"] == OrderState.COLLECTING_NAME:
            order["name"] = message
            order["state"] = OrderState.COLLECTING_ADDRESS
            return "Teşekkürler. Şimdi lütfen adresinizi girin."

        elif order["state"] == OrderState.COLLECTING_ADDRESS:
            order["address"] = message
            order["state"] = OrderState.COLLECTING_PHONE
            return "Adresinizi aldık. Son olarak, telefon numaranızı girer misiniz?"

        elif order["state"] == OrderState.COLLECTING_PHONE:
            order["phone"] = message
            order["state"] = OrderState.CONFIRMING
            return f"Bilgilerinizi özetliyorum:\nİsim: {order['name']}\nAdres: {order['address']}\nTelefon: {order['phone']}\nBu bilgiler doğru mu? (Evet/Hayır)"

        elif order["state"] == OrderState.CONFIRMING:
            if message.lower() == "evet":
                try:
                    order_number = create_airtable_record(order["product_id"], order["name"], order["address"], order["phone"])
                    order["state"] = OrderState.COMPLETED
                    return f"Siparişiniz alındı. Sipariş numaranız: {order_number}. Teşekkür ederiz!"
                except Exception as e:
                    logger.error(f"Error creating Airtable record: {e}")
                    return "Üzgünüz, siparişinizi kaydederken bir hata oluştu. Lütfen daha sonra tekrar deneyin."
            elif message.lower() == "hayır":
                order["state"] = OrderState.COLLECTING_NAME
                return "Özür dileriz. Bilgilerinizi tekrar alalım. Lütfen adınızı ve soyadınızı girin."
            else:
                return "Lütfen 'Evet' veya 'Hayır' şeklinde yanıt verin."

        logger.error(f"Unexpected state: {order['state']} for user {user_id}")
        return "Bir hata oluştu. Lütfen tekrar deneyin."

order_manager = OrderManager()

def handle_order(user_id: str, message: str, product_id: Optional[str] = None) -> str:
    logger.info(f"Handling order for user {user_id}, message: {message}, product_id: {product_id}")
    try:
        response = order_manager.process_message(user_id, message, product_id)
        logger.info(f"Order response: {response}")
        return response
    except Exception as e:
        logger.error(f"Error in handle_order: {e}", exc_info=True)
        return "Bir hata oluştu. Lütfen tekrar deneyin."

def create_airtable_record(product_id, name, address, phone):
    api_key = 'patBOjCbAkFYSl5yd.65d9881a0065d782703e54603326458182719122bc222858afebf95c6873d2'
    base_id = 'appcfWwht8JToMUhi'
    table_name = 'Orders'  # Replace with your actual table name

    api = Api(api_key)
    table = api.table(base_id, table_name)

    record = {
        'Product ID': product_id,
        'Name': name,
        'Address': address,
        'Phone': phone
    }

    response = table.create(record)
    return response['id']  # Return the Airtable record ID as the order number