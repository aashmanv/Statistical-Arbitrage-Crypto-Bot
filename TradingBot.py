#initialize packages
from binance.client import Client
import pandas as pd
import time

#insert binance api key and secret
api_key = 'KINloFU4wVbIZjUetQSVwtSYJnZaOFyjvHgpJxteDlWflDKsKpym8raOQRpIxG66'
api_secret = 'askcWzSu8aayZMedUMav7qXtCNr2CNQfQQgksx82cIC9UYG2TCQ0KXCGCzE2NOQK'

client = Client(api_key, api_secret)

global trading_pair
global bb_range
#MA range for Bollinger bands
bb_range = 20
global bb_std_mult
#SD multiplier for BBs
bb_std_mult = 2


#price data pull function
def getpricedata():
    global trading_pair
    #pulls price data from binance
    klines = client.get_historical_klines(trading_pair, Client.KLINE_INTERVAL_1MINUTE, "20 minutes ago UTC")
    global price_df
    price_df = pd.DataFrame(klines, columns=['open_time','open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol','is_best_match'])


    #cleans up the data frame, removes unecessary columns
    del price_df['open_time']
    del price_df['open']
    #del price_df['high']
    #del price_df['low']
    del price_df['volume']
    del price_df['close_time']
    del price_df['qav']
    del price_df['num_trades']
    del price_df['taker_base_vol']
    del price_df['taker_quote_vol']
    del price_df['is_best_match']

    global bb_range
    global bb_std_mult

    global bb_ma
    global bb_std
    global bb_upper
    global bb_lower
    global last_candle_close
    global last_candle_low
    global last_candle_high

    #calculate MA and SD
    price_df['MA'] = price_df['close'].rolling(window=bb_range).mean()
    price_df['STD_DEV'] = price_df['close'].rolling(window=bb_range).std()

    #calculate variables
    print(len(price_df.index)-1)
    bb_ma = float(price_df.iloc[len(price_df.index)-1]['MA'])
    bb_std = float(price_df.iloc[len(price_df.index)-1]['STD_DEV'])
    bb_upper = bb_ma + (bb_std_mult * bb_std)
    bb_lower = bb_ma - (bb_std_mult * bb_std)
    last_candle_close = float(price_df.iloc[len(price_df.index)-1]['close'])
    last_candle_high = float(price_df.iloc[len(price_df.index)-1]['high'])
    last_candle_low = float(price_df.iloc[len(price_df.index)-1]['low'])

    #print info in console
    print(trading_pair)
    print('moving average: '+str(bb_ma))
    #print('std dev: '+str(bb_std))
    print('upper BB: '+str(bb_upper))
    print('lower BB: '+str(bb_lower))
    print('last price: '+str(last_candle_close))


#variables for bot function
global position_active
position_active = False
global position_type
position_type = ''
global position_entry_price
position_entry_price = 0
global order_quantity
global stop_loss_tolerance
stop_loss_tolerance = 0
global bad_trade_count
bad_trade_count = 0
global total_trade_count
total_trade_count = 0
global lastshortfail
lastshortfail = False
global lastlongfail
lastlongfail = False
global long_allowed
long_allowed = True
global short_allowed
short_allowed = True
global bad_trade_from_mean
bad_trade_from_mean = 0
global bad_trade_from_stoploss
bad_trade_from_stoploss = 0


