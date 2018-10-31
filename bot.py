import os
import sys
import logging
from telegram import *
from telegram.ext import *
from threading import Thread
from functools import wraps

# 初始化Rot
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

# 打印入参数
logger.info("current pid: %s", os.getpid())
for i in range(len(sys.argv)):
    logger.info('argv %s %s'%(i,sys.argv[i]))


# action 装饰器
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



def start(bot, update):
    bot.sendMessage(chat_id=update.message.chat_id, text="Welcome !!")


def unknown(bot, update):
    update.message.reply_text("Sorry, I didn't understand that command!")

def main():

    TOKEN = '706594478:AAFjQFtuHgiR_DoB1HO9MJdPwoI_IpmkMzw'

    REQUEST_KWARGS = {
        'proxy_url': 'http://127.0.0.1:1087'
    }

    updater = Updater(TOKEN, request_kwargs=REQUEST_KWARGS)
    dispatcher = updater.dispatcher

    def stop_and_restart():
        """Gracefully stop the Updater and replace the current process with a new one"""
        updater.stop()
        os.execl(sys.executable, sys.executable, *sys.argv)

    def restart(bot, update):
        update.message.reply_text('Bot is restarting...')
        Thread(target=stop_and_restart).start()

    dispatcher.add_handler(CommandHandler('r', restart))

    dispatcher.add_handler(CommandHandler('start', start))

    # 放置最后
    dispatcher.add_handler(MessageHandler(Filters.command, unknown))

    updater.start_polling()

    updater.idle()
    pass



if __name__ == '__main__':
    main()