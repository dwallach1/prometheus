import time
import os
import logging
import json
from enum import Enum
from coinbase.rest import RESTClient
from dotenv import dotenv_values
from pymongo.mongo_client import MongoClient
from datetime import datetime
import uuid
from decisions import Decision, DecisionType, Enviorment, BestMatchBelowThresholdDecision, BuyDecision, SellDecision, DecisionContext
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
            usd_account_id: str):
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
            self.logger.warning("🛑 Not enough buying power")
        asset_balance = self.get_asset_balance()
        open_buy_decisions = self.get_open_buy_decisions()

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
        price_change_check = price_percentage_change_24h < self.asset_config.buy_price_percentage_change_threshold
        buy_buffer_check = self.check_buy_buffer(open_buy_decisions)
        open_buy_check = len(open_buy_decisions) < self.asset_config.max_open_buys
        self.logger.info("condition checks: {}".format(
            json.dumps({
                'price_change_check': price_change_check,
                'buy_buffer_check': buy_buffer_check,
                'open_buy_check': open_buy_check,
                'open_buy_count': len(open_buy_decisions),
            }, indent=4)
        ))

        context = DecisionContext(
            enviorment=self.enviorment,
            price=current_price,
            symbol=self.asset_config.symbol,
            asset_balance=asset_balance,
            total_asset_value=total_asset_holdings_value,
            usdc_balance=buying_power,
            volume_24h=volume_24h,
            volume_percentage_change_24h=volume_percentage_change_24h,
            price_percentage_change_24h=price_percentage_change_24h,
            total_asset_holdings_value=total_asset_holdings_value,
            price_change_check=price_change_check,
            buy_buffer_check=buy_buffer_check,
            open_buy_check=open_buy_check,
            open_buy_count=len(open_buy_decisions)
        )

        # CHECK BUY CONDITIONS
        if price_change_check and buy_buffer_check and open_buy_check:
            buy_decision = self.place_buy_order(context)
            decisions.append(buy_decision)

        # CHECK SELL CONDITIONS
        if len(open_buy_decisions) > 0:
            best_match = None
            best_match_price_percent_delta = -float('inf')
            best_match_hypothetical_profit = 0
            to_sell = []
            for decision in open_buy_decisions:
                decision_price = float(decision["context"]["price"])
                decision_amount = float(decision["amount"])
                decision_value = float(decision["value"])
                price_percent_delta = ((current_price - decision_price) / decision_price) * 100
                if price_percent_delta > self.asset_config.sell_price_percentage_change_threshold:
                    to_sell.append(decision)
                    decision_id = decision["uuid"]
                    self.logger.info(f"🚀 Placing sell order for {decision_id}")
                if price_percent_delta > best_match_price_percent_delta:
                    best_match = decision
                    best_match_price_percent_delta = price_percent_delta
                    best_match_hypothetical_profit = (decision_amount * current_price) - decision_value

            if len(to_sell) == 0:
                best_match_id = best_match["uuid"]
                self.logger.info(f"no sells found, found best match: {best_match_id} with delta {best_match_price_percent_delta}")
                if best_match_price_percent_delta > 5.0:
                    # we want to get info on the right sell threshold. so use this decision to house that
                    decision = BestMatchBelowThresholdDecision(
                        context=context,
                        percentage_delta=best_match_price_percent_delta,
                        hypothetical_profit=best_match_hypothetical_profit,
                        associated_buy_decision=best_match_id
                    )
                    # save directly to db instead of appending to decisions
                    self.save_decisions_to_db([decision])
            else:
                self.logger.info(f"found {len(to_sell)} open buy orders to sell")
                sell_decision = self.place_sell_order(context, to_sell)
                if sell_decision.is_successful:
                    self.close_open_buy_decisions(to_sell, sell_decision.uuid(), current_price)
                    decisions.append(sell_decision)

        if len(decisions) == 0:
            self.logger.info("no decisions made (no buys or sells)... generating a skip decision")
            decision = Decision(decision_type=DecisionType.SKIP, context=context)
            decisions.append(decision)

        self.save_decisions_to_db(decisions)

    def get_open_buy_decisions(self) -> [any]:
        res = self.mongo_client[self.db_name][self.collection_name].find({
            'decision_type': DecisionType.BUY.value,
            'is_open': True,
            'context.symbol': self.asset_config.symbol,
            'actualualized': True
            # 'context.enviorment': self.enviorment.value
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

    def place_buy_order(self, context: DecisionContext) -> (any, bool):
        """ """
        self.logger.info(f"🚀 Placing BUY order for {self.asset_config.symbol}")
        amount = self.asset_config.amount_to_buy
        amount_as_string = f"{amount:.4f}"
        self.logger.info(f"buying {amount_as_string} $USD worth of {self.asset_config.symbol}")
        successful = True
        errors = []
        value = 0.0
        amount = 0.0
        preview_order = self.cb_client.preview_market_order_buy(
            product_id=self.product_id,
            quote_size=amount_as_string,
        )
        self.logger.info(f"buy preview => {json.dumps(preview_order, indent=4)}")
        if "errs" in preview_order and len(preview_order["errs"]) > 0:
            self.logger.warning(f"preview error: {preview_order['errs']}")
            errors = preview_order["errs"]
            successful = False

        preview_order_total = float(preview_order["order_total"])
        if preview_order_total > MAX_BUY_AMOUNT:
            self.logger.warning("preview order total too high: {preview_order_total}")
            errors.append("preview order total too high")
            successful = False

        value = float(preview_order["quote_size"])
        amount = float(preview_order["base_size"])

        real_order = None
        actualualized = False
        if self.enviorment == Enviorment.PRODUCTION and successful:
            real_order = self.cb_client.market_order_buy(
                client_order_id=str(uuid.uuid4()),
                product_id=self.product_id,
                quote_size=amount_as_string,
            )
            self.logger.info(f"buy order => {json.dumps(real_order, indent=4)}")
            if "errs" in real_order and len(real_order["errs"]) > 0:
                self.logger.warning(f"real order error: {real_order['errs']}")
            else:
                actualualized = True
                # the real order doesnt contain the quote size or base size, so we use the preview order

        decision = BuyDecision(
            context=context,
            amount=amount,
            value=value,
            preview_result=preview_order,
            trade_result=real_order,
            actualualized=actualualized,
            is_successful=successful,
            errors=errors
        )
        return decision

    def place_sell_order(self, context: DecisionContext, buy_decsions_to_sell: [any]) -> Decision:
        self.logger.info(f"🚀 Placing SELL order for {self.asset_config.symbol}")
        amount_to_sell = float(0)
        value_at_purchase = float(0)
        for decision in buy_decsions_to_sell:
            amount_to_sell += float(decision["amount"])
            value_at_purchase += float(decision["value"])

        amount_as_string = "f{amount_to_sell:.4f}"
        self.logger.info(f"selling {amount_as_string} {self.asset_config.symbol}")
        successful = True
        errors = []
        value = 0.0
        amount = 0.0
        preview_order = self.cb_client.preview_market_order_sell(
            product_id=self.product_id,
            base_size=amount_as_string,
        )
        self.logger.info(f"sell preview => {json.dumps(preview_order, indent=4)}")
        if "errs" in preview_order and len(preview_order["errs"]) > 0:
            self.logger.warning(f"preview error: {preview_order['errs']}")
            errors = preview_order["errs"]
            successful = False

        preview_order_total = float(preview_order["order_total"])
        if preview_order_total > MAX_SELL_AMOUNT:
            self.logger.warning("preview order total too high: {preview_order_total}")
            errors.append("preview order total too high")
            successful = False
        
        value = float(preview_order["quote_size"])
        amount = float(preview_order["base_size"])

        real_order = None
        actualualized = False
        if self.enviorment == Enviorment.PRODUCTION and successful:
            real_order = self.cb_client.market_order_sell(
                client_order_id=str(uuid.uuid4()),
                product_id=self.product_id,
                base_size=amount_as_string,
            )
            self.logger.info(f"sell order => {json.dumps(real_order, indent=4)}")
            if "errs" in real_order and len(real_order["errs"]) > 0:
                self.logger.warning(f"real order error: {real_order['errs']}")
            else:
                actualualized = True
                # the real order doesnt contain the quote size or base size, so we use the preview order

        profit = value - value_at_purchase
        self.logger.info(f"sell order profit: {profit}")
        decision = SellDecision(
            context=context,
            amount=amount,
            value=value,
            buy_amount=amount_to_sell,
            buy_value=value_at_purchase,
            profit_usd=profit,
            protit_asset_amount=profit / float(context.price),
            linked_buy_decisions=[decision["uuid"] for decision in buy_decsions_to_sell],
            preview_result=preview_order,
            trade_result=real_order,
            actualualized=actualualized,
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

    ENV = os.getenv("ENV")
    if ENV is None and config is not None:
        ENV = config["ENV"]
    assert ENV, "ENV is required"
    ENV = Enviorment(ENV.lower())  # Use .upper() to match the case of enum members

    cb_client = RESTClient(api_key=API_KEY, api_secret=API_SECRET)
    mongo_client = MongoClient(MONGO_URI)

    cb_accounts = get_cb_accounts(cb_client)
    cash_account = next((account for account in cb_accounts if account["currency"] == USD_SYMBOL), None)
    if cash_account is None:
        raise Exception(f"❌ could not find account for {USDC_SYMBOL}")
    cash_account_id = cash_account["uuid"]
    assets = parse_config(cb_accounts)

    while True:
        for asset_config in assets:
            transaction_id = uuid.uuid4()
            trxId = str(transaction_id)
            logger = setup_logger(trxId)
            decisionMaker = DecisionMaker(
                logger,
                ENV,
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