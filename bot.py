import socket
import json
import time


class Bot:

    def __init__(self, test=False):
        """
        Initialization of bot class.
        :param test:
        """
        print("=-=-= Starting trading bot! =-=-=\n")
        self.team_name = "TEAMSTOCKERS"
        self.test_mode = test
        self.order_id = 0
        self.fair_value_threshold = 1
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
        # Fair-value operations
        while True:
            data = self.read_market()
            if data["type"] == "book" and data["symbol"] == "BOND":
                print("Found BOND in book")
                if "sell" in data:
                    print("Found sell")
                    for order in data["sell"]:
                        if order[0] <= 1000 - self.fair_value_threshold:
                            self.send_action({"type": "add", "order_id": self.order_id,
                                        "symbol":"BOND", "dir":"BUY", "price": order[0],
                                        "size": order[1]})
                            self.order_id += 1
                if "buy" in data:
                    print("Found buy")
                    for order in data["buy"]:
                        if order[0] >= 1000 + self.fair_value_threshold:
                            self.send_action({"type": "add", "order_id": self.order_id,
                                        "symbol": "BOND", "dir": "SELL", "price": order[0],
                                        "size": order[1]})
                            self.order_id += 1
            time.sleep(1)

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
        addr = (hostname + self.team_name * self.test_mode, port)
        self.market.connect(addr)
        self.stream = self.market.makefile('rw', 1)

    def send_action(self, action):
        try:
            print("Entered")
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
            return json.loads(data)
        except json.JSONDecodeError:
            print("Expected JSON but got {}.".format(data))


Bot(True)
