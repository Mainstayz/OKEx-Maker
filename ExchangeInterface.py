import os
import sys
import atexit
import signal
import constants
import csv
from datetime import datetime
from os.path import getmtime
from time import sleep
from log import Logger
from bitmex_ccxt import Bitmex
from config import Config
from RestBot import *

# log
log = Logger('exchangeInterface.log', level='debug')

# 需要监听的文件

watched_files = ['config.json']

# <class 'tuple'>: ('config.json', 1541306559.740827)
watched_files_mtimes = [(f, getmtime(f)) for f in watched_files]

settings = Config.load()


class ExchangeInterface:

    def __init__(self, symbol):
        self.symbol = symbol
        self.bitmex = Bitmex(api_key=settings.api_key, secret=settings.secret, enable_proxy=settings.enable_proxy,
                             test=settings.test)

    def get_ohlc(self, symbol=None, timeframe='15Min', limit=750):
        if symbol is None:
            symbol = self.symbol
        return self.bitmex.fetch_ohlc(symbol, timeframe=timeframe, limit=limit)

    def cancel_order(self, order):

        log.logger.info(
            "Canceling: %s %s %s %s" % (order['side'], order['amount'], order['symbol'], order['price']))
        while True:
            try:
                order = self.bitmex.cancel_order(order['id'])
                pushOrderInfoMessage(order)
                sleep(settings.api_rest_interval)
            except Exception as e:
                log.logger.error(e)
                sleep(settings.api_error_interval)
                pass
            else:
                break

    def cancel_all_orders(self):
        log.logger.info("Resetting current position. Canceling all existing orders.")
        # In certain cases, a WS update might not make it through before we call this.
        # For that reason, we grab via HTTP to ensure we grab them all.
        orders = self.get_orders()
        for order in orders:
            self.cancel_order(order)

        sleep(settings.api_rest_interval)

    def get_portfolio(self):

        contracts = settings.contracts
        portfolio = {}
        for symbol in contracts:
            position = self.bitmex.position(symbol=symbol)
            instrument = self.bitmex.instrument(symbol=symbol)

            if instrument['isQuanto']:
                future_type = "Quanto"
            elif instrument['isInverse']:
                future_type = "Inverse"
            elif not instrument['isQuanto'] and not instrument['isInverse']:
                future_type = "Linear"
            else:
                raise Exception("Unknown future type; not quanto or inverse: %s" % instrument['symbol'])

            if instrument['underlyingToSettleMultiplier'] is None:
                multiplier = float(instrument['multiplier']) / float(instrument['quoteToSettleMultiplier'])
            else:
                multiplier = float(instrument['multiplier']) / float(instrument['underlyingToSettleMultiplier'])

            portfolio[symbol] = {
                "currentQty": float(position['currentQty']),
                "futureType": future_type,
                "multiplier": multiplier,
                "markPrice": float(instrument['markPrice']),
                "spot": float(instrument['indicativeSettlePrice'])
            }

        return portfolio

    def calc_delta(self):
        """Calculate currency delta for portfolio"""
        portfolio = self.get_portfolio()
        spot_delta = 0
        mark_delta = 0
        for symbol in portfolio:
            item = portfolio[symbol]
            if item['futureType'] == "Quanto":
                spot_delta += item['currentQty'] * item['multiplier'] * item['spot']
                mark_delta += item['currentQty'] * item['multiplier'] * item['markPrice']
            elif item['futureType'] == "Inverse":
                spot_delta += (item['multiplier'] / item['spot']) * item['currentQty']
                mark_delta += (item['multiplier'] / item['markPrice']) * item['currentQty']
            elif item['futureType'] == "Linear":
                spot_delta += item['multiplier'] * item['currentQty']
                mark_delta += item['multiplier'] * item['currentQty']
        basis_delta = mark_delta - spot_delta
        delta = {
            "spot": spot_delta,
            "mark_price": mark_delta,
            "basis": basis_delta
        }
        return delta

    def get_position(self, symbol=None):
        if symbol is None:
            symbol = self.symbol
        return self.bitmex.position(symbol)

    def get_delta(self, symbol=None):
        if symbol is None:
            symbol = self.symbol
        return self.get_position(symbol)['currentQty']

    def get_instrument(self, symbol=None):
        if symbol is None:
            symbol = self.symbol
        return self.bitmex.instrument(symbol)

    def get_margin(self):
        return self.bitmex.funds()

    def get_orders(self, symbol=None):
        if symbol is None:
            symbol = self.symbol
        return self.bitmex.open_orders(symbol=symbol)

    def get_order_book(self, symbol=None):
        if symbol is None:
            symbol = self.symbol
        return self.bitmex.fetch_order_book(symbol=symbol);

    def edit_order(self, id, amount=None, price=None, params={}):
        return self.bitmex.edit_order(id=id, amount=amount, price=price, params=params)

    def get_highest_buy(self):
        buys = [o for o in self.get_orders() if o['side'] == 'buy']
        if not len(buys):
            return {'price': -2 ** 32}
        highest_buy = max(buys or [], key=lambda o: o['price'])
        return highest_buy if highest_buy else {'price': -2 ** 32}

    def get_lowest_sell(self):
        sells = [o for o in self.get_orders() if o['side'] == 'sell']
        if not len(sells):
            return {'price': 2 ** 32}
        lowest_sell = min(sells or [], key=lambda o: o['price'])
        return lowest_sell if lowest_sell else {'price': 2 ** 32}

    def get_ticker(self, symbol=None):
        if symbol is None:
            symbol = self.symbol
        return self.bitmex.ticker_data(symbol)

    def create_limit_buy_order(self, amount, price, symbol=None):
        if symbol is None:
            symbol = self.symbol
        return self.bitmex.create_limit_buy_order(symbol=symbol, amount=amount, price=price)

    def create_limit_sell_order(self, amount, price, symbol=None):
        if symbol is None:
            symbol = self.symbol
        return self.bitmex.create_limit_sell_order(symbol=symbol, amount=amount, price=price)

    def create_limit_order(self, amount, price, symbol=None):
        if symbol is None:
            symbol = self.symbol
        if amount > 0:
            return self.bitmex.create_limit_buy_order(symbol=symbol, amount=amount, price=price)
        elif amount < 0:
            return self.bitmex.create_limit_sell_order(symbol=symbol, amount=amount, price=price)
        else:
            log.logger.error('amount should not be Zero.')
            return None

    def check_market_health(self):
        instrument = self.get_instrument()
        if instrument["state"] != "Open" and instrument["state"] != "Closed":
            raise Exception("The instrument %s is not open. State: %s" %
                            (self.symbol, instrument["state"]))
        if instrument['midPrice'] is None:
            raise Exception("Order book is empty, cannot quote")