def run_bot():
    global trading_pair
    global bb_ma
    global last_candle_close
    global position_active
    global bb_lower
    global bb_upper
    global position_type
    global order_quantity
    global stop_loss_tolerance
    global position_entry_price
    global bad_trade_count
    global total_trade_count
    global lastshortfail
    global lastlongfail
    global long_allowed
    global short_allowed
    global bad_trade_from_mean
    global bad_trade_from_stoploss

    bb_ma_rounded = round(bb_ma, 5)
    last_candle_close_rounded = round(last_candle_close, 5)

    stop_loss_tolerance = ((bb_upper-bb_ma)/bb_upper)+1
    print('dynamic stop loss tolerance: '+str(stop_loss_tolerance))

    #if last candle forced a stop loss, if the current candle is outside BB don't execute a long/short
    if position_active == False:

        if lastshortfail == True:
            if last_candle_close >= bb_upper:
                short_allowed = False
            else:
                short_allowed = True

        if lastlongfail == True:
            if last_candle_close <= bb_lower:
                long_allowed = False
            else:
                long_allowed = True

        if (last_candle_close > bb_upper) and (short_allowed == True):
            #short delay as when bands are breached, price goes a little further: this places a more favorable market order.
            time.sleep(1)
            go_short = client.futures_create_order(
                symbol=trading_pair,
                side='SELL',
                type='MARKET',
                quantity=order_quantity
            )
            position_active = True
            position_type = 'short'
            position_entry_price = last_candle_close


        if (last_candle_close < bb_lower) and (long_allowed == True):
            time.sleep(1)
            go_long = client.futures_create_order(
                symbol=trading_pair,
                side='BUY',
                type='MARKET',
                quantity=order_quantity
            )
            position_active = True
            position_type = 'long'
            position_entry_price = last_candle_close

#fullfil and close positions when successful
    if position_active == True:
        if position_type == 'long':
            if last_candle_close >= bb_ma_rounded:
                close_long = client.futures_create_order(
                    symbol=trading_pair,
                    side='SELL',
                    type='MARKET',
                    quantity=order_quantity,
                )
                position_active = False
                total_trade_count = total_trade_count+1
                lastlongfail = False

        if position_type == 'short':
            if last_candle_close <= bb_ma_rounded:
                close_short = client.futures_create_order(
                    symbol=trading_pair,
                    side='BUY',
                    type='MARKET',
                    quantity=order_quantity,
                )
                position_active = False
                total_trade_count = total_trade_count+1
                lastshortfail = False

#trigger dynamically calculated stop loss

        if last_candle_close >= (position_entry_price*stop_loss_tolerance):
            if position_type == 'short':
                close_short = client.futures_create_order(
                    symbol=trading_pair,
                    side='BUY',
                    type='MARKET',
                    quantity=order_quantity,
                )
                position_active = False
                bad_trade_count = bad_trade_count+1
                bad_trade_from_stoploss = bad_trade_from_stoploss + 1
                lastshortfail = True

        if last_candle_close <= (position_entry_price/stop_loss_tolerance):
            if position_type == 'long':
                close_long = client.futures_create_order(
                    symbol=trading_pair,
                    side='SELL',
                    type='MARKET',
                    quantity=order_quantity,
                )
                position_active = False
                bad_trade_count = bad_trade_count + 1
                bad_trade_from_stoploss = bad_trade_from_stoploss + 1
                lastlongfail = True

        # when MA is unvaroable for mean reversion due to sideways movement, close the position
        if position_entry_price <= bb_ma_rounded:
            if position_type == 'short':
                close_short = client.futures_create_order(
                    symbol=trading_pair,
                    side='BUY',
                    type='MARKET',
                    quantity=order_quantity,
                )
                position_active = False
                bad_trade_count = bad_trade_count+1
                bad_trade_from_mean = bad_trade_from_mean + 1
                lastshortfail = True



        if position_entry_price >= bb_ma_rounded:
            if position_type == 'long':
                close_long = client.futures_create_order(
                    symbol=trading_pair,
                    side='SELL',
                    type='MARKET',
                    quantity=order_quantity,
                )
                position_active = False
                bad_trade_count = bad_trade_count + 1
                bad_trade_from_mean = bad_trade_from_mean+1
                lastlongfail = True

