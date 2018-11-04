import sys
import atexit
import signal
from datetime import datetime
from time import sleep
from log import Logger
from bitmex_ccxt import Bitmex
from config import Config

log = Logger('exchangeInterface.log', level='debug')
settings = Config.load()


class ExchangeInterface:
    def __init__(self, symbol):
        self.symbol = symbol
        self.bitmex = Bitmex(api_key=settings.api_key, secret=settings.secret, enable_proxy=True, test=True)

    def get_orders(self):
        return self.bitmex.fetch_open_orders(self.symbol)

    def cancel_order(self, order):

        log.logger.info(
            "Canceling: %s %s %s %s" % (order['side'], order['amount'], order['symbol'], order['price']))
        while True:
            try:
                self.bitmex.cancel_order(order['id'])
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

    def get_orders(self):
        return self.bitmex.open_orders()

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

    def check_market_health(self):
        instrument = self.get_instrument()
        if instrument["state"] != "Open" and instrument["state"] != "Closed":
            raise Exception("The instrument %s is not open. State: %s" %
                            (self.symbol, instrument["state"]))
        if instrument['midPrice'] is None:
            raise Exception("Order book is empty, cannot quote")



class OrderManager:
    def __init__(self):
        self.exchange = ExchangeInterface(settings.symbol)
        # Once exchange is created, register exit handler that will always cancel orders
        # on any error.
        atexit.register(self.exit)
        signal.signal(signal.SIGTERM, self.exit)

        log.logger.info("Using symbol %s." % self.exchange.symbol)
        log.logger.info("Order Manager initializing, connecting to BitMEX. Live run: executing real trades.")

        self.start_time = datetime.now()
        self.instrument = self.exchange.get_instrument()
        self.starting_qty = self.exchange.get_delta()
        self.running_qty = self.starting_qty
        self.reset()

    def reset(self):
        self.exchange.cancel_all_orders()
        self.sanity_check()
        self.print_status()

    def print_status(self):
        """Print the current MM status."""

        margin = self.exchange.get_margin()
        position = self.exchange.get_position()
        self.running_qty = self.exchange.get_delta()
        self.start_XBt = margin['BTC']['total']
        log.logger.info("Current XBT Balance: %.6f" % self.start_XBt)
        log.logger.info("Current Contract Position: %d" % self.running_qty)
        # if settings.CHECK_POSITION_LIMITS:
        #     logger.info("Position limits: %d/%d" % (settings.MIN_POSITION, settings.MAX_POSITION))
        if position['currentQty'] != 0:
            log.logger.info("Avg Cost Price: %.f" % (float(position['avgCostPrice'])))
            log.logger.info("Avg Entry Price: %.f" % (float(position['avgEntryPrice'])))
        log.logger.info("Contracts Traded This Run: %d" % (self.running_qty - self.starting_qty))
        log.logger.info("Total Contract Delta: %.4f XBT" % self.exchange.calc_delta()['spot'])


    ###
    # Sanity
    ##
    def sanity_check(self):
        # 检查仓位
        self.exchange.check_market_health()

    def exit(self):
        log.logger.info("Shutting down. All open orders will be cancelled.")
        try:
            self.exchange.cancel_all_orders()
        except Exception as e:
            log.logger.info("Unable to cancel orders: %s" % e)
        sys.exit()




def run():
    # exchange = ExchangeInterface('BTC/USD')
    # orders = exchange.get_orders()
    # print(orders)
    # exchange.cancel_all_orders()
    # print(exchange.get_portfolio())
    # print(exchange.calc_delta())
    # print(exchange.get_ticker())
    manager = OrderManager()
    pass



if __name__ == '__main__':
    run()
