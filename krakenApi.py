import requests
import time
import base64
import hashlib
import hmac
import urllib.parse
import numpy as np
from pytz import timezone
import matplotlib.pyplot as plt
from matplotlib import cm
import datetime as dt
import json
from pprint import pprint as pp

class KrakenApi(object):

    def __init__(self):

        with open('kraken.key', 'r') as f:
            self.key = f.readline().strip()
            self.secret = f.readline().strip()

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Kraken REST API'
        })

        self.response = None

        return

    def api_public(self, method, data={}, timeout=None):
        return requests.post(f'https://api.kraken.com/0/public/{method}', data=data, timeout=timeout).json()

    def api_private(self, method, data={}, timeout=None):
        data['nonce'] = self._nonce()

        headers = {
            'API-Key': self.key,
            'API-Sign': self._sign(data, f'/0/private/{method}')
        }

        return requests.post(f'https://api.kraken.com/0/private/{method}', data=data, headers=headers,
                             timeout=timeout).json()

    def _sign(self, data, urlpath):
        postdata = urllib.parse.urlencode(data)
        encoded = (str(data['nonce']) + postdata).encode()
        message = urlpath.encode() + hashlib.sha256(encoded).digest()
        signature = hmac.new(base64.b64decode(self.secret), message, hashlib.sha512)
        sigdigest = base64.b64encode(signature.digest())
        return sigdigest.decode()

    def _nonce(self):
        return int(1000 * time.time())

    def get_server_time(self):
        return self.api_public('Time')['result']

    def get_system_status(self):
        return self.api_public('SystemStatus')['result']

    def get_asset_pairs(self):
        return list(filter(lambda x: x.endswith('USD'), [*self.api_public('AssetPairs')['result'].keys()]))

    def get_available_assets(self):
        return [*self.api_public('Assets')['result'].keys()]

    def get_ticker_information(self, pair):
        return self.api_public('Ticker', {'pair': pair})['result'][pair]

    def get_recent_trades(self, pair, since):
        return self.api_public('Trades', {'pair': pair, 'since': since})['result'][pair]

    def get_depth(self, pair, count):
        return self.api_public('Depth', {'pair': pair, 'count': count})['result'][pair]

    def get_best_ask(self, pair):
        return self.api_public('Depth', {'pair': pair, 'count': '1'})['result'][pair]['asks'][0][0]

    def get_best_bid(self, pair):
        return self.api_public('Depth', {'pair': pair, 'count': '1'})['result'][pair]['bids'][0][0]

    def get_ohlc_data(self, pair, interval, since):
        return self.api_public('OHLC', {'pair': pair, 'interval': interval, 'since': since})['result']

    def get_spread(self, pair, since):
        return self.api_public('Spread', {'pair': pair, 'interval': since})['result']

    def get_account_balance(self):
        return self.api_private('Balance')['result']

    def get_open_orders(self):
        return self.api_private('OpenOrders')['result']

    def get_closed_orders(self):
        return self.api_private('ClosedOrders')['result']

    def get_trade_volume(self, pair):
        return self.api_private('TradeVolume', {'pair': pair})['result']

    def cancel_open_order(self, txid):
        return self.api_private('CancelOrder', {'txid': txid})['result']

    def cancel_all_open_orders(self):
        return self.api_private('CancelAll')['result']

    def analyze_market_data(self, pair, interval, since):
        ohlc = self.get_ohlc_data(pair, interval, time.time() - since)
        ohlc_np = np.array(ohlc[pair], dtype=float)

        recent_close = ohlc_np[-1, 4]
        ohlc_close = ohlc_np[:, 4]
        ohlc_time = ohlc_np[:, 0]
        ohlc_volume = ohlc_np[:, 6]
        avg_close = np.sum(ohlc_close) / len(ohlc_np)

        points_above_recent_close = 0
        points_below_recent_close = 0

        for price in ohlc_close:
            if price < recent_close:
                points_below_recent_close += 1
            else:
                points_above_recent_close += 1

        print(f'recent={"{:.2f}".format(recent_close)} average={"{:.2f}".format(avg_close)}')
        print(f'below={points_below_recent_close} above={points_above_recent_close}')

        self.plot_stuff(pair, recent_close, ohlc_close, ohlc_time, ohlc_volume)

        return (recent_close < avg_close) and (points_below_recent_close < points_above_recent_close)

    def add_order(self, pair, amount_in, desired_percentage_gain):
        buy_price = float(self.api_public('Depth', {'pair': pair, 'count': '1'})['result'][pair]['bids'][0][0])
        shares = amount_in / buy_price
        sell_price = buy_price * desired_percentage_gain

        payload = {'pair': pair,
                   'type': 'buy',
                   'ordertype': 'limit',
                   'price': '{:.2f}'.format(buy_price),
                   'volume': '{:.2f}'.format(shares),
                   'close[ordertype]': 'limit',
                   'close[price]': '{:.2f}'.format(sell_price),
                   'close[pair]': pair,
                   'close[type]': 'sell',
                   'close[volume]': '{:.2f}'.format(shares)}

        return self.api_private('AddOrder', payload)['result']['descr']

    def start(self):
        interval = 1
        since = 43200

        assets_that_i_like = ['AAVEUSD', 'ADAUSD', 'ALGOUSD', 'ATOMUSD', 'BALUSD', 'BCHUSD', 'COMPUSD', 'DOTUSD',
                              'EOSUSD', 'FILUSD', 'FLOWUSD', 'LINKUSD', 'OMGUSD', 'REPV2USD', 'UNIUSD', 'XETHZUSD',
                              'XLTCZUSD', 'XREPZUSD', 'XXBTZUSD', 'XXLMZUSD', 'XXRPZUSD', 'XZECZUSD']

        for asset in assets_that_i_like:
            pp(f'\n[{asset}] [{interval}m] [{since}s]')
            pp(f'Analysis -> {"GO IN BABY" if self.analyze_market_data(asset, interval, since) else "chill for now"}')


def plot_stuff(pair, recent_close, ohlc_close, ohlc_time, ohlc_volume):

    pastel = cm.get_cmap('Pastel1')

    local_time = np.array(
        [dt.datetime.fromtimestamp(t, timezone('US/Central')).strftime('%H:%M') for t in ohlc_time])
    fig, [ax1, ax2] = plt.subplots(2, 1)
    ax1.set(xlabel='timestamp', ylabel='price', title=pair)
    ax1.axhline(recent_close, color='black', lw='1')

    ax1.plot(local_time, ohlc_close, color='black')
    ax1.fill_between(local_time, recent_close, ohlc_close, where=recent_close < ohlc_close, facecolor=pastel(0.1))
    ax1.fill_between(local_time, recent_close, ohlc_close, where=recent_close > ohlc_close, facecolor=pastel(0.2))
    ax2.set(xlabel='timestamp', ylabel='volume')
    ax2.bar(local_time, ohlc_volume, color='black')

    fig.autofmt_xdate()

    plt.show()