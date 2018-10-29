import telegram
from telegram.ext import Updater
from telegram.ext import CommandHandler, CallbackQueryHandler
from telegram.ext import MessageHandler, Filters
from telegram.error import (TelegramError, Unauthorized, BadRequest, 
                            TimedOut, ChatMigrated, NetworkError)
from functools import wraps
from telegram import ChatAction
from telegram import (InlineKeyboardButton,InlineKeyboardMarkup)

import logging
import os
import sys
from threading import Thread



logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)


logger.warning("current pid: %s", os.getpid())
len = len(sys.argv)
for i in range(len):
    logger.warning(sys.argv[i])

TOKEN = ''

REQUEST_KWARGS = {
    'proxy_url': 'http://127.0.0.1:1087'
}

# userId =  741547351

# decorater:不用每定义一个函数都要用handler以及add_handler
#@command(CommandHandler,'start')
#@command(MessageHandler,Filters.text)
def command(handler,cmd=None,**kw):
    def decorater(func):
        def wrapper(*args,**kw):
            return func(*args,**kw)
        if cmd==None:
            func_hander=handler(func,**kw)
        else:
            func_hander=handler(cmd,func,**kw)
        dispatcher.add_handler(func_hander)
        return wrapper
    return decorater



def send_action(action):
    """Sends `action` while processing func command."""

    def decorator(func):
        @wraps(func)
        def command_func(*args, **kwargs):
            bot, update = args
            bot.send_chat_action(chat_id=update.message.chat_id, action=action)
            func(bot, update, **kwargs)
        return command_func
    
    return decorator


send_typing_action = send_action(ChatAction.TYPING)
send_upload_video_action = send_action(ChatAction.UPLOAD_VIDEO)
send_upload_photo_action = send_action(ChatAction.UPLOAD_PHOTO)



LIST_OF_ADMINS = [12345678, 87654321]

def restricted(func):
    @wraps(func)
    def wrapped(bot, update, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in LIST_OF_ADMINS:
            print("Unauthorized access denied for {}.".format(user_id))
            return
        return func(bot, update, *args, **kwargs)
    return wrapped



updater = Updater(TOKEN, request_kwargs=REQUEST_KWARGS)
dispatcher = updater.dispatcher

# 741547351
def start(bot, update):
    keyboard = [[InlineKeyboardButton("Option 1", callback_data='1'),
                 InlineKeyboardButton("Option 2", callback_data='2')],

                [InlineKeyboardButton("Option 3", callback_data='3')]]

    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text('Please choose:', reply_markup=reply_markup)

start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)



def button(bot, update):
    query = update.callback_query
    bot.edit_message_text(text="Selected option: {}".format(query.data),
                          chat_id=query.message.chat_id,
                          message_id=query.message.message_id)
                          
dispatcher.add_handler(CallbackQueryHandler(button))



def pos(bot, update):
    # bot.send_message(chat_id=update.message.chat_id, text='baby,come on! ')
    update.message.reply_text('Help!')

pos_handler = CommandHandler('pos', pos)
dispatcher.add_handler(pos_handler)


def location(bot,update):
    location_keyboard = telegram.KeyboardButton(text="send_location", request_location=True)
    contact_keyboard = telegram.KeyboardButton(text="send_contact", request_contact=True)
    custom_keyboard = [[ location_keyboard, contact_keyboard ]]
    reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
    bot.send_message(chat_id=update.message.chat_id, 
                     text="Would you mind sharing your location and contact with me?", 
                     reply_markup=reply_markup)

pos_handler = CommandHandler('loc', location)
dispatcher.add_handler(pos_handler)



def reply(bot,update):
    custom_keyboard = [['top-left', 'top-right'], 
                       ['bottom-left', 'bottom-right']]
    reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
    bot.send_message(chat_id=update.message.chat_id, 
                     text="Custom Keyboard Test", 
                     reply_markup=reply_markup)


pos_handler = CommandHandler('re', reply)
dispatcher.add_handler(pos_handler)



#args = ['up', 'to', 'my', 'next', 'start']
@send_typing_action
def caps(bot, update, args):
    text_caps = ' '.join(args).upper()
    bot.send_message(chat_id=update.message.chat_id, text=text_caps)


caps_handler = CommandHandler('caps', caps, pass_args=True)
dispatcher.add_handler(caps_handler)


def echo(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text=update.message.text)


echo_handler = MessageHandler(Filters.text, echo)
dispatcher.add_handler(echo_handler)


# def callback_minute(bot,job):
#     bot.send_message(chat_id='741547351', text='message')


# j = updater.job_queue
# job_minute = j.run_repeating(callback_minute, interval=60, first=0)





def stop_and_restart():
    """Gracefully stop the Updater and replace the current process with a new one"""
    updater.stop()
    logger.info('executable %s  ' % sys.executable)
    os.execl(sys.executable, sys.executable, *sys.argv)

def restart(bot, update):
    update.message.reply_text('Bot is restarting...')
    Thread(target=stop_and_restart).start()

dispatcher.add_handler(CommandHandler('r', restart))#filters=Filters.user(username='@jh0ker')))

def unknown(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text="Sorry, I didn't understand that command.")

unknown_handler = MessageHandler(Filters.command, unknown)
dispatcher.add_handler(unknown_handler)



    

def error_callback(bot, update, error):
    logger.warning('Update "%s" caused error "%s"', update, error)
    try:
        raise error
    except Unauthorized:
        # remove update.message.chat_id from conversation list
        pass
    except BadRequest:
        # handle malformed requests - read more below!
        pass
    except TimedOut:
        # handle slow connection problems
        pass
    except NetworkError:
        # handle other connection problems
        pass
    except ChatMigrated as e:
        # the chat_id of a group has changed, use e.new_chat_id instead
        pass
    except TelegramError:
        # handle all other telegram related errors
        pass

dispatcher.add_error_handler(error_callback)

# 启动机器人
updater.start_polling()





updater.idle()
