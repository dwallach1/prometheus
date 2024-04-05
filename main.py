import time
import os
import logging
import json
from enum import Enum
from coinbase.rest import RESTClient
from json import dumps
from dotenv import dotenv_values
from pymongo.mongo_client import MongoClient
from datetime import datetime
import uuid
from decisions import Decision, DecisionType, Enviorment, BestMatchBelowThresholdDecision, BuyDecision, SellDecision, DecsionContext
from assets import Asset

# https://docs.cloud.coinbase.com/prime/reference/primerestapi_createorder
# https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getproduct

DEFAULT_CONFIG_PATH = "config.json"
USD_SYMBOL = "USD"
USDC_SYMBOL = "USDC"
BTC_SYMBOL = "BTC"
ETH_SYMBOL = "ETH"
SOL_SYMBOL = "SOL"
ONE_HOUR = 60 * 60
DECISION_BUFFER = ONE_HOUR
BUY_BUFFER = ONE_HOUR * 12

MAX_BUY_AMOUNT = 1000.00
MAX_SELL_AMOUNT = 5000.00


class OrderType(Enum):
    BUY = "BUY"
    SELL = "SELL"


class DecisionMaker():

    def __init__(
            self,
            logger: logging.Logger,
            enviormnet: Enviorment, 
            cb_client: RESTClient, 
            mongo_client: MongoClient,
            db_name: str,
            collection_name: str,
            asset_config: Asset,
            usd_account_id: str
        ):
        self.logger = logger
        self.logger.info(f"============ intializing new decision maker for {asset_config.symbol} in {enviormnet} ============")
        self.enviorment = enviormnet
        self.cb_client = cb_client
        self.mongo_client = mongo_client
        self.db_name = db_name
        self.collection_name = collection_name
        self.asset_config = asset_config
        self.usd_account_id = usd_account_id
        self.product_id = f"{self.asset_config.symbol}-USD"

    def get_buying_power(self) -> float:
        self.logger.info("Getting buying power")
        account = self.cb_client.get_account(self.usd_account_id)
        usd_balance = float(account["account"]["available_balance"]["value"])
        self.logger.info(f"$USD balance: {usd_balance} as of {datetime.utcnow()}")
        return usd_balance

    def get_asset_balance(self) -> float:
        self.logger.info("Getting asset balances")
        account = self.cb_client.get_account(self.asset_config.account_id)
        asset_balance = float(account["account"]["available_balance"]["value"])
        self.logger.info(f"{self.asset_config.symbol} balance: {asset_balance} as of {datetime.utcnow()}")
        return asset_balance

    def compute_decisions(self):
        now = datetime.utcnow()
        decisions = []
        self.logger.info(f"computing decisions for {self.asset_config.symbol} at {now}")
        buying_power = self.get_buying_power()
        has_enough_buying_power = buying_power > self.asset_config.amount_to_buy * 1.5
        if not has_enough_buying_power:
            self.logger.warn("🛑 Not enough buying power")
        asset_balance = self.get_asset_balance()
        open_decisions = self.get_open_decisions()

        product = self.cb_client.get_product(self.product_id)
        current_price = float(product["price"])
        price_percentage_change_24h = float(product["price_percentage_change_24h"])
        volume_percentage_change_24h = float(product["volume_percentage_change_24h"])
        volume_24h = float(product["volume_24h"])
        total_asset_holdings_value = asset_balance * current_price
        self.logger.info("asset prices: {}".format(
            json.dumps({
                'current_price': current_price,
                'price_percentage_change_24h': price_percentage_change_24h,
                'volume_percentage_change_24h': volume_percentage_change_24h,
                'volume_24h': volume_24h,
                'total_asset_holdings_value': total_asset_holdings_value
            }, indent=4)
        ))

        context = DecsionContext(
            enviorment=self.enviorment,
            price=current_price,
            symbol=self.asset_config.symbol,
            asset_balance=asset_balance,
            total_asset_value=total_asset_holdings_value,
            usdc_balance=buying_power,
            volume_24h=volume_24h,
            volume_percentage_change_24h=volume_percentage_change_24h,
            price_percentage_change_24h=price_percentage_change_24h,
            total_asset_holdings_value=total_asset_holdings_value
        )

        if price_percentage_change_24h < self.asset_config.buy_price_percentage_change_threshold:
            self.logger.info(f"🟢 Price percentage change in 24h is above threshold [{price_percentage_change_24h}]")
            buy_buffer_check = self.check_buy_buffer(open_decisions)
            if not buy_buffer_check:
                self.logger.warn("🛑 Buy buffer not met")
            elif has_enough_buying_power:
                self.logger.info("🟢 Buying power is sufficient")
                open_buy_orders = self.make_buy_decisions()
                if len(open_buy_orders) < self.asset_config.max_open_buys:
                    self.logger.info("🚀 Placing buy order")
                    amount_to_buy = self.asset_config.amount_to_buy / current_price
                    # todo place buy order
                    # get the orderId and other relevant info from buy order
                    order_result, ok = self.place_order(OrderType.BUY, f"{self.asset_config.amount_to_buy}")
                    if not ok:
                        self.logger.warn("🛑 Failed to place buy order")
                        # TODO: make custom decision for this and capture
                        decision = Decision(
                            decision_type=DecisionType.FAILED_TO_PLACE_BUY_ORDER,
                            enviorment=self.enviorment,
                            price=current_price,
                            symbol=self.asset_config.symbol,
                            asset_balance=asset_balance,
                            total_asset_value=total_asset_holdings_value,
                            usdc_balance=buying_power,
                            volume_24h=volume_24h,
                            volume_percentage_change_24h=volume_percentage_change_24h,
                            price_percentage_change_24h=price_percentage_change_24h
                        )
                        decisions.append(decision)
                    else:
                        buy_decision = BuyDecision(
                            enviorment=self.enviorment,
                            price=current_price,
                            symbol=self.asset_config.symbol,
                            asset_balance=asset_balance,
                            total_asset_value=total_asset_holdings_value,
                            usdc_balance=buying_power,
                            volume_24h=volume_24h,
                            volume_percentage_change_24h=volume_percentage_change_24h,
                            price_percentage_change_24h=price_percentage_change_24h,
                            coinbase_order=order_result,
                            # todo: replace this with actual values from 
                            amount=amount_to_buy,
                            value=amount_to_buy * current_price
                        )
                        decisions.append(buy_decision)
                else:
                    self.logger.info(f"too mamy open buy orders ({len(open_buy_orders)} >= {self.asset_config.max_open_buys})")
                    decision = Decision(decision_type=DecisionType.TOO_MANY_OPEN_BUYS, context=context)
                    decisions.append(decision)
            else:
                self.logger.warn("🛑 Not enough buying power to place buy orders")
                decision = Decision(decision_type=DecisionType.NOT_ENOUGH_BUYING_POWER, context=context)
        
        else:
            self.logger.info(f"🛑 Price percentage change in 24h does not meet buying threshold ({price_percentage_change_24h} > {self.asset_config.buy_price_percentage_change_threshold})")

        if len(open_decisions) > 0:
            best_match = None
            best_match_price_delta = -float('inf')
            best_match_hypothetical_profit = 0
            to_sell = []
            for decision in open_decisions:
                decision_price = float(decision["price"])
                decision_amount = float(decision["amount"])
                decision_value = float(decision["value"])
                price_delta = ((current_price - decision_price) / decision_price) * 100
                if price_delta > self.asset_config.sell_price_percentage_change_threshold:
                    to_sell.append(decision)
                    decision_id = decision["uuid"]
                    self.logger.info(f"🚀 Placing sell order for {decision_id}")
                if price_delta > best_match_price_delta:
                    best_match = decision
                    best_match_price_delta = price_delta
                    best_match_hypothetical_profit = (decision_amount * current_price) - decision_value
            
            if len(to_sell) == 0:
                self.logger.info("no open buy orders meet sell threshold, saving best match below threshold decision")
                best_match_id = best_match["uuid"]
                decision = BestMatchBelowThresholdDecision(
                    context=context,
                    percentage_delta=best_match_price_delta,
                    hypothetical_profit=best_match_hypothetical_profit,
                    associated_buy_decision=best_match_id
                )
                decisions.append(decision)
            else:
                self.logger.info(f"found {len(to_sell)} open buy orders to sell")
                sell_decision = self.place_sell_order(context, to_sell)
                if sell_decision.is_successful:
                    self.close_open_buy_decisions(to_sell, sell_decision.uuid(), current_price)
                    decisions.append(sell_decision)

        if len(decisions) == 0:
            self.logger.info("no decisions made... generating a skip decision")
            decision = Decision(decision_type=DecisionType.SKIP, context=context)
            decisions.append(decision)

        self.save_decisions_to_db(decisions)

    def get_open_decisions(self) -> [any]:
        res = self.mongo_client[self.db_name][self.collection_name].find({
            'decision_type': DecisionType.BUY.value,
            'is_open': True,
            'symbol': self.asset_config.symbol,
            'enviorment': self.enviorment.value
        }).sort("timestamp", -1)
        open_decisions = [result for result in res]
        open_decisions_uuids = [decision["uuid"] for decision in open_decisions]
        self.logger.info(f"found {len(open_decisions)} open decisions: {open_decisions_uuids}")
        return open_decisions

    def check_buy_buffer(self, open_decisions: [any]) -> bool:
        if len(open_decisions) == 0:
            return True
        # becasue we are sorting by timestamp in descending order, the first element is the most recent
        last_decision = open_decisions[0]
        last_decision_timestamp = last_decision["timestamp"]
        self.logger.info("last decision timestamp: " + str(last_decision_timestamp))
        now = datetime.utcnow()
        time_delta = now - last_decision_timestamp
        return time_delta.total_seconds() > BUY_BUFFER

    def place_order(self, order_type: OrderType, amount: str) -> (any, bool):
        """"""
        if self.enviorment != Enviorment.PRODUCTION:
            self.logger.info(f"non-production mode detected ({self.enviorment}). Not placing any real orders")
            return None, True
        """
        {
            "order_total": "1000.00000000000000002025",
            "commission_total": "5.46991546494281452025",
            "errs": [
                "PREVIEW_INSUFFICIENT_FUND"
            ],
            "warning": [],
            "quote_size": "994.5300845350571855",
            "base_size": "0.0146854779492673",
            "best_bid": "67722",
            "best_ask": "67722.01",
            "is_max": false,
            "order_margin_total": "0",
            "leverage": "0",
            "long_leverage": "0",
            "short_leverage": "0",
            "slippage": "0.0000000000000024"
        }
        """

        if order_type == OrderType.BUY:
            preview = self.cb_client.preview_market_order_buy(
                self.product_id,
                amount,
            )
            self.logger.info(f"buy preview => {json.dumps(preview, indent=4)}")
            if "errs" in preview and len(preview["errs"]) > 0:
                self.logger.warn(f"🛑 preview error: {preview['errs']}")
                return preview, False
            preview_order_total = float(preview["order_total"])
            if preview_order_total > MAX_BUY_AMOUNT:
                self.logger.warn(f"🛑 preview order total too high: {preview_order_total}")
                return preview, False
            order = self.cb_client.place_market_order_buy(
                self.product_id,
                amount,
            )
            self.logger.info(f"buy order => {json.dumps(order, indent=4)}")
            if "errs" in order and len(order["errs"]) > 0:
                self.logger.warn(f"🛑 order error: {order['errs']}")
                return order, False
            return order, True
        elif order_type == OrderType.SELL:
            preview = self.cb_client.preview_market_order_sell(
                self.product_id,
                amount,
            )
            self.logger.info(f"sell preview => {json.dumps(preview, indent=4)}")
            if "errs" in preview and len(preview["errs"]) > 0:
                self.logger.warn(f"🛑 preview error: {preview['errs']}")
                return preview, False
            preview_order_total = float(preview["order_total"])
            if preview_order_total > MAX_SELL_AMOUNT:
                self.logger.warn(f"🛑 preview order total too high: {preview_order_total}")
                return preview, False
            order = self.cb_client.place_market_order_sell(
                self.product_id,
                amount,
            )
            self.logger.info(f"sell order => {json.dumps(order, indent=4)}")
            if "errs" in order and len(order["errs"]) > 0:
                self.logger.warn(f"🛑 order error: {order['errs']}")
                return order, False
            return order, True
        else:
            raise Exception("Invalid order type")

    def place_sell_order(self, context: DecsionContext, buy_decsions_to_sell: [any]) -> Decision:
        amount_to_sell = float(0)
        value_accumulated = float(0)
        for decision in buy_decsions_to_sell:
            amount_to_sell += float(decision["amount"])
            value_accumulated += float(decision["value"])
        
        amount_as_string = "f{amount_to_sell}"
        successful = True
        errors = []
        order_total = 0.0
        preview_order = self.cb_client.preview_market_order_sell(
            self.product_id,
            amount_as_string,
        )
        self.logger.info(f"sell preview => {json.dumps(preview_order, indent=4)}")
        if "errs" in preview_order and len(preview_order["errs"]) > 0:
            self.logger.warn(f"preview error: {preview_order['errs']}")
            errors = preview_order["errs"]
            successful = False
        
        preview_order_total = float(preview_order["order_total"])
        order_total = preview_order_total
        if preview_order_total > MAX_SELL_AMOUNT:
            self.logger.warn("preview order total too high: {preview_order_total}")
            errors.append("preview order total too high")
            successful = False

        real_order = None
        if self.enviorment == Enviorment.PRODUCTION and successful:
            real_order = self.cb_client.place_market_order_sell(
                self.product_id,
                amount_as_string,
            )
            real_order_total = float(real_order["order_total"])
            order_total = real_order_total
            self.logger.info(f"sell order => {json.dumps(real_order, indent=4)}")
            if "errs" in real_order and len(real_order["errs"]) > 0:
                self.logger.warn(f"real order error: {real_order['errs']}")

        profit = order_total - value_accumulated
        self.logger.info(f"sell order profit: {profit}")
        decision = SellDecision(
            context=context,
            amount=amount_to_sell,
            value=order_total,
            profit=profit,
            linked_buy_decisions=[decision["uuid"] for decision in buy_decsions_to_sell],
            preview_result=preview_order,
            trade_result=real_order,
            is_successful=successful,
            errors=errors
        )
        return decision

    def save_decisions_to_db(self, decisions: [Decision]):
        data = [d.get_attributes() for d in decisions]
        res = self.mongo_client[self.db_name][self.collection_name].insert_many(data)
        self.logger.info(f"Saved decisions to database {res}")

    def close_open_buy_decisions(self, buy_decisions: [any], closed_by: str, current_price: float):
        for decision in buy_decisions:
            decision_id = decision["uuid"]
            self.logger.info(f"Closing buy order {decision_id}")
            updated_decision = {
                "is_open": False,
                "close_price": current_price,
                "close_time": datetime.utcnow(),
                "closed_by": closed_by,
                "profit": (float(decision["amount"]) * current_price) - float(decision["value"])
            }
            self.mongo_client[self.db_name][self.collection_name].update_one(
                {"uuid": decision_id},
                {"$set": updated_decision}
            )


