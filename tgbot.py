from telegram.ext import Updater
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler, Filters
from telegram.error import (TelegramError, Unauthorized, BadRequest, 
                            TimedOut, ChatMigrated, NetworkError)
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

TOKEN = '706594478:AAFjQFtuHgiR_DoB1HO9MJdPwoI_IpmkMzw'

REQUEST_KWARGS = {
    'proxy_url': 'http://127.0.0.1:1087'
}

# userId =  741547351

updater = Updater(TOKEN, request_kwargs=REQUEST_KWARGS)
dispatcher = updater.dispatcher

# 741547351
def start(bot, update):
    bot.send_message(chat_id=update.message.chat_id,
                     text="I'm a bot, please talk to me!")


start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)


def pos(bot, update):
    # bot.send_message(chat_id=update.message.chat_id, text='baby,come on! ')
    update.message.reply_text('Help!')


pos_handler = CommandHandler('pos', pos)
dispatcher.add_handler(pos_handler)


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
