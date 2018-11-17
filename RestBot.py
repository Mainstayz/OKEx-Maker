import telegram
from telegram.utils.request import Request
from config import Config

settings = Config.load()
bot = telegram.Bot(token='706594478:AAFjQFtuHgiR_DoB1HO9MJdPwoI_IpmkMzw',
                   request=Request(proxy_url='http://127.0.0.1:1087' if settings.enable_proxy else None))
