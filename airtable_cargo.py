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
cargo_logger = setup_logger('airtable_cargo', 'logs/airtable_cargo.log')

# check if the number exists in Takip numarasi
def check_tracking_number(tracking_number):
    # Implement your logic here
    cargo_logger.info(f"Checking tracking number: {tracking_number}")
    # if not exist in the table 
    # mesaji yaz> Bu takip numarasina ait kargo bulunamadi lutfen musteri temsilcisi ile iletisime gecin
    if not tracking_number_exists(tracking_number):
        cargo_logger.warning(f"Tracking number not found: {tracking_number}")
        return "Bu takip numarasina ait kargo bulunamadi. Lutfen musteri temsilcisi ile iletisime gecin."
    else:
        cargo_logger.info(f"Tracking number found: {tracking_number}")
        return "Kargo bilgileri bulundu."

def tracking_number_exists(tracking_number):
    # Implement your logic to check if the tracking number exists
    # This is a placeholder function
    return False

# ... rest of the airtable_cargo.py code ...