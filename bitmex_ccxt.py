import ccxt
import json

TOKEN = {
    "api": {
        "apiKey": "**************",
        "secret": "**************"},
    "test": {
        "apiKey": "7d1u9ttNtNZgnxSc60Usg3bG",
        "secret": "UVxPTX3hluddC3ElYLAlktlk7_vhaZMmtPXjRCiNqTFZMR7x"}
}

PAIR = "BTC/USD"
TEST = True

proxies = {
    'http': 'http://127.0.0.1:1087',  # these proxies won't work for you, they are here for example
    'https': 'http://127.0.0.1:1087',
}

exchange = ccxt.bitmex({
    'apiKey': '7d1u9ttNtNZgnxSc60Usg3bG',
    'secret': 'UVxPTX3hluddC3ElYLAlktlk7_vhaZMmtPXjRCiNqTFZMR7x',
    'proxies': proxies
})
if 'test' in exchange.urls:
    exchange.urls['api'] = exchange.urls['test']  # ←----- switch the base URL to testnet
exchange.enableRateLimit = True
exchange.create_limit_buy_order()
# 获取USD
mexbal = exchange.fetch_total_balance()
mexusd = mexbal['BTC'] * exchange.fetch_ticker('BTC/USD')['last']
print(mexbal)
print(mexusd)

respon = exchange.fetch_closed_orders('BTC/USD')

print(respon)

orders = exchange.fetch_orders('BTC/USD')
print(orders)
