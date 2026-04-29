# core/stats.py
import time
from datetime import datetime

START_TIME = time.time()
LAST_MESSAGE_AT = None

def update_last_message():
    global LAST_MESSAGE_AT
    LAST_MESSAGE_AT = datetime.now()

def get_uptime():
    return int(time.time() - START_TIME)
