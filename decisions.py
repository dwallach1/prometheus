from enum import Enum
from datetime import datetime
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
    FAILED_TRADE = "FAILED_TRADE"


class DecisionContext:
    """ """
    def __init__(self,
                 enviorment: Enviorment,
                 price: float,
                 symbol: str,
                 asset_balance: float,
                 total_asset_value: float,
                 usdc_balance: float,
                 volume_24h: float,
                 volume_percentage_change_24h: float,
                 price_percentage_change_24h: float,
                 total_asset_holdings_value: float):
        self.enviorment = enviorment
        self.price = price
        self.symbol = symbol
        self.asset_balance = asset_balance
        self.total_asset_value = total_asset_value
        self.usdc_balance = usdc_balance
        self.volume_24h = volume_24h
        self.volume_percentage_change_24h = volume_percentage_change_24h
        self.price_percentage_change_24h = price_percentage_change_24h
        self.total_asset_holdings_value = total_asset_holdings_value
     
    def get_attributes(self):
        # This method returns all instance attributes as a dictionary
        attrs = self.__dict__
        attrs['enviorment'] = self.enviorment.value
        return attrs


class Decision():
    """ """
    def __init__(
            self,
            decision_type: DecisionType,
            context: DecisionContext):
        self.decision_type = decision_type
        self.context = context
        self.timestamp = datetime.utcnow()
        unique_id = uuid.uuid4()
        self.uuid = str(unique_id)

    def get_attributes(self):
        # This method returns all instance attributes as a dictionary
        attrs = self.__dict__
        attrs['decision_type'] = self.decision_type.value
        attrs["context"] = self.context.get_attributes()
        return attrs

    def uuid(self):
        return self.uuid


class BuyDecision(Decision):

    def __init__(
            self,
            context,

            # custom attributes
            amount: float,
            value: float,
            preview_result: any,
            trade_result: any,
            is_successful: bool,
            errors: [str]):
        super().__init__(
            DecisionType.BUY, context)

        self.amount = amount
        self.value = value
        self.preview_result = preview_result
        self.trade_result = trade_result
        self.is_successful = is_successful
        self.errors = errors
        self.is_open = True

    @property
    def action(self):
        return DecisionType.BUY.value


class SellDecision(Decision):

    def __init__(
            self,
            context: DecisionContext,

            # custom attributes
            amount: float,
            value: float,
            profit: float,
            linked_buy_decisions: [str],
            preview_result: any,
            trade_result: any,
            is_successful: bool,
            errors: [str]):

        super().__init__(DecisionType.SELL, context)
        self.amount = amount
        self.value = value
        self.profit = profit
        self.linked_buy_decisions = linked_buy_decisions
        self.preview_result = preview_result
        self.trade_result = trade_result
        self.is_successful = is_successful
        self.errors = errors

    @property
    def action(self):
        return DecisionType.SELL.value

    @property
    def is_successful(self):
        return self.is_successful


class BestMatchBelowThresholdDecision(Decision):

    def __init__(
            self,
            context: DecisionContext,

            # custom attributes
            percentage_delta: float,
            hypothetical_profit: float,
            associated_buy_decision: str):

        super().__init__(
            DecisionType.BEST_MATCH_BELOW_THRESHOLD, context)

        self.percentage_delta = percentage_delta
        self.hypothetical_profit = hypothetical_profit
        self.associated_buy_decision = associated_buy_decision

    @property
    def action(self):
        return DecisionType.BEST_MATCH_BELOW_THRESHOLD.value
