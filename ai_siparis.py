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
    CORRECTING = 6
    COMPLETED = 7

class OrderManager:
    def __init__(self):
        self.orders: Dict[str, Dict] = {}

    def get_or_create_order(self, user_id: str) -> Dict:
        if user_id not in self.orders:
            self.orders[user_id] = self._create_new_order()
        return self.orders[user_id]

    def _create_new_order(self) -> Dict:
        return {
            "state": OrderState.IDLE,
            "name": "",
            "address": "",
            "phone": "",
            "product_id": "",
            "text": "",
            "order_number": "",
            "correction_field": None
        }

    def validate_phone(self, phone: str) -> bool:
        cleaned_phone = re.sub(r'\D', '', phone)
        return 10 <= len(cleaned_phone) <= 15

    def validate_name(self, name: str) -> bool:
        return len(name.split()) >= 1 and all(part.isalpha() for part in name.split())

    def validate_address(self, address: str) -> bool:
        return len(address) >= 5

    def get_order_summary(self, order: Dict) -> str:
        return (f"Bilgilerinizi özetliyorum:\n"
                f"İsim: {order['name']}\n"
                f"Adres: {order['address']}\n"
                f"Telefon: {order['phone']}\n"
                f"Ürün No: {order['product_id']}\n"
                f"Ürün Metni: {order['text'] or 'Yok'}\n"
                f"Bu bilgiler doğru mu?")

    def get_correction_buttons(self) -> List[Dict[str, str]]:
        return [
            {"title": "İsim", "callback_data": "correct_name"},
            {"title": "Adres", "callback_data": "correct_address"},
            {"title": "Telefon", "callback_data": "correct_phone"},
            {"title": "Ürün Metni", "callback_data": "correct_text"},
            {"title": "Ürün No", "callback_data": "correct_product_id"}
        ]

    def process_message(self, user_id: str, message: str, product_id: Optional[str] = None) -> Dict[str, Any]:
        order = self.get_or_create_order(user_id)
        ai_siparis_logger.info(f"Processing message for user {user_id}, current state: {order['state']}, message: {message}, product_id: {product_id}")

        if product_id:
            return self._start_new_order(order, product_id)

        state_handlers = {
            OrderState.IDLE: self._handle_idle_state,
            OrderState.COLLECTING_NAME: self._handle_collecting_name,
            OrderState.COLLECTING_ADDRESS: self._handle_collecting_address,
            OrderState.COLLECTING_PHONE: self._handle_collecting_phone,
            OrderState.COLLECTING_TEXT: self._handle_collecting_text,
            OrderState.CONFIRMING: self._handle_confirming,
            OrderState.CORRECTING: self._handle_correcting,
        }

        handler = state_handlers.get(order['state'], self._handle_unknown_state)
        return handler(order, message)

    def _start_new_order(self, order: Dict, product_id: str) -> Dict[str, Any]:
        order["product_id"] = product_id
        order["state"] = OrderState.COLLECTING_NAME
        return {"text": f"Ürün {product_id} için siparişinizi almaya başlıyoruz. Lütfen adınızı ve soyadınızı girin."}

    def _handle_idle_state(self, order: Dict, message: str) -> Dict[str, Any]:
        return {"text": "Lütfen bir ürün seçin veya yardım için müşteri temsilcisiyle iletişime geçin."}

    def _handle_collecting_name(self, order: Dict, message: str) -> Dict[str, Any]:
        if self.validate_name(message):
            order["name"] = message
            order["state"] = OrderState.COLLECTING_ADDRESS
            return {"text": "Teşekkürler. Şimdi lütfen adresinizi girin."}
        else:
            return {"text": "Geçersiz isim. Lütfen adınızı ve soyadınızı tekrar girin."}

    def _handle_collecting_address(self, order: Dict, message: str) -> Dict[str, Any]:
        if self.validate_address(message):
            order["address"] = message
            order["state"] = OrderState.COLLECTING_PHONE
            return {"text": "Adresinizi aldık. Son olarak, telefon numaranızı girer misiniz? (Örnek: 05551234567)"}
        else:
            return {"text": "Geçersiz adres. Lütfen en az 5 karakterden oluşan bir adres girin."}

    def _handle_collecting_phone(self, order: Dict, message: str) -> Dict[str, Any]:
        if self.validate_phone(message):
            order["phone"] = message
            order["state"] = OrderState.COLLECTING_TEXT
            return {"text": "Teşekkürler. Ürün üzerine yazdırmak istediğiniz metni girin. Eğer istemiyorsanız 'Yok' yazabilirsiniz."}
        else:
            return {"text": "Geçersiz telefon numarası. Lütfen 5551234567 formatında bir numara girin."}

    def _handle_collecting_text(self, order: Dict, message: str) -> Dict[str, Any]:
        order["text"] = message if message.lower() != "yok" else ""
        order["state"] = OrderState.CONFIRMING
        return {"text": self.get_order_summary(order), "buttons": [
            {"title": "Evet", "callback_data": "confirm_order_yes"},
            {"title": "Hayır", "callback_data": "confirm_order_no"}
        ]}

    def _handle_confirming(self, order: Dict, message: str) -> Dict[str, Any]:
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
                        return {"text": f"Siparişiniz alındı. Sipariş numaranız: {order_number}. Teşekkür ederiz!"}
                    else:
                        ai_siparis_logger.error(f"Failed to create Airtable record for user {user_id}. Returned order_number: {order_number}")
                        return {"text": "Üzgünüz, siparişinizi kaydederken bir hata oluştu. Lütfen daha sonra tekrar deneyin."}
                except Exception as e:
                    ai_siparis_logger.error(f"Error creating Airtable record for user {user_id}: {str(e)}", exc_info=True)
                    return {"text": "Üzgünüz, siparişinizi kaydederken bir hata oluştu. Lütfen daha sonra tekrar deneyin."}
            else:
                order["state"] = OrderState.CORRECTING
                return {"text": "Hangi bilgiyi düzeltmek istersiniz?", "buttons": self.get_correction_buttons()}
        else:
            return {"text": "Lütfen 'Evet' veya 'Hayır' şeklinde yanıt verin.", "buttons": [
                {"title": "Evet", "callback_data": "confirm_order_yes"},
                {"title": "Hayır", "callback_data": "confirm_order_no"}
            ]}

    def _handle_correcting(self, order: Dict, message: str) -> Dict[str, Any]:
        if message.startswith("correct_"):
            order["correction_field"] = message[8:]
            return {"text": f"Lütfen yeni {order['correction_field']} bilgisini girin:"}
        else:
            if order["correction_field"] == "name":
                if self.validate_name(message):
                    order["name"] = message
                else:
                    return {"text": "Geçersiz isim. Lütfen adınızı ve soyadınızı tekrar girin."}
            elif order["correction_field"] == "address":
                if self.validate_address(message):
                    order["address"] = message
                else:
                    return {"text": "Geçersiz adres. Lütfen en az 5 karakterden oluşan bir adres girin."}
            elif order["correction_field"] == "phone":
                if self.validate_phone(message):
                    order["phone"] = message
                else:
                    return {"text": "Geçersiz telefon numarası. Lütfen 5551234567 formatında bir numara girin."}
            elif order["correction_field"] == "text":
                order["text"] = message if message.lower() != "yok" else ""
            elif order["correction_field"] == "product_id":
                order["product_id"] = message

            order["state"] = OrderState.CONFIRMING
            return {"text": self.get_order_summary(order), "buttons": [
                {"title": "Evet", "callback_data": "confirm_order_yes"},
                {"title": "Hayır", "callback_data": "confirm_order_no"}
            ]}

    def _handle_unknown_state(self, order: Dict, message: str) -> Dict[str, Any]:
        ai_siparis_logger.error(f"Unexpected state: {order['state']}")
        return {"text": "Bir hata oluştu. Lütfen tekrar deneyin."}

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