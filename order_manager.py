from enum import Enum
from typing import Dict, Optional
from airtable_siparisler import create_airtable_record

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
                    return f"Üzgünüz, siparişinizi kaydederken bir hata oluştu. Lütfen daha sonra tekrar deneyin. Hata: {str(e)}"
            elif message.lower() == "hayır":
                order["state"] = OrderState.COLLECTING_NAME
                return "Özür dileriz. Bilgilerinizi tekrar alalım. Lütfen adınızı ve soyadınızı girin."
            else:
                return "Lütfen 'Evet' veya 'Hayır' şeklinde yanıt verin."

        return "Bir hata oluştu. Lütfen tekrar deneyin."

order_manager = OrderManager()

def handle_order(user_id: str, message: str, product_id: Optional[str] = None) -> str:
    return order_manager.process_message(user_id, message, product_id)