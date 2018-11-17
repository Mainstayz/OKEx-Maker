import numpy as np
import talib
import threading
import time

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

    def check_orders(self):

        # 等待时间
        wait_time = 120

        # 每次等待时间
        wait_duration = 10

        order_list = []

        while True:
            log.logger.info('Check order state...count down: %s S' % wait_time)

            # 暂停
            time.sleep(wait_duration)
            # 查询订单信息
            order_list = self.exchange.get_orders()
            if len(order_list) > 0:
                log.logger.info('Order info: %s ' % order_list[0])
                # 如果一直有订单信息
                wait_time = wait_time - wait_duration
                if wait_time <= 0:
                    break
            else:
                break

        # 如果 120秒 委托还无法成交
        if len(order_list) > 0:
            for order in order_list:

                symbol = order['symbol']
                order_book = self.exchange.get_order_book(symbol)
                if order['side'] == 'buy':
                    last_price = order_book['asks'][0][0] if len(order_book['asks']) > 0 else None
                else:
                    last_price = order_book['bids'][0][0] if len(order_book['bids']) > 0 else None

                order_id = order['id']

                edited_order = self.exchange.edit_order(order_id, price=last_price)
                log.logger.info('Fix order info: %s ' % edited_order)
                # save!!
                save_order_record(edited_order)
                pushOrderInfoMessage(edited_order)
                # 如果依旧无法成交
                if edited_order['remaining'] > 0:
                    return self.check_orders()

        return None

    def start_check_orders(self):
        t = threading.Thread(target=self.check_orders, name='Check_Orders_Thread')
        t.start()
        pass

    def handle_order(self, order):
        save_order_record(order)
        pushOrderInfoMessage(order)
        self.start_check_orders()

    def place_orders(self):

        data = self.exchange.get_ohlc()

        conf = settings.strategies['STA']

        atr, st, stx = super_trend_atr(data, conf['period'], conf['multiplier'])
        signal = stx.values[-1]

        # 获取仓位
        position = self.position['currentQty']
        # 获取BTC
        total_btc = self.exchange.bitmex.total_funds()
        # 杠杆
        leverage = self.position['leverage']
        log.logger.info('Current leverage %s' % leverage)

        # 计算杠杆满仓
        price = self.instrument['lastPrice']
        mult = self.instrument["multiplier"]

        amount = quantity(mult, total_btc * leverage, price)

        log.logger.info('Full position %s' % amount)

        # 如果空仓
        if position == 0:
            # 获取 1/10 层仓位
            amount = int(amount * 0.9)
            # 如是是空信号
            if signal == 'down':
                amount = amount * -1

            order = self.exchange.create_limit_order(amount=amount, price=price)
            log.logger.info('Open position: %s' % order)
            # save!!
            self.handle_order(order)


        # 如果持有多仓
        elif position > 0:
            # 做空
            if signal == 'down':
                # 平仓加开仓
                position = abs(position) + int(amount * 0.9)
                order = self.exchange.create_limit_order(amount=-position, price=price)
                log.logger.info('Make short position: %s' % order)
                # 添加数据库
                self.handle_order(order)

            pass
        # 如果持有空仓
        elif position < 0:
            if signal == 'up':
                position = abs(position) + int(amount * 0.9)
                order = self.exchange.create_limit_order(amount=position, price=price)
                log.logger.info('Make long position: %s' % order)
                # 添加数据库
                self.handle_order(order)
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
