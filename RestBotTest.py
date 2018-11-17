from RestBot import *

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


def pushCommonMessage(content):
    bot.sendMessage(chat_id=741547351, text=content)