#print data in console
    if position_active:
        print('current position is a: '+position_type)
        print('current position entry price: '+str(position_entry_price))

        if position_type == 'short':
            print('stop loss set at: '+str(position_entry_price*stop_loss_tolerance))

        if position_type == 'long':
            print('stop loss set at: ' + str(position_entry_price / stop_loss_tolerance))

    else:
        print('no position is active')

    print('BOT 1')
    print('total trades made: '+str(total_trade_count))
    print('good trades made: '+str(total_trade_count-bad_trade_count))
    print('bad trades made: ' + str(bad_trade_count))
    print('bad trades from stop loss: '+str(bad_trade_from_stoploss))
    print('bad trades from entry price = mean: '+str(bad_trade_from_mean))


###### Variables and functions for 2 more instances of the bot######

global trading_pair2
global bb_range2
bb_range2 = 20
global bb_std_mult2
bb_std_mult2 = 2



def getpricedata2():
    global trading_pair2
    klines = client.get_historical_klines(trading_pair2, Client.KLINE_INTERVAL_1MINUTE, "20 minutes ago UTC")
    global price_df
    price_df = pd.DataFrame(klines, columns=['open_time','open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol','is_best_match'])


    del price_df['open_time']
    del price_df['open']
    #del price_df['high']
    #del price_df['low']
    del price_df['volume']
    del price_df['close_time']
    del price_df['qav']
    del price_df['num_trades']
    del price_df['taker_base_vol']
    del price_df['taker_quote_vol']
    del price_df['is_best_match']

    global bb_range2
    global bb_std_mult2

    global bb_ma2
    global bb_std2
    global bb_upper2
    global bb_lower2
    global last_candle_close2
    global last_candle_low
    global last_candle_high2

    price_df['MA'] = price_df['close'].rolling(window=bb_range2).mean()
    price_df['STD_DEV'] = price_df['close'].rolling(window=bb_range2).std()

    #print(price_df)
    print(len(price_df.index)-1)
    bb_ma2 = float(price_df.iloc[len(price_df.index)-1]['MA'])
    bb_std2 = float(price_df.iloc[len(price_df.index)-1]['STD_DEV'])
    bb_upper2 = bb_ma2 + (bb_std_mult2 * bb_std2)
    bb_lower2 = bb_ma2 - (bb_std_mult2 * bb_std2)
    last_candle_close2 = float(price_df.iloc[len(price_df.index)-1]['close'])
    last_candle_high2 = float(price_df.iloc[len(price_df.index)-1]['high'])
    last_candle_low = float(price_df.iloc[len(price_df.index)-1]['low'])

    #print(price_df)
    print(trading_pair2)
    print('moving average: '+str(bb_ma2))
    #print('std dev: '+str(bb_std2))
    print('upper BB: '+str(bb_upper2))
    print('lower BB: '+str(bb_lower2))
    print('last price: '+str(last_candle_close2))
    #print(last_candle_high2)
    #print(last_candle_low)


global position_active2
position_active2 = False
global position_type2
position_type2 = ''
global position_entry_price2
position_entry_price2 = 0
global order_quantity2
global stop_loss_tolerance2
stop_loss_tolerance2 = 0
global bad_trade_count2
bad_trade_count2 = 0
global total_trade_count2
total_trade_count2 = 0
global lastshortfail2
lastshortfail2 = False
global lastlongfail2
lastlongfail2 = False
global long_allowed2
long_allowed2 = True
global short_allowed2
short_allowed2 = True


