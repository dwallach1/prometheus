
class Asset():
    """Base class for all assets"""

    def __init__(
            self,
            name: str,
            symbol: str,
            account_id: str,
            amount_to_buy: float,
            buy_price_percentage_change_threshold: float,
            sell_price_percentage_change_threshold: float,
            max_open_buys: int):
        self.name = name
        self.symbol = symbol
        self.account_id = account_id
        self.amount_to_buy = amount_to_buy
        self.buy_price_percentage_change_threshold = buy_price_percentage_change_threshold
        self.sell_price_percentage_change_threshold = sell_price_percentage_change_threshold
        self.max_open_buys = max_open_buys

    def __str__(self):
        return f'{self.name} @ {self.price}'

    def symbol(self):
        return self.symbol

    def amount_to_buy(self):
        return self.amount_to_buy

    def buy_price_percentage_change_threshold(self):
        return self.buy_price_percentage_change_threshold

    def sell_price_percentage_change_threshold(self):
        return self.sell_price_percentage_change_threshold

    def max_open_buys(self):
        return self.max_open_buys
