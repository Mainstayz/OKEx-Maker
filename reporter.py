from bitmex_ccxt import Bitmex
from config import Config
from ST_ATR_Strategy import super_trend_atr
from drawer import *
from config import Config
from RestBot import bot
import multiprocessing

settings = Config.load()

settings = Config.load()

bitmex = Bitmex(api_key=settings.api_key, secret=settings.secret, enable_proxy=settings.enable_proxy,
                test=settings.test)


def report(inputData):
    symbol = inputData['symbol']
    dateframe = inputData['dateframe']
    strategy = inputData['strategy']
    data = bitmex.fetch_ohlc(symbol=symbol, timeframe=dateframe)
    if strategy == 'STA':
        conf = settings.strategies['STA']
        atr, st, stx = super_trend_atr(data, conf['period'], conf['multiplier'])
        file = draw_candlestick_st(data, st)
        return file
    return None


def send_image(file):
    print(file)
    bot.sendPhoto(chat_id=741547351, photo=open(file, 'rb'))
