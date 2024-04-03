from enum import Enum
from datetime import datetime, timezone, timedelta


class Enviorment(Enum):
    DRYRUN = "dryrun"
    SANDBOX = "sandbox"
    PRODUCTION = "production"


class DecisionType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    SKIP = "SKIP"
    BEST_MATCH_BELOW_THRESHOLD = "BEST_MATCH_BELOW_THRESHOLD"
    TOO_MANY_OPEN_BUYS = "TOO_MANY_OPEN_BUYS"

class Decision():
    """ """
    def __init__(
            self,
            trxId: str,
            enviorment: Enviorment, 
            decisionType: DecisionType, 
            amount: float, 
            value: float, 
            price: float,
            btcBalance: float,
            usdcBalance: float,
            rateOfChange: float, 
            timestamp: datetime = None):
        self.trxId = trxId
        self.enviorment = enviorment
        self.decisionType = decisionType
        self.amount = amount
        self.value = value
        self.price = price
        self.rateOfChange = rateOfChange
        self.timestamp = timestamp if timestamp else datetime.now()
        
    def __str__(self):
        return f"{self.action} {self.amount} at {self.price} on {self.timestamp}"
    
    def get_attributes(self):
        # This method returns all instance attributes as a dictionary
        return self.__dict__
    

