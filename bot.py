import socket
import json


class Bot:

    def __init__(self, test=False):
        """
        Initialization of bot class.
        :param test:
        """
        self.team_name = "TEAMSTOCKERS"
        self.test_mode = test
        if test:
            self.test()
        pass

    def test(self):
        self.make_connection("test-exch-", 25000)
        print(self.read_market())


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
            json.dump(self.stream, action)
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