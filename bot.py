import time
from collections import deque as queue
import socket
import json


class Bot:

    def __init__(self, test=False):
        """
        Initialization of bot class.
        :param test:
        """
        print("=-=-= Starting trading bot! =-=-=\n")
        # General attributes
        self.team_name = "TEAMSTOCKERS"
        self.test_mode = test
        self.order_id = 0

        # Bond trading attributes
        self.fair_value_threshold = 1
        self.open_bonds = set()

        # ADR Arbitrage
        self.adr_queue = queue([], 10)
        self.open_adrs = set()
        self.open_adr_converts = {}
        self.adr_count = 0
        self.adr_z_count = 0
        self.adr_left = {}

        # ETF Arbitrage
        self.etf_queues = {"GS": queue([], 10),
                           "MS": queue([], 10),
                           "WFC": queue([], 10)}
        self.etf_prices = {}
        self.open_etfs = set()

        if test:
            print("=-=-= Test mode activated. Getting hello from exchange. =-=-= \n")
            self.test()
        else:
            self.launch()

    def test(self):
        self.make_connection("test-exch-", 25000)
        print("=-=-= Connection made! =-=-=")
        self.hello()
        self.check_market()

    def launch(self):
        self.make_connection("production", 25000)
        self.hello()
        self.check_market()

    def hello(self):
        self.send_action({"type": "hello", "team": "TEAMSTOCKERS"})
        print("Hello received from server: ", self.read_market())

    def check_market(self):
        """
        self.send_action({"type": "add", "order_id": self.order_id,
                          "symbol": "BOND", "dir": "BUY", "price": 1000 - self.fair_value_threshold,
                          "size": 50})
        self.open_bonds.add(self.order_id)
        self.order_id += 1

        self.send_action({"type": "add", "order_id": self.order_id,
                          "symbol": "BOND", "dir": "SELL", "price": 1000 + self.fair_value_threshold,
                          "size": 50})
        self.open_bonds.add(self.order_id)
        self.order_id += 1
        """
        while True:
            data = self.read_market()
            """
            # Fair-value operations
            if data["type"] == "fill" and data["order_id"] in self.open_bonds:
                if data["dir"] == "BUY":
                    self.send_action({"type": "add", "order_id": self.order_id,
                                      "symbol": "BOND", "dir": "BUY", "price": 1000 - self.fair_value_threshold,
                                      "size": data["size"]})
                    self.open_bonds.add(self.order_id)
                    self.order_id += 1
                elif data["dir"] == "SELL":
                    self.send_action({"type": "add", "order_id": self.order_id,
                                      "symbol": "BOND", "dir": "SELL", "price": 1000 + self.fair_value_threshold,
                                      "size": data["size"]})
                    self.open_bonds.add(self.order_id)
                    self.order_id += 1
            elif data["type"] == "out" and data["order_id"] in self.open_bonds:
                self.open_bonds.remove(data["order_id"])
            """
            # ADR Arbitrage
            if data["type"] == "trade" and data["symbol"] == "VALBZ":
                self.adr_queue.append(data["price"])
                self.adr_price = sum(self.adr_queue) // len(self.adr_queue)

                if not len(self.open_adrs) or abs(self.adr_price - self.adr_order_price) >= 5:
                    self.adr_order_price = self.adr_price
                    for open_order in self.open_adrs:
                        self.send_action({"type": "cancel", "order_id": open_order})

                    self.send_action({"type": "add", "order_id": self.order_id,
                                      "symbol": "VALE", "dir": "BUY", "price": self.adr_price - 10,
                                      "size": 5})
                    self.open_adrs.add(self.order_id)
                    self.order_id += 1

                    self.send_action({"type": "add", "order_id": self.order_id,
                                      "symbol": "VALE", "dir": "SELL", "price": self.adr_price + 10,
                                      "size": 5})
                    self.open_adrs.add(self.order_id)
                    self.order_id += 1

            if data["type"] == "fill" and data["order_id"] in self.open_adrs:
                if data["dir"] == "BUY" and data["symbol"] == "VALE":
                    self.send_action({"type": "add", "order_id": self.order_id,
                                      "symbol": "VALE", "dir": "BUY", "price": self.adr_price - 10,
                                      "size": data["size"]})
                    self.open_adrs.add(self.order_id)
                    self.order_id += 1
                    self.adr_count += data["size"]

                    self.send_action({"type": "add", "order_id": self.order_id,
                                      "symbol": "VALBZ", "dir": "SELL", "price": self.adr_price + 10,
                                      "size": data["size"]})
                    self.open_adrs.add(self.order_id)
                    self.order_id += 1

                elif data["dir"] == "BUY" and data["symbol"] == "VALBZ":
                    self.adr_z_count += data["size"]

                elif data["dir"] == "SELL" and data["symbol"] == "VALE":
                    self.send_action({"type": "add", "order_id": self.order_id,
                                      "symbol": "VALE", "dir": "SELL", "price": self.adr_price + 10,
                                      "size": data["size"]})
                    self.open_adrs.add(self.order_id)
                    self.order_id += 1
                    self.adr_count -= data["size"]

                    self.send_action({"type": "add", "order_id": self.order_id,
                                      "symbol": "VALBZ", "dir": "BUY", "price": self.adr_price - 10,
                                      "size": data["size"]})
                    self.open_adrs.add(self.order_id)
                    self.order_id += 1

                if self.adr_count == 10 and self.adr_z_count == -10:
                    self.send_action({"type": "convert", "order_id": self.order_id,
                                      "symbol": "VALE", "dir": "SELL", "price": self.adr_price,
                                      "size": data["size"]})
                    self.open_adr_converts[self.order_id] = "SELL"
                    self.order_id += 1

                if self.adr_count == -10 and self.adr_z_count == 10:
                    self.send_action({"type": "convert", "order_id": self.order_id,
                                      "symbol": "VALE", "dir": "BUY", "price": self.adr_price,
                                      "size": data["size"]})
                    self.open_adr_converts[self.order_id] = "BUY"
                    self.order_id += 1

            if data["type"] == "fill" and data["order_id"] in self.open_adr_converts:
                if self.open_adr_converts[data["order_id"]] == "BUY":
                    self.adr_count += data["size"]
                    self.adr_z_count -= data["size"]
                else:
                    self.adr_count -= data["size"]
                    self.adr_z_count += data["size"]

            elif data["type"] == "out" and data["order_id"] in self.open_adrs:
                self.open_adrs.remove(data["order_id"])

            elif data["type"] == "out" and data["order_id"] in self.adr_left:
                self.send_action({"type": ["BUY", "SELL"]})
            """
            # ETF Arbitrage
            if data["type"] == "trade" and data["symbol"] in self.etf_queues:
                stock = data["symbol"]
                self.etf_queues[stock].append(data["price"])
                self.etf_prices[stock] = sum(self.etf_queues[stock]) // len(self.etf_queues[stock])
                if len(self.etf_prices) == 3:
                    self.xlf_price = (3000 + 2 * self.etf_prices["GS"] +
                        3 * self.etf_prices["MS"] + 2 * self.etf_prices["WFC"]) // 10
                    if not len(self.open_etfs) or \
                        abs(self.xlf_price - self.etf_order_price) >= 10:
                        self.etf_order_price = self.xlf_price
                        for open_order in self.open_etfs:
                            self.send_action({"type": "cancel", "order_id": open_order})

                        self.send_action({"type": "add", "order_id": self.order_id,
                                          "symbol": "XLF", "dir": "BUY", "price": self.xlf_price - 30,
                                          "size": 50})
                        self.open_etfs.add(self.order_id)
                        self.order_id += 1

                        self.send_action({"type": "add", "order_id": self.order_id,
                                          "symbol": "XLF", "dir": "SELL", "price": self.xlf_price + 30,
                                          "size": 50})
                        self.open_etfs.add(self.order_id)
                        self.order_id += 1

            if data["type"] == "fill" and data["order_id"] in self.open_etfs:
                if data["dir"] == "BUY":
                    self.send_action({"type": "add", "order_id": self.order_id,
                                      "symbol": "XLF", "dir": "BUY", "price": self.xlf_price - 30,
                                      "size": data["size"]})
                    self.open_etfs.add(self.order_id)
                    self.order_id += 1
                elif data["dir"] == "SELL":
                    self.send_action({"type": "add", "order_id": self.order_id,
                                      "symbol": "XLF", "dir": "SELL", "price": self.xlf_price + 30,
                                      "size": data["size"]})
                    self.open_etfs.add(self.order_id)
                    self.order_id += 1
            elif data["type"] == "out" and data["order_id"] in self.open_etfs:
                self.open_etfs.remove(data["order_id"])
            """

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
            print("Expected JSON but got {}.".format(data))


Bot(True)
