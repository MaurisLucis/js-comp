# Trading Bot developed for the Jane Street Electronic Trading Competition at UC Berkeley.
# Developed by Nick Mecklenburg and Cjache Kang on February 9th, 2019.
#
# Please do not copy or otherwise distribute this code, especially for another
# Jane Street ETC competition. I've thrown a couple wrenches into the bot to
# throttle its functionality. Don't plagiarize!

from collections import deque as queue
import socket
import json
from time import sleep


class Bot:

    def __init__(self, test=False):
        """
        Initialization of bot class. If TEST parameter is True, bot connects to and runs on
        Jane Street's test-exchange server. If TEST parameter is False, runs on production market.
        :param test:

        For reference, the market consists of the following stocks:
        BOND  -- Bond stock, fair value known
        VALBZ -- regular stock
        VALE  -- ADR of VALBZ
        GS    -- XLF component
        MS    -- XLF component
        WFC   -- XLF component
        XLF   -- ETF of GS, MS, WFC, and BOND
        """
        print("=-=-= Starting trading bot! =-=-=\n")
        # General attributes
        self.team_name = "TEAMSTOCKERS"
        self.test_mode = test
        self.order_id = 0

        # -- Bond trading attributes -- #
        # Specifies minimum difference from BOND's fair
        # value that we're willing to work with.
        # If we're selling, we'll sell at >= bond's fair value (1000) + threshold.
        # If we're buying, we'll buy at <= bond's fair value (1000) - threshold.
        self.bond_threshold = 1
        # Tracks open bond orders we've sent to the market.
        self.open_bonds = set()

        # -- ADR Arbitrage -- #
        # Last 10 prices VALBZ was traded at
        self.adr_queue = queue([], 10)
        # Tracks open ADR-related orders we've sent to the market.
        self.open_adrs = set()
        # Tracks open ADR conversion orders we've sent to the market.
        self.open_adr_converts = {}
        # Quantity of VALE owned.
        self.adr_count = 0
        # Quantity of VALBZ owned.
        self.adr_z_count = 0

        # -- ETF Arbitrage -- #
        # Dictionary mapping XLF components to queues representing their prices;
        # each queue tracks the last 10 prices at which its corresponding stock was traded at.
        self.etf_queues = {"GS": queue([], 10),
                           "MS": queue([], 10),
                           "WFC": queue([], 10)}
        # Dictionary mapping XLF component names to their average prices.
        self.etf_prices = {}
        # Tracks open ETF-related orders we've sent to the market.
        self.open_etfs = set()
        # Quantity of XLF stocks owned.
        self.etf_count = 0
        # List of [GS quantity, MS quantity, WFC quantity]
        self.ind_count = [0] * 3

        if test:
            print("=-=-= Test mode activated. Getting hello from exchange. =-=-= \n")
            self.test()
        else:
            self.launch()

    def test(self):
        """
        Function for testing new market strategies on
        Jane Street's provided test server.
        :return:
        """
        self.make_connection("test-exch-", 25000)
        print("=-=-= Connection made! =-=-=")
        self.hello()
        self.check_market()

    def launch(self):
        """
        Function for running market strategies on
        Jane Street's production server to be scored
        for the competition.
        :return:
        """
        self.make_connection("production", 25000)
        self.hello()
        self.check_market()

    def hello(self):
        """
        Jane Street's server requires a hello message to be
        exchanged upon successfully connecting.
        :return:
        """
        self.send_action({"type": "hello", "team": "TEAMSTOCKERS"})
        print("Hello received from server: ", self.read_market())

    def check_market(self):
        """
        Central function that runs each strategy on the data
        received from the market.
        :return:
        """
        self.bond_initialize()
        while True:
            data = self.read_market()
            self.bond_trading(data)
            self.adr_trading(data)
            self.etf_trading(data)
            # Pause so Bot doesn't get kicked from Jane Street's
            # exchange for overloading it with requests.
            sleep(1)

    def adr_trading(self, data):
        # First check for any VALBZ trades, so that we can update its estimated price
        if data["type"] == "trade" and data["symbol"] == "VALBZ":
            self.adr_queue.append(data["price"])
            self.adr_price = sum(self.adr_queue) // len(self.adr_queue)

            if not len(self.open_adrs) or abs(self.adr_price - self.adr_order_price) >= 5:
                self.adr_order_price = self.adr_price
                for open_order in self.open_adrs:
                    # The price at which we made our orders is now outdated, so
                    # cancel any outgoing orders requested based off of the info to cut losses.
                    self.send_action({"type": "cancel", "order_id": open_order})
                # Send out new ADR orders using updated price estimate
                self.send_action({"type": "add", "order_id": self.order_id,
                                  "symbol": "VALE", "dir": "BUY", "price": self.adr_price + 10,
                                  "size": 5})
                self.open_adrs.add(self.order_id)
                self.order_id += 1

                self.send_action({"type": "add", "order_id": self.order_id,
                                  "symbol": "VALE", "dir": "SELL", "price": self.adr_price - 10,
                                  "size": 5})
                self.open_adrs.add(self.order_id)
                self.order_id += 1

        if data["type"] == "fill" and data["order_id"] in self.open_adrs:
            if data["dir"] == "BUY":
                if data["symbol"] == "VALE":
                    # An ADR order was partially or fully filled. Since we want to have as
                    # many (profitable) orders out as possible, send out as many new orders
                    # as the amount that was just filled.
                    self.send_action({"type": "add", "order_id": self.order_id,
                                      "symbol": "VALE", "dir": "BUY", "price": self.adr_price + 10,
                                      "size": data["size"]})
                    self.open_adrs.add(self.order_id)
                    self.order_id += 1
                    self.adr_count += data["size"]

                    # Part of our attempt at hedging. For every VALE we buy, sell the same of VALBZ.
                    self.send_action({"type": "add", "order_id": self.order_id,
                                      "symbol": "VALBZ", "dir": "SELL", "price": self.adr_price - 10,
                                      "size": data["size"]})
                    self.open_adrs.add(self.order_id)
                    self.order_id += 1

                elif data["symbol"] == "VALBZ":
                    self.adr_z_count += data["size"]

            elif data["dir"] == "SELL":
                if data["symbol"] == "VALE":
                    # As before, refill ADR orders.
                    self.send_action({"type": "add", "order_id": self.order_id,
                                      "symbol": "VALE", "dir": "SELL", "price": self.adr_price - 10,
                                      "size": data["size"]})
                    self.open_adrs.add(self.order_id)
                    self.order_id += 1
                    self.adr_count -= data["size"]

                    # Hedge with VALBZ.
                    self.send_action({"type": "add", "order_id": self.order_id,
                                      "symbol": "VALBZ", "dir": "BUY", "price": self.adr_price + 10,
                                      "size": data["size"]})
                    self.open_adrs.add(self.order_id)
                    self.order_id += 1

            if self.adr_count == 10 and self.adr_z_count == -10:
                # Check to see if VAL and VALBZ are both maxed out and, if so, convert them.
                self.send_action({"type": "convert", "order_id": self.order_id,
                                  "symbol": "VALE", "dir": "SELL", "price": self.adr_price,
                                  "size": data["size"]})
                self.open_adr_converts[self.order_id] = "SELL"
                self.order_id += 1

            if self.adr_count == -10 and self.adr_z_count == 10:
                # VALE and VALBZ might have maxed out in the other direction, too.
                self.send_action({"type": "convert", "order_id": self.order_id,
                                  "symbol": "VALE", "dir": "BUY", "price": self.adr_price,
                                  "size": data["size"]})
                self.open_adr_converts[self.order_id] = "BUY"
                self.order_id += 1

        if data["type"] == "fill" and data["order_id"] in self.open_adr_converts:
            # After a conversion request has been successfully filled,
            # update the amounts of VALE and VALBZ stocks owned.
            if self.open_adr_converts[data["order_id"]] == "BUY":
                self.adr_count += data["size"]
                self.adr_z_count -= data["size"]
            else:
                self.adr_count -= data["size"]
                self.adr_z_count += data["size"]

        elif data["type"] == "out" and data["order_id"] in self.open_adrs:
            self.open_adrs.remove(data["order_id"])

    def bond_initialize(self):
        """
        Initialize our bond trading strategy. We know the price and
        what we'd like to trade it at, so start out with as many orders as possible.
        :return:
        """
        self.send_action({"type": "add", "order_id": self.order_id,
                          "symbol": "BOND", "dir": "BUY", "price": 1000 - self.bond_threshold,
                          "size": 50})
        self.open_bonds.add(self.order_id)
        self.order_id += 1

        self.send_action({"type": "add", "order_id": self.order_id,
                          "symbol": "BOND", "dir": "SELL", "price": 1000 + self.bond_threshold,
                          "size": 50})
        self.open_bonds.add(self.order_id)
        self.order_id += 1

    def bond_trading(self, data):
        """
        Using DATA, a JSON object of information sent over from the exchange,
        determine if we need to replenish bond buy/sell orders based on if they
        got filled.
        :param data:
        :return:
        """
        if data["type"] == "fill" and data["order_id"] in self.open_bonds:
            if data["dir"] == "BUY":
                self.send_action({"type": "add", "order_id": self.order_id,
                                  "symbol": "BOND", "dir": "BUY", "price": 1000 - self.bond_threshold,
                                  "size": data["size"]})
                self.open_bonds.add(self.order_id)
                self.order_id += 1
            elif data["dir"] == "SELL":
                self.send_action({"type": "add", "order_id": self.order_id,
                                  "symbol": "BOND", "dir": "SELL", "price": 1000 + self.bond_threshold,
                                  "size": data["size"]})
                self.open_bonds.add(self.order_id)
                self.order_id += 1
        elif data["type"] == "out" and data["order_id"] in self.open_bonds:
            self.open_bonds.remove(data["order_id"])

    def etf_trading(self, data):
        # Like with ADR arbitrage, check to see if any XLF components were traded
        # recently and use this information to update the component's price estimate.
        if data["type"] == "trade" and data["symbol"] in self.etf_queues:
            stock = data["symbol"]
            self.etf_queues[stock].append(data["price"])
            self.etf_prices[stock] = sum(self.etf_queues[stock]) // len(self.etf_queues[stock])
            # If we have pricing information about the three unknown XLF components,
            # we can start our trading.
            if len(self.etf_prices) == 3:
                self.xlf_price = (3000 + 2 * self.etf_prices["GS"] +
                                  3 * self.etf_prices["MS"] + 2 * self.etf_prices["WFC"]) // 10
                # If we haven't made any ETF trades yet or our pricing information is outdated,
                # send a new round of orders.
                if not len(self.open_etfs) or \
                        abs(self.xlf_price - self.etf_order_price) >= 10:
                    self.etf_order_price = self.xlf_price
                    for open_order in self.open_etfs:
                        self.send_action({"type": "cancel", "order_id": open_order})

                    self.send_action({"type": "add", "order_id": self.order_id,
                                      "symbol": "XLF", "dir": "BUY", "price": self.xlf_price - 25,
                                      "size": 50})
                    self.open_etfs.add(self.order_id)
                    self.order_id += 1

                    self.send_action({"type": "add", "order_id": self.order_id,
                                      "symbol": "XLF", "dir": "SELL", "price": self.xlf_price + 25,
                                      "size": 50})
                    self.open_etfs.add(self.order_id)
                    self.order_id += 1

        if data["type"] == "fill" and data["order_id"] in self.open_etfs:
            if data["dir"] == "BUY":
                if data["symbol"] == "XLF":
                    # Like before, replenish filled orders.
                    self.send_action({"type": "add", "order_id": self.order_id,
                                      "symbol": "XLF", "dir": "BUY", "price": self.xlf_price - 25,
                                      "size": data["size"]})
                    self.open_etfs.add(self.order_id)
                    self.etf_count += data["size"]
                    self.order_id += 1

                    self.hedge_etf("SELL", 1)
                elif data["symbol"] == "GS":
                    self.ind_count[0] -= data["size"]
                elif data["symbol"] == "MS":
                    self.ind_count[1] -= data["size"]
                elif data["symbol"] == "WFC":
                    self.ind_count[2] -= data["size"]

                # If we can convert our XLF stock into its components,
                # do it. We want to be able to work with as many XLF stocks
                # as possible.
                if self.etf_count >= 30 and self.ind_count[0] >= 6 and \
                    self.ind_count[1] >= 9 and self.ind_count[2] >= 6:
                    self.send_action({"type": "convert", "order_id": self.order_id,
                                  "symbol": "XLF", "dir": "SELL", "price": self.xlf_price + 25,
                                  "size": 30})

            elif data["dir"] == "SELL":
                if data["symbol"] == "XLF":
                    # Replenish filled orders.
                    self.send_action({"type": "add", "order_id": self.order_id,
                                      "symbol": "XLF", "dir": "SELL", "price": self.xlf_price + 25,
                                      "size": data["size"]})
                    self.open_etfs.add(self.order_id)
                    self.etf_count -= data["size"]
                    self.order_id += 1

                    self.hedge_etf("BUY", -1)
                elif data["symbol"] == "GS":
                    self.ind_count[0] += data["size"]
                elif data["symbol"] == "MS":
                    self.ind_count[1] += data["size"]
                elif data["symbol"] == "WFC":
                    self.ind_count[2] += data["size"]

                # Convert components into XLF to be sold if we can.
                if self.etf_count <= -30 and self.ind_count[0] <= -6 and \
                        self.ind_count[1] <= -9 and self.ind_count[2] <= -6:
                    self.send_action({"type": "convert", "order_id": self.order_id,
                                      "symbol": "XLF", "dir": "BUY", "price": self.xlf_price - 25,
                                      "size": 30})

        elif data["type"] == "out" and data["order_id"] in self.open_etfs:
            self.open_etfs.remove(data["order_id"])

    def hedge_etf(self, oper, fac):
        """
        For every XLF bought or sold, we want to try to hedge in the opposite direction.
        OPER specifies "BUY" or "SELL" and FAC specifies in what direction of the estimated value
        we should trade in.
        :param oper:
        :param fac:
        :return:
        """
        self.send_action({"type": "add", "order_id": self.order_id,
                          "symbol": "GS", "dir": oper, "price": self.etf_prices["GS"] - (30 * fac),
                          "size": 2})
        self.open_etfs.add(self.order_id)
        self.order_id += 1
        self.send_action({"type": "add", "order_id": self.order_id,
                          "symbol": "MS", "dir": oper, "price": self.etf_prices["MS"] - (30 * fac),
                          "size": 3})
        self.open_etfs.add(self.order_id)
        self.order_id += 1
        self.send_action({"type": "add", "order_id": self.order_id,
                          "symbol": "WFC", "dir": oper, "price": self.etf_prices["WFC"] - (30 * fac),
                          "size": 2})
        self.open_etfs.add(self.order_id)
        self.order_id += 1

    def make_connection(self, hostname, port):
        """
        Makes connection between the bot and the Jane Street trading server.
        Utilizes Python Socket library to connect to an address tuple, (HOSTNAME, PORT).
        If test mode is on, appends team_name to hostname to connect to test server.
        :param hostname:
        :param port:
        :return:
        """
        self.market = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.market.settimeout(5)
        addr = (hostname + self.team_name * self.test_mode, port)
        print(addr)
        self.market.connect(addr)
        self.stream = self.market.makefile('rw', 1)

    def send_action(self, action):
        """
        Send a valid ACTION to the server (e.g. hello, add, convert, cancel).
        ACTION should be a JSON formatted as specified by Jane Street.
        :param action:
        :return:
        """
        try:
            print("Entered {}".format(self.order_id))
            json.dump(action, self.stream)
            self.stream.write('\n')
        except ValueError:
            print("Invalid JSON string provided.")

    def read_market(self):
        """
        Returns JSON input from socket stream, if present.
        :return:
        """
        try:
            data = self.stream.readline()
            if data is None:
                return self.read_market()
            return json.loads(data)
        except json.JSONDecodeError:
            print("Expected JSON but encountered decoding error.")
            self.read_market()

Bot(True)