def parse_config(cb_accounts) -> [Asset]:
    config_path = os.getenv("CONFIG_PATH", DEFAULT_CONFIG_PATH)
    with open(config_path, 'r') as file:
        data = json.load(file)
    print("lodaded config ➡️ ", json.dumps(data, indent=4))
    assets = []
    for asset in data["assets"]:
        account = next((account for account in cb_accounts if account["currency"] == asset["symbol"]), None)
        if account is None:
            raise Exception(f"❌ could not find account for {asset['symbol']}")

        asset = Asset(
            asset["name"],
            asset["symbol"],
            account["uuid"],
            float(asset["amount_to_buy_usd"]),
            float(asset["buy_price_percentage_change_threshold"]),
            float(asset["sell_price_percentage_change_threshold"]),
            float(asset["max_open_buys"])
        )
        assets.append(asset)
        print(f"sucessfully loaded asset config {asset.name} (${asset.symbol})")
    return assets


def get_cb_accounts(cb_clinet: RESTClient) -> dict:
    accounts = []
    has_more = True
    cursor = None
    while has_more:
        response = cb_clinet.get_accounts(cursor=cursor)
        accounts += response["accounts"]
        has_more = response["has_next"]
        cursor = response["cursor"]
    return accounts


def setup_logger(trx_id):
    """
    Set up a logger with a specific transaction ID.
    """
    logger = logging.getLogger(trx_id)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    return logger