def run_bot2():
    global trading_pair2
    global bb_ma2
    global last_candle_close2
    global position_active2
    global bb_lower2
    global bb_upper2
    global position_type2
    global order_quantity2
    global stop_loss_tolerance2
    global position_entry_price2
    global bad_trade_count2
    global total_trade_count2
    global lastshortfail2
    global lastlongfail2
    global long_allowed2
    global short_allowed2

    #print(trading_pair2)
    #print(bb_ma2)
    bb_ma2_rounded = round(bb_ma2, 5)
    last_candle_close2_rounded = round(last_candle_close2, 5)

    stop_loss_tolerance2 = ((bb_upper2-bb_ma2)/bb_upper2)+1
    print('dynamic stop loss tolerance: '+str(stop_loss_tolerance2))

    if position_active2 == False:

        if lastshortfail2 == True:
            if last_candle_close2 >= bb_upper2:
                short_allowed2 = False
            else:
                short_allowed2 = True

        if lastlongfail2 == True:
            if last_candle_close2 <= bb_lower2:
                long_allowed2 = False
            else:
                long_allowed2 = True

        if (last_candle_close2 > bb_upper2) and (short_allowed2 == True):
            time.sleep(1)
            go_short = client.futures_create_order(
                symbol=trading_pair2,
                side='SELL',
                type='MARKET',
                quantity=order_quantity2
            )
            position_active2 = True
            position_type2 = 'short'
            position_entry_price2 = last_candle_close2


        if (last_candle_close2 < bb_lower2) and (long_allowed2 == True):
            time.sleep(1)
            go_long = client.futures_create_order(
                symbol=trading_pair2,
                side='BUY',
                type='MARKET',
                quantity=order_quantity2
            )
            position_active2 = True
            position_type2 = 'long'
            position_entry_price2 = last_candle_close2


    if position_active2 == True:
        if position_type2 == 'long':
            if last_candle_close2 >= bb_ma2_rounded:
                close_long = client.futures_create_order(
                    symbol=trading_pair2,
                    side='SELL',
                    type='MARKET',
                    quantity=order_quantity2,
                )
                position_active2 = False
                total_trade_count2 = total_trade_count2+1
                lastlongfail2 = False

        if position_type2 == 'short':
            if last_candle_close2 <= bb_ma2_rounded:
                close_short = client.futures_create_order(
                    symbol=trading_pair2,
                    side='BUY',
                    type='MARKET',
                    quantity=order_quantity2,
                )
                position_active2 = False
                total_trade_count2 = total_trade_count2+1
                lastshortfail2 = False

        if last_candle_close2 >= (position_entry_price2*stop_loss_tolerance2):
            if position_type2 == 'short':
                close_short = client.futures_create_order(
                    symbol=trading_pair2,
                    side='BUY',
                    type='MARKET',
                    quantity=order_quantity2,
                )
                position_active2 = False
                bad_trade_count2 = bad_trade_count2+1
                lastshortfail2 = True

        if last_candle_close2 <= (position_entry_price2/stop_loss_tolerance2):
            if position_type2 == 'long':
                close_long = client.futures_create_order(
                    symbol=trading_pair2,
                    side='SELL',
                    type='MARKET',
                    quantity=order_quantity2,
                )
                position_active2 = False
                bad_trade_count2 = bad_trade_count2 + 1
                lastlongfail2 = True


        if position_entry_price2 <= bb_ma2_rounded:
            if position_type2 == 'short':
                close_short = client.futures_create_order(
                    symbol=trading_pair2,
                    side='BUY',
                    type='MARKET',
                    quantity=order_quantity2,
                )
                position_active2 = False
                bad_trade_count2 = bad_trade_count2+1
                lastshortfail2 = True


        if position_entry_price2 >= bb_ma2_rounded:
            if position_type2 == 'long':
                close_long = client.futures_create_order(
                    symbol=trading_pair2,
                    side='SELL',
                    type='MARKET',
                    quantity=order_quantity2,
                )
                position_active2 = False
                bad_trade_count2 = bad_trade_count2 + 1
                lastlongfail2 = True


    if position_active2:
        print('current position is a: '+position_type2)
        print('current position entry price: '+str(position_entry_price2))

        if position_type2 == 'short':
            print('stop loss set at: '+str(position_entry_price2*stop_loss_tolerance2))

        if position_type2 == 'long':
            print('stop loss set at: ' + str(position_entry_price2 / stop_loss_tolerance2))

    else:
        print('no position is active')

    print('BOT 2, SLEEP 1')
    print('total trades made: '+str(total_trade_count2))
    print('bad trades made: '+str(bad_trade_count2))
    print('good trades made: '+str(total_trade_count2-bad_trade_count2))


global trading_pair3
global bb_range3
bb_range3 = 20
global bb_std_mult3
bb_std_mult3 = 2

