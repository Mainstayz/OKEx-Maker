import ccxt
import json
import pandas as pd

TOKEN = {
    "api": {
        "apiKey": "**************",
        "secret": "**************"},
    "test": {
        "apiKey": "7d1u9ttNtNZgnxSc60Usg3bG",
        "secret": "UVxPTX3hluddC3ElYLAlktlk7_vhaZMmtPXjRCiNqTFZMR7x"}
}

proxies = {
    'http': 'http://127.0.0.1:1087',  # these proxies won't work for you, they are here for example
    'https': 'http://127.0.0.1:1087',
}


class Bitmex:

    def __init__(self, api_key, secret, enable_proxy=False, test=False):

        self.client = ccxt.bitmex()
        self.client.enableRateLimit = True

        self.client.apiKey = api_key
        self.client.secret = secret

        if enable_proxy:
            self.client.proxies = proxies
        if test:
            self.client.urls['api'] = self.client.urls['test']
        self.client.load_markets()

    def authentication_required(fn):
        """Annotation for methods that require auth."""

        def wrapped(self, *args, **kwargs):
            if not self.client.apiKey:
                msg = "You must be authenticated to use this method"
                raise Exception(msg)
            else:
                return fn(self, *args, **kwargs)

        return wrapped

    def _curl(self, data, method_name):
        try:
            res = eval(f'self.client.{method_name}(data)')
        except Exception as e:
            print(e)
        else:
            return res

    def fetch_order_book(self, symbol, limit=10, params={}):
        return self.client.fetch_order_book(symbol=symbol, limit=limit, params=params)

    # orderbook = okex.fetch_order_book('EOS/USDT', limit=10)

    # obj = okexChanged.load_fees()
    # print(client.exchange.fetch_tickers())
    # 买1价
    # bid = orderbook['bids'][0][0] if len(orderbook['bids']) > 0 else None

    # 卖1价
    # ask = orderbook['asks'][0][0] if len(orderbook['asks']) > 0 else None

    def ticker_data(self, symbol):
        return self.client.fetch_ticker(symbol)

    def instrument(self, symbol, filter=None):
        """filter = {"key": "value"}"""
        query = {}
        market_id = self.client.market_id(symbol)
        query['symbol'] = market_id
        if filter is not None:
            query['filter'] = json.dumps(filter)
        responder = self._curl(query, 'publicGetInstrument')
        return responder[0] if responder and len(responder) > 0 else None

    def fetch_ohlc(self, symbol, timeframe='15Min', limit=576):
        # 两天前
        ohloc_data = self.client.fetch_ohlcv(symbol, '5m', limit=limit, params={'reverse': True})
        df = pd.DataFrame(data=ohloc_data, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
        df['date'] = pd.to_datetime(df['date'], unit='ms')
        df.set_index("date", inplace=True)
        # 合并
        result = df['close'].resample(timeframe).ohlc()
        return result

    @authentication_required
    def funds(self):
        return self.client.fetch_balance()

    @authentication_required
    def total_funds(self):
        return self.client.fetch_total_balance()['BTC']

    @authentication_required
    def free_funds(self):
        return self.client.fetch_free_balance()['BTC']

    @authentication_required
    def total_usd(self):
        return self.total_funds() * self.client.fetch_ticker('BTC/USD')['last']

    @authentication_required
    def position(self, symbol):
        market_id = self.client.market_id(symbol)
        data = {'filter': json.dumps({'symbol': market_id})}
        array = self._curl(data, 'privateGetPosition')
        return array[0] if array and len(array) > 0 else None

    @authentication_required
    def isolate_margin(self, symbol, leverage):
        """Set the leverage on an isolated margin position"""
        market_id = self.client.market_id(symbol)
        dic = {
            'symbol': market_id,
            'leverage': leverage
        }
        return self._curl(dic, 'privatePostPositionLeverage')

    @authentication_required
    def delta(self, symbol):
        return self.position(symbol)['homeNotional']

    @authentication_required
    def open_orders(self, symbol=None, since=None, limit=None, params={}):
        return self.client.fetch_open_orders(symbol=symbol, since=since, limit=limit, params=params)

    @authentication_required
    def cancel_order(self, order_id=None):
        return self.client.cancel_order(id=order_id)

    @authentication_required
    def create_limit_buy_order(self, symbol, amount, price):
        return self.client.create_order(symbol=symbol, type='limit', side='buy', amount=amount, price=price)

    @authentication_required
    def create_limit_sell_order(self, symbol, amount, price):
        return self.client.create_order(symbol=symbol, type='limit', side='sell', amount=amount, price=price)

    @authentication_required
    def edit_order(self, id, amount=None, price=None, params={}):
        return self.client.edit_order(id=id, symbol=None, type=None, side=None, amount=amount, price=price,
                                      params=params)


if __name__ == '__main__':
    pass
    access = TOKEN['test']
    bitmex = Bitmex(api_key=access['apiKey'], secret=access['secret'], enable_proxy=True, test=True)
    # orders = bitmex.open_orders('BTC/USD')
    # print(orders)
    # print(bitmex.delta('XBTUSD'))
    # print(bitmex.isolate_margin('XBTUSD', 5))
    print(bitmex.instrument('BTC/USD'))
    # bitmex.client.load_markets()
    # print(bitmex.client.market_id('BTC/USD'))
    # print(bitmex.funds())
    # print(bitmex.position('BTC/USD'))
    # print(bitmex.cancel_order('77b5bfe7-9b7b-25da-4734-e7cb23e2cd0c'))

    # result = bitmex.free_funds()
    # leverage = 5
    # rick = result * 5
    # bitPrice = bitmex.client.fetch_ticker('BTC/USD')['last']
    # pos = bitPrice * rick
    # print(pos)

    #  0.00889511 * 5 = 0.0413198 总用可用的XBT
    # 6344.5 * 0.0413198 = 262.1534711

    # 买单
    # responder = bitmex.client.create_order(symbol='BTC/USD', type='limit', side='buy', amount=10, price=6345.0)

    # print(responder)

    # bitmex.create_limit_sell_order('BTC/USD', 20, 6338.5)
