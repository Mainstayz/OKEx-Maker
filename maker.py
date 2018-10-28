import ccxt
import pandas as pd
import numpy as np
import datetime as dt
import time
import talib
from log import Logger
from config import *

pd.set_option('expand_frame_repr', False)
pd.set_option('display.max_columns', 10)
pd.set_option('display.max_rows', 500)

# 代理
enable_proxies = True

proxies = {
    # these proxies won't work for you, they are here for example
    'http': 'http://127.0.0.1:8001',
    'https': 'http://127.0.0.1:8001',
}
apiKey = ''
secret = ''

base = ['XRP', 'OF']
quote = 'USDT'

# 获取2天前的K线
hours = 48
# 15m 周期
timeframe = '15m'

# 指标
period = 7
multiplier = 3

log = Logger('all.log',level='debug')

log.logger.info('----- start -----')

def beforeHours2Timestamp(hours):
    return int(time.time() * 1000) - hours*60*60*1000


def ymdhms(timestamp):
    utc_datetime = dt.datetime.utcfromtimestamp(int(round(timestamp / 1000)))
    return utc_datetime.strftime('%Y-%m-%d' + ' ' + '%H:%M:%S')


def super_trend_ATR(df, period, multiplier):

    atr = 'atr_' + str(period)
    st = 'st_' + str(period) + '_' + str(multiplier)
    stx = 'stx_' + str(period) + '_' + str(multiplier)

    df[['open', 'high', 'low', 'close']] = df[[
        'open', 'high', 'low', 'close']].astype(float)

    df[atr] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=period)
    # Compute basic upper and lower bands
    df['basic_ub'] = (df['high'] + df['low']) / 2 + multiplier * df[atr]
    df['basic_lb'] = (df['high'] + df['low']) / 2 - multiplier * df[atr]

    # Compute final upper and lower bands
    df['final_ub'] = 0.00
    df['final_lb'] = 0.00

    for i in range(period, len(df)):
        df['final_ub'].iat[i] = df['basic_ub'].iat[i] if df['basic_ub'].iat[i] < df['final_ub'].iat[i - 1] or \
            df['close'].iat[i - 1] > df['final_ub'].iat[i - 1] else \
            df['final_ub'].iat[i - 1]
        df['final_lb'].iat[i] = df['basic_lb'].iat[i] if df['basic_lb'].iat[i] > df['final_lb'].iat[i - 1] or \
            df['close'].iat[i - 1] < df['final_lb'].iat[i - 1] else \
            df['final_lb'].iat[i - 1]

    # Set the Supertrend value
    df[st] = 0.00
    for i in range(period, len(df)):
        df[st].iat[i] = df['final_ub'].iat[i] if df[st].iat[i - 1] == df['final_ub'].iat[i - 1] and df['close'].iat[
            i] <= df['final_ub'].iat[i] else \
            df['final_lb'].iat[i] if df[st].iat[i - 1] == df['final_ub'].iat[i - 1] and df['close'].iat[i] > \
            df['final_ub'].iat[i] else \
            df['final_lb'].iat[i] if df[st].iat[i - 1] == df['final_lb'].iat[i - 1] and df['close'].iat[i] >= \
            df['final_lb'].iat[i] else \
            df['final_ub'].iat[i] if df[st].iat[i - 1] == df['final_lb'].iat[i - 1] and df['close'].iat[i] < \
            df['final_lb'].iat[i] else 0.00

    # Mark the trend direction up/down
    df[stx] = np.where((df[st] > 0.00), np.where(
        (df['close'] < df[st]), 'down', 'up'), None)

    # Remove basic and final bands from the columns
    df.drop(['basic_ub', 'basic_lb', 'final_ub',
             'final_lb'], inplace=True, axis=1)

    # save
    result = df[[atr, st, stx]].copy()

    # Remove
    df.drop([atr, st, stx], inplace=True, axis=1)

    result.fillna(0, inplace=True)

    return result[atr], result[st], result[stx]


exchange = ccxt.okex({'proxies': proxies if enable_proxies else None, 'apiKey': apiKey,
                      'secret': secret,
                      'timeout': 20000,
                      'enableRateLimit': True})
# 两天前
since = beforeHours2Timestamp(hours)

for currency in base:

    info = exchange.fetch_balance()
    base_pos = info[currency]
    quote_pos = info[quote]
    
    # 货币组合
    symbol = '{}/{}'.format(currency, quote)

    # 获取K线
    data = exchange.fetchOHLCV(symbol=symbol, timeframe=timeframe, since=since)

    kline_data = pd.DataFrame(data=data, columns=[
                              'timestamp', 'open', 'high', 'low', 'close', 'volume'], dtype=float)

    business_date = kline_data.timestamp.apply(lambda x: ymdhms(x))
    # 插入date
    kline_data.insert(0, 'date', business_date)

    # 获取信号
    atr, st, stx = super_trend_ATR(kline_data, period, multiplier)

    signal = stx.values[-1]

    if signal == 'down':
        # 如果有仓位
        if base_pos['free'] > 1:
            amount = base_pos['free']
            response = exchange.create_market_sell_order(symbol, amount)
            log.logger.debug('%s Sell:%s' % (symbol, response))
        else:
            log.logger.debug('%s down.. And nothing ...',symbol)

    elif signal == 'up':
        # 满仓就是干
        if quote_pos['free'] > 1:
            free_quote = quote_pos['free']
            order_book = exchange.fetch_order_book(symbol, limit=10)
            # 卖1价
            ask = order_book['asks'][0][0] if len(order_book['asks']) > 0 else None
            amount = free_quote / ask
            response = exchange.create_limit_buy_order(symbol, amount, ask)
            log.logger.debug('%s Bull:%s' % (symbol, response))
        else:
            log.logger.debug('%s up.. And nothing ...',symbol)
    else:
        pass

    time.sleep(10)