def getpricedata3():
    global trading_pair3
    klines = client.get_historical_klines(trading_pair3, Client.KLINE_INTERVAL_1MINUTE, "20 minutes ago UTC")
    global price_df
    price_df = pd.DataFrame(klines, columns=['open_time','open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol','is_best_match'])


    del price_df['open_time']
    del price_df['open']
    #del price_df['high']
    #del price_df['low']
    del price_df['volume']
    del price_df['close_time']
    del price_df['qav']
    del price_df['num_trades']
    del price_df['taker_base_vol']
    del price_df['taker_quote_vol']
    del price_df['is_best_match']

    global bb_range3
    global bb_std_mult3

    global bb_ma3
    global bb_std3
    global bb_upper3
    global bb_lower3
    global last_candle_close3
    global last_candle_low
    global last_candle_high3

    price_df['MA'] = price_df['close'].rolling(window=bb_range3).mean()
    price_df['STD_DEV'] = price_df['close'].rolling(window=bb_range3).std()

    #print(price_df)
    print(len(price_df.index)-1)
    bb_ma3 = float(price_df.iloc[len(price_df.index)-1]['MA'])
    bb_std3 = float(price_df.iloc[len(price_df.index)-1]['STD_DEV'])
    bb_upper3 = bb_ma3 + (bb_std_mult3 * bb_std3)
    bb_lower3 = bb_ma3 - (bb_std_mult3 * bb_std3)
    last_candle_close3 = float(price_df.iloc[len(price_df.index)-1]['close'])
    last_candle_high3 = float(price_df.iloc[len(price_df.index)-1]['high'])
    last_candle_low = float(price_df.iloc[len(price_df.index)-1]['low'])

    #print(price_df)
    print(trading_pair3)
    print('moving average: '+str(bb_ma3))
    #print('std dev: '+str(bb_std3))
    print('upper BB: '+str(bb_upper3))
    print('lower BB: '+str(bb_lower3))
    print('last price: '+str(last_candle_close3))
    #print(last_candle_high3)
    #print(last_candle_low)

global position_active3
position_active3 = False
global position_type3
position_type3 = ''
global position_entry_price3
position_entry_price3 = 0
global order_quantity3
global stop_loss_tolerance3
stop_loss_tolerance3 = 0
global bad_trade_count3
bad_trade_count3 = 0
global total_trade_count3
total_trade_count3 = 0
global lastshortfail3
lastshortfail3 = False
global lastlongfail3
lastlongfail3 = False
global long_allowed3
long_allowed3 = True
global short_allowed3
short_allowed3 = True

