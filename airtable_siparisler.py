#urun numarasi,isim soyisim, adresi ve telefon numarasi degiskenlerini aliyor olacak.
#Bu alinan degerlerle  airtable de record olustur.
#Record olusturduktan sonra airtable  record icin bir siparis numarasi atar bu siparis numarasini al.
#Siparis numarasini  ve olusturan bilgileri return et.

from pyairtable import Table
import os
from dotenv import load_dotenv

load_dotenv()

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")

table = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)

def create_airtable_record(product_id: str, name: str, address: str, phone: str) -> str:
    record = table.create({
        "Ürün Numarası": product_id,
        "İsim Soyisim": name,
        "Adres": address,
        "Telefon Numarası": phone
    })
    return record['id']  # Airtable'ın oluşturduğu benzersiz ID'yi sipariş numarası olarak kullanıyoruz