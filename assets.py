from typing import List
from dataclasses import dataclass
from abc import ABC, abstractmethod
import datetime


@dataclass
class Candle:
    """
    Represents a single candlestick data point.
    """
    start: int
    low: float
    high: float
    open: float
    close: float
    volume: float


def parse_candles(candle_data: List[dict]) -> List[Candle]:
    """
    Parses an array of JSON-like candle data into an array of Candle objects.

    Args:
        candle_data (List[dict]): A list of dictionaries, where each dictionary represents a single candle.

    Returns:
        List[Candle]: A list of Candle objects.
    """
    candles = []
    for candle_dict in candle_data:
        candle = Candle(
            start=int(candle_dict["start"]),
            low=float(candle_dict["low"]),
            high=float(candle_dict["high"]),
            open=float(candle_dict["open"]),
            close=float(candle_dict["close"]),
            volume=float(candle_dict["volume"])
        )
        candles.append(candle)
    return candles


class BuyStrategy(ABC):
    """
    Base class for all buy strategies.
    """
    @abstractmethod
    def should_buy(self, logger, candles: [Candle]):
        """
        Determines whether the asset should be sold based on the strategy.

        Args:
            asset_data (dict): A dictionary containing the current asset data.

        Returns:
            bool: True if the asset should be sold, False otherwise.
        """
        pass


class BuyTheDipStrategy(ABC):
    """
    Buy strategy to buy the dip.
    """

    def __init__(self, candle_size, green_candles_in_a_row):
        self.candle_size = candle_size
        self.green_candles_in_a_row = green_candles_in_a_row

    def should_buy(self, logger, candles: [Candle]):
        """
        Determines whether the asset should be bought based on the Buy the Dip strategy.
        """
        green_candle_count = 0
        for candle in candles:
            candle_time = datetime.utcfromtimestamp(int(candle.start))
            candle_date = candle_time.strftime("%Y-%m-%d %H:%M:%S")
            is_green = candle["close"] > candle["open"]
            if is_green:
                logger.info(f"found green candle at {candle_date}")
                green_candle_count += 1
            else:
                logger.info(f"found red candle at {candle_date}")
                break

        return green_candle_count >= self.green_candles_in_a_row


class SellStrategy(ABC):
    """
    Base class for all sell strategies.
    """
    @abstractmethod
    def should_sell(self, logger, candles: [Candle]):
        """
        Determines whether the asset should be sold based on the strategy.

        Args:
            asset_data (dict): A dictionary containing the current asset data.

        Returns:
            bool: True if the asset should be sold, False otherwise.
        """
        pass


class MaximizeProfitSellStrategy(SellStrategy):
    """
    Sell strategy that aims to maximize profit.
    """

    def __init__(self, candle_size, red_candles_in_a_row):
        self.candle_size = candle_size
        self.red_candles_in_a_row = red_candles_in_a_row

    def should_sell(self, logger, candles: [Candle]):
        """
        Determines whether the asset should be sold based on the Maximize Profit strategy.
        """
        red_candle_count = 0
        for candle in candles:
            candle_time = datetime.utcfromtimestamp(int(candle.start))
            candle_date = candle_time.strftime("%Y-%m-%d %H:%M:%S")
            is_red = candle["close"] < candle["open"]
            if is_red:
                logger.info(f"found red candle at {candle_date}")
                red_candle_count += 1
            else:
                logger.info(f"found green candle at {candle_date}")
                break

        return red_candle_count >= self.red_candles_in_a_row


class ImmediateSellStrategy(SellStrategy):
    """
    Sell strategy that sells the asset immediately.
    """

    def should_sell(self, logger, candles: [Candle]):
        """
        Determines whether the asset should be sold based on the Immediate Sell strategy.
        """
        return True


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
        max_open_buys: int,
        buy_strategy: BuyStrategy,
        sell_strategy: SellStrategy

    ):
        self.name = name
        self.symbol = symbol
        self.account_id = account_id
        self.amount_to_buy = amount_to_buy
        self.buy_price_percentage_change_threshold = buy_price_percentage_change_threshold
        self.sell_price_percentage_change_threshold = sell_price_percentage_change_threshold
        self.max_open_buys = max_open_buys
        self.buy_strategy = buy_strategy
        self.sell_strategy = sell_strategy

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
