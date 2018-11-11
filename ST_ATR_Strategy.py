import sys
import pandas as pd
import numpy as np
import talib
from ExchangeInterface import *


def super_trend_atr(df, period, multiplier):
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


class CustomOrderManager(OrderManager):

    def place_orders(self):
        data = self.exchange.get_ohlc()

        conf = settings.strategies['STA']

        atr, st, stx = super_trend_atr(data, conf['period'], conf['multiplier'])
        signal = stx.values[-1]

        # 获取仓位
        position = self.position['currentQty']
        # 获取BTC
        free_btc = self.exchange.bitmex.free_funds()
        # 杠杆
        leverage = self.position['leverage']

        # 计算杠杆满仓
        price = self.instrument['lastPrice']
        mult = self.instrument["multiplier"]

        amount = quantity(mult, free_btc * leverage, price)
        log.logger.debug('杠杆满仓 %s' % amount)

        # 如果空仓
        if position == 0:
            # 获取 1/10 层仓位
            amount = int(amount * 0.9)
            # 如是是空信号
            if signal == 'down':
                amount = amount * -1

            order = self.exchange.create_limit_order(amount=amount, price=price)
            log.logger.debug('开仓 %s' % order)
            # 入库
            #
            order.pop('info')
            # 添加数据库
            save_order_record(order)
            if order['remaining'] != 0:
                log.logger.warning('开启子线程检查订单状态')
                pass

        # 如果持有多仓
        elif position > 0:
            if signal == 'down':
                position = 2 * position
                order = self.exchange.create_limit_order(amount=-position, price=price)
                log.logger.debug('开空仓 %s' % order)
                # 入库
                #
                order.pop('info')
                # 添加数据库
                save_order_record(order)
                if order['remaining'] != 0:
                    log.logger.warning('开启子线程检查订单状态')
                    pass
            pass
        # 如果持有空仓
        elif position < 0:
            if signal == 'up':
                position = 2 * position
                order = self.exchange.create_limit_order(amount=-position, price=price)
                log.logger.debug('开多仓 %s' % order)
                # 入库
                #
                order.pop('info')
                # 添加数据库
                save_order_record(order)
                if order['remaining'] != 0:
                    log.logger.warning('开启子线程检查订单状态')
                    pass
            pass


def run() -> None:
    order_manager = CustomOrderManager()
    # Try/except just keeps ctrl-c from printing an ugly stacktrace
    try:
        order_manager.run_loop()
    except (KeyboardInterrupt, SystemExit):
        sys.exit()


if __name__ == '__main__':
    run()