class OrderManager:
    def __init__(self):
        self.symbol = settings.symbol
        self.exchange = ExchangeInterface(self.symbol)
        # Once exchange is created, register exit handler that will always cancel orders
        # on any error.
        atexit.register(self.exit)
        signal.signal(signal.SIGTERM, self.exit)

        log.logger.info("Using symbol %s." % self.exchange.symbol)
        log.logger.info("Order Manager initializing, connecting to BitMEX. Live run: executing real trades.")

        self.start_time = datetime.now()

        self.instrument = None
        self.margin = None
        self.position = None

        self.reset()

    def reset(self):
        log.logger.info("Reset status")
        # 取消所以订单
        self.exchange.cancel_all_orders()
        # 检查环境
        self.sanity_check()
        # 更新状态
        self.print_status()
        # 下单
        self.place_orders()

    def print_status(self):

        """Print the current MM status."""
        # 更新
        self.instrument = self.exchange.get_instrument()

        # 获取合约钱包
        self.margin = self.exchange.get_margin()
        log.logger.info("Current XBT balance: %.6f" % self.margin['BTC']['total'])

        # 获取仓位信息
        self.position = self.exchange.get_position()
        running_qty = self.position['currentQty']

        log.logger.info("Current position: %d" % running_qty)

        leverage = self.position['leverage']
        log.logger.info("Current leverage: %d" % leverage)

        pushCommonMessage("Current XBT balance: %.6f, position: %d ." % (self.margin['BTC']['total'], running_qty))

        # 检查仓位
        # if settings.CHECK_POSITION_LIMITS:
        #     logger.info("Position limits: %d/%d" % (settings.MIN_POSITION, settings.MAX_POSITION))

        if running_qty != 0:
            log.logger.info("Avg Cost Price:: %.f" % (float(self.position['avgCostPrice'])))
            log.logger.info("Avg Entry Price: %.f" % (float(self.position['avgEntryPrice'])))

    def sanity_check(self):

        # 检查市场
        self.exchange.check_market_health()

        # TODO: 检查仓位

    def check_file_change(self):
        """Restart if any files we're watching have changed."""
        for f, mtime in watched_files_mtimes:
            if getmtime(f) > mtime:
                self.restart()

    def restart(self):
        '''这里需要发通知'''
        log.logger.info("Restarting the market maker...")
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def exit(self):
        '''这里需要发通知'''
        log.logger.info("Shutting down. All open orders will be cancelled.")
        try:
            self.exchange.cancel_all_orders()
            pass
        except Exception as e:
            log.logger.info("Unable to cancel orders: %s" % e)
        sys.exit()

    def place_orders(self):
        pass

    def run_loop(self):
        while True:
            # 清屏
            sys.stdout.write("-----\n")
            sys.stdout.flush()

            # 检查文件是否发生改变
            self.check_file_change()

            # 确保正常获取到市场行情
            self.sanity_check()

            # 打印当前状态
            self.print_status()

            # 下单
            self.place_orders()

            # 线程休息
            sleep(settings.loop_interval)


def XBt_to_XBT(XBt):
    return float(XBt) / 100000000


def XBT_to_XBt(XBT):
    return float(XBT) * 100000000


# 开仓成本
# 保证金 = 开仓成本/杠杆
def cost(mult, quantity, price):
    P = mult * price if mult >= 0 else mult / price
    return XBt_to_XBT(abs(quantity * P))


def quantity(mult, btc, price):
    '''根据BTC 以及 当前价格 换算成 数量'''
    P = mult * price if mult >= 0 else mult / price
    xbt = XBT_to_XBt(btc)
    return abs(xbt / P)


def save_order_record(order={}):
    order.pop('info')
    file = 'order.csv'
    is_exist = os.path.isfile(file)
    with open(file, "a") as csvFile:
        writer = csv.DictWriter(csvFile, list(order.keys()))
        if not is_exist:
            writer.writeheader()
            writer.writerow(order)
        csvFile.close()


def last_order_record():
    file = 'order.csv'
    is_exist = os.path.isfile(file)
    if not is_exist:
        return None

    order = None
    with open(file, "r") as csvFile:
        reader = csv.DictReader(csvFile)
        for record in reader:
            pass
        order = dict(record)
        csvFile.close()
    return order


def pushOrderInfoMessage(order):
    if order is None:
        return
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


def run():
    log.logger.info('BitMEX Market Maker Version: %s\n' % constants.VERSION)
    om = OrderManager()
    try:
        om.run_loop()
    except (KeyboardInterrupt, SystemExit):
        sys.exit()
