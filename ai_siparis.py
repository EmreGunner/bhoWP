import logging
from logging.handlers import RotatingFileHandler
from enum import Enum
from typing import Dict, Optional, List, Any
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

    def process_message(self, user_id: str, message: str, product_id: Optional[str] = None) -> Dict[str, Any]:
        order = self.get_or_create_order(user_id)
        ai_siparis_logger.info(f"Processing message for user {user_id}, current state: {order['state']}, message: {message}, product_id: {product_id}")

        response = {"text": "", "buttons": []}

        if product_id:
            order["product_id"] = product_id
            order["state"] = OrderState.COLLECTING_NAME
            response["text"] = f"Ürün {product_id} için siparişinizi almaya başlıyoruz. Lütfen adınızı ve soyadınızı girin."
            return response

        if order["state"] == OrderState.IDLE:
            if product_id:
                order["product_id"] = product_id
                order["state"] = OrderState.COLLECTING_NAME
                response["text"] = f"Ürün {product_id} için siparişinizi almaya başlıyoruz. Lütfen adınızı ve soyadınızı girin."
            else:
                response["text"] = "Lütfen önce bir ürün seçin."
            return response

        elif order["state"] == OrderState.COLLECTING_NAME:
            if self.validate_name(message):
                order["name"] = message
                order["state"] = OrderState.COLLECTING_ADDRESS
                response["text"] = "Teşekkürler. Şimdi lütfen adresinizi girin."
            else:
                response["text"] = "Geçersiz isim. Lütfen adınızı ve soyadınızı tekrar girin."

        elif order["state"] == OrderState.COLLECTING_ADDRESS:
            if self.validate_address(message):
                order["address"] = message
                order["state"] = OrderState.COLLECTING_PHONE
                response["text"] = "Adresinizi aldık. Son olarak, telefon numaranızı girer misiniz? (Örnek: 05551234567)"
            else:
                response["text"] = "Geçersiz adres. Lütfen en az 5 karakterden oluşan bir adres girin."

        elif order["state"] == OrderState.COLLECTING_PHONE:
            if self.validate_phone(message):
                order["phone"] = message
                order["state"] = OrderState.COLLECTING_TEXT
                response["text"] = "Teşekkürler. Ürün üzerine yazdırmak istediğiniz metni girin. Eğer istemiyorsanız 'Yok' yazabilirsiniz."
            else:
                response["text"] = "Geçersiz telefon numarası. Lütfen 5551234567 formatında bir numara girin."

        elif order["state"] == OrderState.COLLECTING_TEXT:
            order["text"] = message if message.lower() != "yok" else ""
            order["state"] = OrderState.CONFIRMING
            response["text"] = f"Bilgilerinizi özetliyorum:\nİsim: {order['name']}\nAdres: {order['address']}\nTelefon: {order['phone']}\nÜrün Metni: {order['text'] or 'Yok'}\nBu bilgiler doğru mu?"
            response["buttons"] = [
                {"title": "Evet", "callback_data": "confirm_order_yes"},
                {"title": "Hayır", "callback_data": "confirm_order_no"}
            ]

        elif order["state"] == OrderState.CONFIRMING:
            if message.lower() in ["evet", "hayır", "hayir"] or message in ["confirm_order_yes", "confirm_order_no"]:
                if message.lower() == "evet" or message == "confirm_order_yes":
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
                            response["text"] = f"Siparişiniz alındı. Sipariş numaranız: {order_number}. Teşekkür ederiz!"
                        else:
                            ai_siparis_logger.error(f"Failed to create Airtable record for user {user_id}. Returned order_number: {order_number}")
                            response["text"] = "Üzgünüz, siparişinizi kaydederken bir hata oluştu. Lütfen daha sonra tekrar deneyin."
                    except Exception as e:
                        ai_siparis_logger.error(f"Error creating Airtable record for user {user_id}: {str(e)}", exc_info=True)
                        response["text"] = "Üzgünüz, siparişinizi kaydederken bir hata oluştu. Lütfen daha sonra tekrar deneyin."
                else:
                    order["state"] = OrderState.COLLECTING_NAME
                    response["text"] = "Özür dileriz. Bilgilerinizi tekrar alalım. Lütfen adınızı ve soyadınızı girin."
            else:
                response["text"] = "Lütfen 'Evet' veya 'Hayır' şeklinde yanıt verin."
                response["buttons"] = [
                    {"title": "Evet", "callback_data": "confirm_order_yes"},
                    {"title": "Hayır", "callback_data": "confirm_order_no"}
                ]

        else:
            ai_siparis_logger.error(f"Unexpected state: {order['state']} for user {user_id}")
            response["text"] = "Bir hata oluştu. Lütfen tekrar deneyin."

        return response

order_manager = OrderManager()

def handle_order(user_id: str, message: str, product_id: Optional[str] = None) -> Dict[str, Any]:
    ai_siparis_logger.info(f"Handling order for user {user_id}, message: {message}, product_id: {product_id}")
    try:
        response = order_manager.process_message(user_id, message, product_id)
        ai_siparis_logger.info(f"Order response: {response}")
        return response
    except Exception as e:
        ai_siparis_logger.error(f"Error in handle_order: {str(e)}", exc_info=True)
        return {"text": "Bir hata oluştu. Lütfen tekrar deneyin.", "buttons": []}

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