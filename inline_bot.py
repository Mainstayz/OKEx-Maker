import copy
from telegram.ext import Updater
from telegram.ext import CommandHandler, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from reporter import *
from config import Config
settings = Config.load()

############################### Bot ############################################

input_data = {}


def symbol_menu(bot, update):
    keyboard = [[InlineKeyboardButton('BTC', callback_data='symbol_BTC/USD')]]
    markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Choose the symbol:',
                              reply_markup=markup)


def dateframe_menu(bot, update):
    query = update.callback_query
    symbol = query.data.split('_')[1]
    input_data['symbol'] = symbol
    keyboard = [[InlineKeyboardButton('5Min', callback_data='dateframe_5Min')],
                [InlineKeyboardButton('15Min', callback_data='dateframe_15Min')]]
    markup = InlineKeyboardMarkup(keyboard)

    bot.edit_message_text(chat_id=query.message.chat_id,
                          message_id=query.message.message_id,
                          text='%s' % symbol,
                          reply_markup=markup)


def strategy_menu(bot, update):
    query = update.callback_query
    df = query.data.split('_')[1]
    input_data['dateframe'] = df
    text = query.message.text + '\n' + df
    keyboard = [[InlineKeyboardButton('STA', callback_data='strategy_STA')]]
    markup = InlineKeyboardMarkup(keyboard)
    bot.edit_message_text(chat_id=query.message.chat_id,
                          message_id=query.message.message_id,
                          text='%s' % text,
                          reply_markup=markup)


def done(bot, update):
    query = update.callback_query
    strategy = query.data.split('_')[1]
    input_data['strategy'] = strategy
    text = query.message.text + '\n' + strategy
    bot.edit_message_text(chat_id=query.message.chat_id,
                          message_id=query.message.message_id,
                          text='%s' % text,
                          reply_markup=None)
    data = copy.deepcopy(input_data)
    input_data.clear()
    file = report(data)
    if file:
        bot.sendPhoto(chat_id=741547351, photo=open(file, 'rb'))
    else:
        print('draw..error..')


############################# Handlers #########################################
TOKEN = '706594478:AAFjQFtuHgiR_DoB1HO9MJdPwoI_IpmkMzw'

REQUEST_KWARGS = {
    'proxy_url': 'http://127.0.0.1:1087'
}

updater = Updater(TOKEN, request_kwargs=REQUEST_KWARGS if settings.enable_proxy else None)

updater.dispatcher.add_handler(CommandHandler('info', symbol_menu))
updater.dispatcher.add_handler(CallbackQueryHandler(dateframe_menu, pattern='symbol_.*'))
updater.dispatcher.add_handler(CallbackQueryHandler(strategy_menu, pattern='dateframe_.*'))
updater.dispatcher.add_handler(CallbackQueryHandler(done, pattern='strategy_.*'))

updater.start_polling()
updater.idle()
################################################################################
