import logging
from logging.handlers import RotatingFileHandler
from enum import Enum
from typing import Dict, Optional
from airtable_siparisler import create_airtable_record
import re
import json

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
ai_siparis_logger = setup_logger('ai_siparis', 'logs/ai_siparis.log')

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
                "text": "",
                "order_number": ""
            }
        return self.orders[user_id]

    def validate_phone(self, phone: str) -> bool:
        cleaned_phone = re.sub(r'\D', '', phone)
        return 10 <= len(cleaned_phone) <= 15

    def validate_name(self, name: str) -> bool:
        return len(name.split()) >= 1 and all(part.isalpha() for part in name.split())

    def validate_address(self, address: str) -> bool:
        return len(address) >= 5

    def process_message(self, user_id: str, message: str, product_id: Optional[str] = None) -> str:
        order = self.get_or_create_order(user_id)
        ai_siparis_logger.info(f"Processing message for user {user_id}, current state: {order['state']}, message: {message}, product_id: {product_id}")

        if product_id:
            order["product_id"] = product_id
            order["state"] = OrderState.COLLECTING_NAME
            return f"Ürün {product_id} için siparişinizi almaya başlıyoruz. Lütfen adınızı ve soyadınızı girin."

        if order["state"] == OrderState.COLLECTING_NAME:
            if self.validate_name(message):
                order["name"] = message
                order["state"] = OrderState.COLLECTING_ADDRESS
                return "Teşekkürler. Şimdi lütfen adresinizi girin."
            else:
                return "Geçersiz isim. Lütfen adınızı ve soyadınızı tekrar girin."

        elif order["state"] == OrderState.COLLECTING_ADDRESS:
            if self.validate_address(message):
                order["address"] = message
                order["state"] = OrderState.COLLECTING_PHONE
                return "Adresinizi aldık. Son olarak, telefon numaranızı girer misiniz? (Örnek: 05551234567)"
            else:
                return "Geçersiz adres. Lütfen en az 5 karakterden oluşan bir adres girin."

        elif order["state"] == OrderState.COLLECTING_PHONE:
            if self.validate_phone(message):
                order["phone"] = message
                order["state"] = OrderState.COLLECTING_TEXT
                return "Teşekkürler. Ürün üzerine yazdırmak istediğiniz metni girin. Eğer istemiyorsanız 'Yok' yazabilirsiniz."
            else:
                return "Geçersiz telefon numarası. Lütfen 5551234567 formatında bir numara girin."

        elif order["state"] == OrderState.COLLECTING_TEXT:
            order["text"] = message if message.lower() != "yok" else ""
            order["state"] = OrderState.CONFIRMING
            return f"Bilgilerinizi özetliyorum:\nİsim: {order['name']}\nAdres: {order['address']}\nTelefon: {order['phone']}\nÜrün Metni: {order['text'] or 'Yok'}\nBu bilgiler doğru mu? (Evet/Hayır)"

        elif order["state"] == OrderState.CONFIRMING:
            if message.lower() in ["evet", "hayır", "hayir"]:
                if "evet" in message.lower():
                    try:
                        order_number = create_airtable_record(
                            order["product_id"],
                            order["name"],
                            order["address"],
                            order["phone"],
                            order["text"]
                        )
                        if order_number and order_number != "ERROR":
                            order["order_number"] = order_number
                            order["state"] = OrderState.COMPLETED
                            return f"Siparişiniz alındı. Sipariş numaranız: {order_number}. Teşekkür ederiz!"
                        else:
                            ai_siparis_logger.warning(f"Failed to create Airtable record for user {user_id}")
                            return "Üzgünüz, siparişinizi kaydederken bir hata oluştu. Lütfen daha sonra tekrar deneyin."
                    except Exception as e:
                        ai_siparis_logger.error(f"Error creating Airtable record: {e}", exc_info=True)
                        return "Üzgünüz, siparişinizi kaydederken bir hata oluştu. Lütfen daha sonra tekrar deneyin."
                else:
                    order["state"] = OrderState.COLLECTING_NAME
                    return "Özür dileriz. Bilgilerinizi tekrar alalım. Lütfen adınızı ve soyadınızı girin."
            else:
                return "Lütfen 'Evet' veya 'Hayır' şeklinde yanıt verin."

        ai_siparis_logger.error(f"Unexpected state: {order['state']} for user {user_id}")
        return "Bir hata oluştu. Lütfen tekrar deneyin."

order_manager = OrderManager()

def handle_order(user_id: str, message: str, product_id: Optional[str] = None) -> str:
    ai_siparis_logger.info(f"Handling order for user {user_id}, message: {message}, product_id: {product_id}")
    try:
        response = order_manager.process_message(user_id, message, product_id)
        ai_siparis_logger.info(f"Order response: {response}")
        return response
    except Exception as e:
        ai_siparis_logger.error(f"Error in handle_order: {e}", exc_info=True)
        return "Bir hata oluştu. Lütfen tekrar deneyin."

def create_airtable_record(product_id, name, address, phone, text):
    try:
        from airtable_siparisler import create_airtable_record as airtable_create_record
        ai_siparis_logger.info(f"Calling Airtable create record function with: product_id={product_id}, name={name}, address={address}, phone={phone}, text={text}")
        record_id = airtable_create_record(product_id, name, address, phone, text)
        ai_siparis_logger.info(f"Airtable record created successfully with ID: {record_id}")
        return record_id
    except Exception as e:
        ai_siparis_logger.error(f"Error in create_airtable_record: {str(e)}", exc_info=True)
        return None