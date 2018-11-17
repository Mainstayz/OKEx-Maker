from RestBot import *
from retrying import retry
def pushOrderInfoMessage(order):
    text = '{}: {} {} {} contract with price {}. filled {}, cost {}, and remaining {}.'.format(order['datetime'],
                                                                                               order['side'],
                                                                                               order['amount'],
                                                                                               order['symbol'],
                                                                                               order['price'],
                                                                                               order['filled'],
                                                                                               order['cost'],
                                                                                               order['remaining'])
    bot.sendMessage(chat_id=741547351, text=text)
@retry(stop_max_attempt_number=2)
def pushCommonMessage(content):
    print('retry ...')
    bot.sendMessage(chat_id=741547351, text=content)



pushCommonMessage('goodboy')