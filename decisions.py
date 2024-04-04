from enum import Enum
from datetime import datetime, timezone, timedelta
import uuid


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
    NOT_ENOUGH_BUYING_POWER = "NOT_ENOUGH_BUYING_POWER"

class Decision():
    """ """
    def __init__(
            self,
            decision_type: DecisionType, 
            enviorment: Enviorment, 
            price: float,
            symbol: str,
            asset_balance: float,
            total_asset_value: float,
            usdc_balance: float,
            volume_24h: float,
            volume_percentage_change_24h: float,
            price_percentage_change_24h: float):
        self.enviorment = enviorment
        self.decision_type = decision_type
        self.price = price
        self.symbol = symbol
        self.asset_balance = asset_balance
        self.total_asset_value = total_asset_value
        self.usdc_balance = usdc_balance
        self.volume_24h = volume_24h
        self.volume_percentage_change_24h = volume_percentage_change_24h
        self.price_percentage_change_24h = price_percentage_change_24h
        self.timestamp = datetime.utcnow()
        unique_id = uuid.uuid4()
        self.uuid = str(unique_id)
        
    def __str__(self):
        return f"{self.action} {self.amount} at {self.price} on {self.timestamp}"
    
    def get_attributes(self):
        # This method returns all instance attributes as a dictionary
        attrs = self.__dict__
        attrs['enviorment'] = self.enviorment.value
        attrs['decision_type'] = self.decision_type.value
        return attrs

    def uuid(self):
        return self.uuid

class BuyDecision(Decision): 

    def __init__(
            self,
            enviorment: Enviorment, 
            price: float,
            symbol: str,
            asset_balance: float,
            usdc_balance: float,
            volume_24h: float,
            volume_percentage_change_24h: float,
            price_percentage_change_24h: float,
            
            # custom attributes
            coinbase_order: any,
            amount: float, 
            value: float):
        super().__init__(
            DecisionType.BUY, 
            enviorment,
            price,
            symbol,
            asset_balance,
            usdc_balance,
            volume_24h,
            volume_percentage_change_24h,
            price_percentage_change_24h)
        
        self.coinbase_order = coinbase_order
        self.amount = amount
        self.value = value
        self.is_open = True
        
    @property
    def action(self):
        return DecisionType.BUY.value
    

class SellDecision(Decision): 

    def __init__(
            self,
            enviorment: Enviorment, 
            price: float,
            symbol: str,
            asset_balance: float,
            usdc_balance: float,
            volume_24h: float,
            volume_percentage_change_24h: float,
            price_percentage_change_24h: float,
            current_price: float,

            # custom attributes
            cointbase_order: any,
            amount: float, 
            value: float,
            profit: float,
            linked_buy_decisions: [str]):

        super().__init__(
            DecisionType.SELL, 
            enviorment, 
            price,
            symbol,
            asset_balance,
            usdc_balance,
            volume_24h,
            volume_percentage_change_24h,
            price_percentage_change_24h,
            current_price)
        
        self.cointbase_order = cointbase_order
        self.amount = amount
        self.value = value
        self.profit = profit
        self.linked_buy_decisions = linked_buy_decisions

        
    @property
    def action(self):
        return DecisionType.SELL.value
    

class BestMatchBelowThresholdDecision(Decision): 

    def __init__(
            self,
            enviorment: Enviorment, 
            price: float,
            symbol: str,
            asset_balance: float,
            usdc_balance: float,
            volume_24h: float,
            volume_percentage_change_24h: float,
            price_percentage_change_24h: float,

            # custom attributes
            percentage_delta: float,
            hypothetical_profit: float,
            associated_buy_decision: str):

        super().__init__(
            DecisionType.BEST_MATCH_BELOW_THRESHOLD, 
            enviorment, 
            price,
            symbol,
            asset_balance,
            usdc_balance,
            volume_24h,
            volume_percentage_change_24h,
            price_percentage_change_24h)
        
        self.percentage_delta = percentage_delta
        self.hypothetical_profit = hypothetical_profit
        self.associated_buy_decision = associated_buy_decision

        
    @property
    def action(self):
        return DecisionType.BEST_MATCH_BELOW_THRESHOLD.value

