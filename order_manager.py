from enum import Enum
from typing import Dict, Optional
from airtable_siparisler import create_airtable_record
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
order_logger = setup_logger('order_manager', 'logs/order_manager.log')

class OrderState(Enum):
    IDLE = 0
    COLLECTING_NAME = 1
    COLLECTING_ADDRESS = 2
    COLLECTING_PHONE = 3
    COLLECTING_TEXT = 4
    CONFIRMING = 5
    COMPLETED = 6

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
                "product_id": "",
                "text": ""
            }
        return self.orders[user_id]

    def process_message(self, user_id: str, message: str, product_id: Optional[str] = None) -> str:
        order = self.get_or_create_order(user_id)
        order_logger.info(f"Processing message for user {user_id}, current state: {order['state']}, message: {message}, product_id: {product_id}")

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
            order["state"] = OrderState.COLLECTING_TEXT
            return f"Bilgilerinizi özetliyorum:\nİsim: {order['name']}\nAdres: {order['address']}\nTelefon: {order['phone']}\nÜrün Metni: {order['text'] or 'Yok'}\nBu bilgiler doğru mu? (Evet/Hayır)"

        elif order["state"] == OrderState.COLLECTING_TEXT:
            order["text"] = message if message.lower() != "yok" else ""
            order["state"] = OrderState.CONFIRMING
            return f"Bilgilerinizi özetliyorum:\nİsim: {order['name']}\nAdres: {order['address']}\nTelefon: {order['phone']}\nÜrün Metni: {order['text'] or 'Yok'}\nBu bilgiler doğru mu? (Evet/Hayır)"

        elif order["state"] == OrderState.CONFIRMING:
            if message.lower() == "evet":
                try:
                    order_number = create_airtable_record(
                        order["product_id"],
                        order["name"],
                        order["address"],
                        order["phone"],
                        order["text"]
                    )
                    order["state"] = OrderState.COMPLETED
                    return f"Siparişiniz alındı. Sipariş numaranız: {order_number}. Teşekkür ederiz!"
                except Exception as e:
                    order_logger.error(f"Error creating Airtable record: {e}", exc_info=True)
                    return "Üzgünüz, siparişinizi kaydederken bir hata oluştu. Lütfen daha sonra tekrar deneyin."
            elif message.lower() == "hayır":
                order["state"] = OrderState.COLLECTING_NAME
                return "Özür dileriz. Bilgilerinizi tekrar alalım. Lütfen adınızı ve soyadınızı girin."
            else:
                return "Lütfen 'Evet' veya 'Hayır' şeklinde yanıt verin."

        return "Bir hata oluştu. Lütfen tekrar deneyin."

order_manager = OrderManager()

def handle_order(user_id: str, message: str, product_id: Optional[str] = None) -> str:
    return order_manager.process_message(user_id, message, product_id)