def test_order_placing(cb_client):
    transaction_id = uuid.uuid4()
    trxId = str(transaction_id)
    logger = setup_logger(trxId)  
    decisionMaker = DecisionMaker(
        logger, 
        Enviorment.PRODUCTION, 
            cb_client, 
            None,
            "",
            "",
            Asset(
                name="Test",
                symbol="TEST",
                account_id="",
                amount_to_buy=0,
                buy_price_percentage_change_threshold=0,
                sell_price_percentage_change_threshold=0,
                max_open_buys=0
            ),
            ""
        )
    decisionMaker.place_order(USDC_SYMBOL, BTC_SYMBOL, 50)


def main():
    dotenv_exists = os.path.exists(".env")
    config = None
    if dotenv_exists:
        config = dotenv_values(".env")

    MONGO_URI = os.getenv("MONGO_URI")
    if MONGO_URI is None and config is not None:
        MONGO_URI = config["MONGO_URI"]
    assert MONGO_URI, "MONGO_URI is required"

    DB_NAME = os.getenv("DB_NAME")
    if DB_NAME is None and config is not None:
        DB_NAME = config["DB_NAME"]
    assert DB_NAME, "DB_NAME is required"

    DB_COLLECTION = os.getenv("DB_COLLECTION")
    if DB_COLLECTION is None and config is not None:
        DB_COLLECTION = config["DB_COLLECTION"]
    assert DB_COLLECTION, "DB_COLLECTION is required"

    API_KEY = os.getenv("COINBASE_API_KEY")
    if API_KEY is None and config is not None:
        API_KEY = config["COINBASE_API_KEY"]
    assert API_KEY, "API_KEY is required"

    API_SECRET = os.getenv("COINBASE_API_SECRET")
    if API_SECRET is None and config is not None:
        API_SECRET = config["COINBASE_API_SECRET"]
    assert API_SECRET, "API_SECRET is required"

    cb_client = RESTClient(api_key=API_KEY, api_secret=API_SECRET)
    mongo_client = MongoClient(MONGO_URI)
    
    cb_accounts = get_cb_accounts(cb_client)
    cash_account = next((account for account in cb_accounts if account["currency"] == USD_SYMBOL), None)
    if cash_account is None:
        raise Exception(f"❌ could not find account for {USDC_SYMBOL}")
    cash_account_id = cash_account["uuid"]
    assets = parse_config(cb_accounts)

    # buy_preview = cb_client.preview_market_order_buy(
    #     "BTC-USD", 
    #     "1000",
    #     )
    # print("buy preview =>")
    # print (json.dumps(buy_preview, indent=4))
    

    # sell_preview = cb_client.preview_market_order_sell(
    #     "BTC-USD", 
    #     "1",
    #     )
    # print (json.dumps(sell_preview, indent=4))

    while True:
        for asset_config in assets:
            transaction_id = uuid.uuid4()
            trxId = str(transaction_id)
            logger = setup_logger(trxId)
            decisionMaker = DecisionMaker(
                logger,
                Enviorment.PRODUCTION,
                cb_client,
                mongo_client,
                DB_NAME,
                DB_COLLECTION,
                asset_config,
                cash_account_id
            )
            decisionMaker.compute_decisions()
            logger.info("finished making decisions :)")
        time.sleep(DECISION_BUFFER)

if __name__ == "__main__":
    main()