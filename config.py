import os
import json


class Config:
    def __init__(self, **entries):
        self.running = False
        self.enable_proxy = False
        self.test = False
        self.proxies = {'http': 'http://127.0.0.1:8001', 'https': 'http://127.0.0.1:8001'}
        self.api_key = ''
        self.secret = ''
        self.symbol = ''
        self.time_frame = ''
        self.strategies = []
        self.api_rest_interval = 0
        self.api_error_interval = 0
        self.contracts = []
        self.__dict__.update(entries)

    def save(self):
        with open('config.json', 'w') as fp:
            json.dump(self.__dict__, fp, indent=4)

    @classmethod
    def load(cls):
        if os.path.isfile('config.json'):
            with open('config.json', 'r') as fp:
                return cls(**json.load(fp))
        return cls()
