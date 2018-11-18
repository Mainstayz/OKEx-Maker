from RestBot import *
import multiprocessing
from retrying import retry


def _pushOrderInfoMessage(order):
    text = '{}: {} {} {} contract with price {}. filled {}, cost {}, and remaining {}.'.format(order['datetime'],
                                                                                               order['side'],
                                                                                               order['amount'],
                                                                                               order['symbol'],
                                                                                               order['price'],
                                                                                               order['filled'],
                                                                                               order['cost'],
                                                                                               order['remaining'])
    bot.sendMessage(chat_id=741547351, text=text)


# @retry(stop_max_attempt_number=2)

def _pushCommonMessage(content):
    bot.sendMessage(chat_id=741547351, text=content)


def pushCommonMessage(content):
    multiprocessing.Process(target=_pushCommonMessage, args=(content,)).start()


def pushOrderInfoMessage(order):
    multiprocessing.Process(target=_pushOrderInfoMessage, args=(order,)).start()


pushCommonMessage('goodboy')
