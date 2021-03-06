import numpy as np
import talib
import threading
import time
from exchangeInterface import *
from config import Config
import sys
from retrying import retry

settings = Config.load()
log.logger.warning('sys: %s' % ([sys.executable] + sys.argv))


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
        #  如果 basic_ub < final_ub[]
        df['final_ub'].iat[i] = df['basic_ub'].iat[i] if df['basic_ub'].iat[i] < df['final_ub'].iat[i - 1] or \
                                                         df['close'].iat[i - 1] > df['final_ub'].iat[i - 1] else \
            df['final_ub'].iat[i - 1]
        df['final_lb'].iat[i] = df['basic_lb'].iat[i] if df['basic_lb'].iat[i] > df['final_lb'].iat[i - 1] or \
                                                         df['close'].iat[i - 1] < df['final_lb'].iat[i - 1] else \
            df['final_lb'].iat[i - 1]

    # Set the Supertrend value
    df[st] = 0.00
    for i in range(period, len(df)):
        #  1. 做空 2.空转多 3.做空 4.多转空
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
            # 打印
            log.logger.info('Check order state...count down: %s S' % wait_time)

            # 暂停
            time.sleep(wait_duration)

            # 查询未成交完成的订单信息
            order_list = self.exchange.get_orders()

            if len(order_list) > 0:
                log.logger.info('Order info: %s ' % order_list[0])
                # 如果一直有订单信息
                wait_time = wait_time - wait_duration

                # 总等待时间少于等于0
                if wait_time <= 0:
                    break
            else:
                # 退出循环
                break

        # 如果 120秒 委托还无法成交
        if len(order_list) > 0:
            # 循环获取
            for order in order_list:

                symbol = order['symbol']
                order_book = self.exchange.get_order_book(symbol)

                if order['side'] == 'buy':
                    last_price = order_book['asks'][0][0] if len(order_book['asks']) > 0 else None
                else:
                    last_price = order_book['bids'][0][0] if len(order_book['bids']) > 0 else None

                order_id = order['id']

                # 修改订单信息
                edited_order = self.exchange.edit_order(order_id, price=last_price)
                log.logger.info('Fix order info: %s ' % edited_order)

                # save!!
                save_order_record(edited_order)
                pushOrderInfoMessage(edited_order)
                # 如果依旧无法成交
                if edited_order['remaining'] > 0:
                    return self.check_orders()

        log.logger.info('Check order state...Done!!!  %s S' % wait_time)
        return True

    def start_check_orders(self):
        t = threading.Thread(target=self.check_orders, name='Check_Orders_Thread')
        t.start()
        pass

    def handle_order(self, order):
        save_order_record(order)
        pushOrderInfoMessage(order)
        return self.check_orders()


    @retry(stop_max_attempt_number=10)
    def place_orders(self):

        data = self.exchange.get_ohlc()

        conf = settings.strategies['STA']

        # atr
        atr, st, stx = super_trend_atr(data, conf['period'], conf['multiplier'])

        signal = stx.values[-1]

        log.logger.info('signal %s' % signal)

        # 获取仓位
        position = self.position['currentQty']

        # 平均成本价
        avgCostPrice = self.position['avgCostPrice']

        # 平均入场价
        avgEntryPrice = self.position['avgEntryPrice']

        # 获取BTC
        total_btc = self.exchange.bitmex.total_funds()
        # 杠杆
        leverage = self.position['leverage']
        log.logger.info('Current leverage %s' % leverage)

        # 计算杠杆满仓

        mult = self.instrument["multiplier"]

        order_book = self.exchange.get_order_book()
        # 卖1
        ask_price = order_book['asks'][0][0] if len(order_book['asks']) > 0 else None
        # 买1
        bid_price = order_book['bids'][0][0] if len(order_book['bids']) > 0 else None

        amount = 0
        price = 0

        if signal == 'down':
            price = bid_price
            amount = quantity(mult, total_btc * leverage, bid_price) * -1
        else:
            price = ask_price
            amount = quantity(mult, total_btc * leverage, ask_price)

        log.logger.info('Full position %s' % amount)

        # 如果空仓
        if position == 0:
            # 获取 1/10 层仓位
            amount = int(amount * 0.1)
            # MA
            MA100 = talib.MA(data['close'], 100, 0)
            MA200 = talib.MA(data['close'], 200, 0)
            # 做多
            is_long = MA100[-1] - MA200[-1]

            # 上升趋势中，不做空
            if is_long > 0 and amount < 0:
                log.logger.info('Upward trend！！Don`t open Short position!!!')
                pushCommonMessage('Upward trend！！Don`t open Short position!!!')
                return
            if is_long <= 0 and amount > 0:
                log.logger.info('Down trend！！Don`t open Long position!!!')
                pushCommonMessage('Down trend！！Don`t open Long position!!!')
                return

            order = self.exchange.create_limit_order(amount=amount, price=price)
            log.logger.info('Open position: %s' % order)
            self.handle_order(order)


        # 如果持有多仓
        elif position > 0:
            # 做空
            if signal == 'down':
                # 平仓
                order = self.exchange.create_limit_order(amount=-position, price=price)
                log.logger.info('Close position: %s' % order)
                # 添加数据库
                if self.handle_order(order):
                    time.sleep(settings.api_rest_interval)
                    self.print_status()
                    self.place_orders()
            else:
                log.logger.info('waiting .... next loop')

        # 如果持有空仓
        elif position < 0:
            if signal == 'up':
                order = self.exchange.create_limit_order(amount=-position, price=price)
                log.logger.info('Close position: %s' % order)
                if self.handle_order(order):
                    time.sleep(settings.api_rest_interval)
                    self.print_status()
                    self.place_orders()
            else:
                log.logger.info('waiting .... next loop')

def run() -> None:
    order_manager = CustomOrderManager()
    # Try/except just keeps ctrl-c from printing an ugly stacktrace
    try:
        order_manager.run_loop()
    except (KeyboardInterrupt, SystemExit):
        sys.exit()


if __name__ == '__main__':
    run()