def run_bot3():
    global trading_pair3
    global bb_ma3
    global last_candle_close3
    global position_active3
    global bb_lower3
    global bb_upper3
    global position_type3
    global order_quantity3
    global stop_loss_tolerance3
    global position_entry_price3
    global bad_trade_count3
    global total_trade_count3
    global lastshortfail3
    global lastlongfail3
    global long_allowed3
    global short_allowed3

    #print(trading_pair3)
    #print(bb_ma3)
    bb_ma3_rounded = round(bb_ma3, 5)
    last_candle_close3_rounded = round(last_candle_close3, 5)

    stop_loss_tolerance3 = ((bb_upper3-bb_ma3)/bb_upper3)+1
    print('dynamic stop loss tolerance: '+str(stop_loss_tolerance3))

    if position_active3 == False:

        if lastshortfail3 == True:
            if last_candle_close3 >= bb_upper3:
                short_allowed3 = False
            else:
                short_allowed3 = True

        if lastlongfail3 == True:
            if last_candle_close3 <= bb_lower3:
                long_allowed3 = False
            else:
                long_allowed3 = True

        if (last_candle_close3 > bb_upper3) and (short_allowed3 == True):
            time.sleep(2)
            go_short = client.futures_create_order(
                symbol=trading_pair3,
                side='SELL',
                type='MARKET',
                quantity=order_quantity3
            )
            position_active3 = True
            position_type3 = 'short'
            position_entry_price3 = last_candle_close3


        if (last_candle_close3 < bb_lower3) and (long_allowed3 == True):
            time.sleep(2)
            go_long = client.futures_create_order(
                symbol=trading_pair3,
                side='BUY',
                type='MARKET',
                quantity=order_quantity3
            )
            position_active3 = True
            position_type3 = 'long'
            position_entry_price3 = last_candle_close3


    if position_active3 == True:
        if position_type3 == 'long':
            if last_candle_close3 >= bb_ma3_rounded:
                close_long = client.futures_create_order(
                    symbol=trading_pair3,
                    side='SELL',
                    type='MARKET',
                    quantity=order_quantity3,
                )
                position_active3 = False
                total_trade_count3 = total_trade_count3+1
                lastlongfail3 = False

        if position_type3 == 'short':
            if last_candle_close3 <= bb_ma3_rounded:
                close_short = client.futures_create_order(
                    symbol=trading_pair3,
                    side='BUY',
                    type='MARKET',
                    quantity=order_quantity3,
                )
                position_active3 = False
                total_trade_count3 = total_trade_count3+1
                lastshortfail3 = False

        if last_candle_close3 >= (position_entry_price3*stop_loss_tolerance3):
            if position_type3 == 'short':
                close_short = client.futures_create_order(
                    symbol=trading_pair3,
                    side='BUY',
                    type='MARKET',
                    quantity=order_quantity3,
                )
                position_active3 = False
                bad_trade_count3 = bad_trade_count3+1
                lastshortfail3 = True

        if last_candle_close3 <= (position_entry_price3/stop_loss_tolerance3):
            if position_type3 == 'long':
                close_long = client.futures_create_order(
                    symbol=trading_pair3,
                    side='SELL',
                    type='MARKET',
                    quantity=order_quantity3,
                )
                position_active3 = False
                bad_trade_count3 = bad_trade_count3 + 1
                lastlongfail3 = True


        if position_entry_price3 <= bb_ma3_rounded:
            if position_type3 == 'short':
                close_short = client.futures_create_order(
                    symbol=trading_pair3,
                    side='BUY',
                    type='MARKET',
                    quantity=order_quantity3,
                )
                position_active3 = False
                bad_trade_count3 = bad_trade_count3+1
                lastshortfail3 = True


        if position_entry_price3 >= bb_ma3_rounded:
            if position_type3 == 'long':
                close_long = client.futures_create_order(
                    symbol=trading_pair3,
                    side='SELL',
                    type='MARKET',
                    quantity=order_quantity3,
                )
                position_active3 = False
                bad_trade_count3 = bad_trade_count3 + 1
                lastlongfail3 = True


    if position_active3:
        print('current position is a: '+position_type3)
        print('current position entry price: '+str(position_entry_price3))

        if position_type3 == 'short':
            print('stop loss set at: '+str(position_entry_price3*stop_loss_tolerance3))

        if position_type3 == 'long':
            print('stop loss set at: ' + str(position_entry_price3 / stop_loss_tolerance3))

    else:
        print('no position is active')

    print('BOT 3, SLEEP 2')
    print('total trades made: '+str(total_trade_count3))
    print('bad trades made: '+str(bad_trade_count3))
    print('good trades made: '+str(total_trade_count3-bad_trade_count3))



while True:
    tic = time.perf_counter()
    trading_pair = 'ETHUSDT'
    order_quantity = 0.03
    getpricedata()
    run_bot()

#time delays as to not exceed the 1200 requests per minute limit for binance api
    #time.sleep(0.1)

   # trading_pair2 = 'ETHUSDT'
    #order_quantity2 = 0.03
    #getpricedata2()
    #run_bot2()

  #  time.sleep(0.1)

    #trading_pair3 = 'ETHUSDT'
    #order_quantity3 = 0.03
    #getpricedata3()
    #run_bot3()

 #   time.sleep(0.1)

    toc = time.perf_counter()

    print(f"Bot Run in {toc - tic:0.4f} seconds")




