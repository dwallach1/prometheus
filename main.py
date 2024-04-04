import time
import os
import logging
from logging.handlers import RotatingFileHandler
import json
from enum import Enum
from coinbase.rest import RESTClient
from json import dumps
from dotenv import dotenv_values
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from datetime import datetime
import uuid
from decisions import Decision, DecisionType, Enviorment, BestMatchBelowThresholdDecision, BuyDecision, SellDecision
from assets import Asset

# https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getproduct

DEFAULT_CONFIG_PATH = "config.json"
USDC_SYMBOL = "USDC"
ONE_HOUR = 60 * 60
DECISION_BUFFER = ONE_HOUR
BUY_BUFFER = ONE_HOUR * 12

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
            usdc_account_id: str
        ):
        self.logger = logger
        self.logger.info(f"============ intializing new decision maker for {asset_config.symbol} in {enviormnet} ============")
        self.enviorment = enviormnet
        self.cb_client = cb_client
        self.mongo_client = mongo_client
        self.db_name = db_name
        self.collection_name = collection_name
        self.asset_config = asset_config
        self.usdc_account_id = usdc_account_id

      
    
    def get_buying_power(self) -> float:
        self.logger.info("Getting buying power")
        account = self.cb_client.get_account(self.usdc_account_id)
        usdc_balance = float(account["account"]["available_balance"]["value"])
        self.logger.info(f"USDC balance: {usdc_balance} as of {datetime.utcnow()}")
        return usdc_balance
    
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
            self.logger.warn(f"🛑 Not enough buying power")
        asset_balance = self.get_asset_balance()
        open_decisions = self.get_open_decisions()
        currency_pair = f"{self.asset_config.symbol}-USD"

        product = self.cb_client.get_product(currency_pair)
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


        if price_percentage_change_24h < self.asset_config.buy_price_percentage_change_threshold:
            self.logger.info(f"🟢 Price percentage change in 24h is above threshold [{price_percentage_change_24h}]")
            buy_buffer_check = self.check_buy_buffer(open_decisions)
            if not buy_buffer_check:
                self.logger.warn(f"🛑 Buy buffer not met")
            elif has_enough_buying_power:
                self.logger.info(f"🟢 Buying power is sufficient")
                open_buy_orders = self.make_buy_decisions()
                if len(open_buy_orders) < self.asset_config.max_open_buys:
                    self.logger.info(f"🚀 Placing buy order")
                    amount_to_buy = self.asset_config.amount_to_buy / current_price
                    # todo place buy order
                    # get the orderId and other relevant info from buy order
                    order_result = self.place_buy_order()
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
                    decision = Decision(
                        decision_type=DecisionType.TOO_MANY_OPEN_BUYS,
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
                self.logger.warn(f"🛑 Not enough buying power to place buy orders")
                decision = Decision(
                    decision_type=DecisionType.NOT_ENOUGH_BUYING_POWER,
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
        
        else:
            self.logger.info(f"🛑 Price percentage change in 24h does not meet buying threshold ({price_percentage_change_24h} > {self.asset_config.buy_price_percentage_change_threshold})")


        #  CHECK OPEN BUYS
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
                self.logger.info(f"🛑 No open buy orders to sell")
                # save BEST_MATCH_BELOW_THRESHOLD decision
                best_match_id = best_match["uuid"]
                decision = BestMatchBelowThresholdDecision(
                    enviorment=self.enviorment,
                    price=current_price,
                    symbol=self.asset_config.symbol,
                    asset_balance=asset_balance,
                    total_asset_value=total_asset_holdings_value,
                    usdc_balance=buying_power,
                    volume_24h=volume_24h,
                    volume_percentage_change_24h=volume_percentage_change_24h,
                    price_percentage_change_24h=price_percentage_change_24h,

                    percentage_delta=best_match_price_delta,
                    hypothetical_profit=best_match_hypothetical_profit,
                    associated_buy_decision=best_match_id
                )
                decisions.append(decision)
            else:
                amount_to_sell = float(0)
                value_accumulated = float(0)
                for decision in to_sell:
                    amount_to_sell += float(decision["amount"])
                    value_accumulated += float(decision["value"])
          
                    # place sell order
                    # get the orderId and other relevant info from sell order
                    order_result = self.place_sell_order()
                    sell_decision = SellDecision(
                        enviorment=self.enviorment,
                        price=current_price,
                        symbol=self.asset_config.symbol,
                        asset_balance=asset_balance,
                        total_asset_value=total_asset_holdings_value,
                        usdc_balance=buying_power,
                        volume_24h=volume_24h,
                        volume_percentage_change_24h=volume_percentage_change_24h,
                        price_percentage_change_24h=price_percentage_change_24h,
                        current_price=current_price,
                        cointbase_order=order_result,
                        amount=amount_to_sell,
                        value=amount_to_sell * current_price,
                        profit=(amount_to_sell * current_price) - value_accumulated,
                        linked_buy_decisions=[decision["uuid"] for decision in to_sell]
                    )
                    self.close_open_decisions(to_sell, sell_decision.uuid(), current_price)
                    decisions.append(sell_decision)
        
        if len(decisions) == 0:
            self.logger.info(f"no decisions made... generating a skip decision")
            # make SKIPPED decision
            decision = Decision(
                decision_type=DecisionType.SKIP,
                enviorment=self.enviorment,
                price=current_price,
                symbol=self.asset_config.symbol,
                asset_balance=asset_balance,
                total_asset_value=total_asset_holdings_value,
                usdc_balance=buying_power,
                volume_24h=volume_24h,
                volume_percentage_change_24h=volume_percentage_change_24h,
                price_percentage_change_24h=price_percentage_change_24h,
            )
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

    def place_order(self, action):
        """save to mongo for now. In the future, we will place orders on coinbase as well"""
        if self.enviorment == Enviorment.DRYRUN:
            self.logger.info(f"🛑 DRYRUN mode detected. Not placing any real orders")
            return
        #  conversion = self.cb_client.create_convert(from_currency=from_currency, to_currency=to_currency, amount=amount)
        pass
        
    def save_decisions_to_db(self, decisions: [Decision]):
        data = [d.get_attributes() for d in decisions]
        res = self.mongo_client[self.db_name][self.collection_name].insert_many(data)
        self.logger.info(f"Saved decisions to database {res}")

    def close_open_decisions(self, buy_decisions: [any], closed_by: str, current_price: float):
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
    print ("lodaded config ➡️ ", data)
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
        print (f"sucessfully loaded asset config {asset.name} (${asset.symbol})")
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
    
    # Check if the logger already has handlers to avoid duplicate logs
    if not logger.handlers:
        # Create a file handler which logs even debug messages
        # fh = RotatingFileHandler(f'logs/{trx_id}.log', maxBytes=1048576, backupCount=5)
        # fh.setLevel(logging.INFO)
        
        # Create console handler with a higher log level
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Create formatter and add it to the handlers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        # fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        # Add the handlers to the logger
        # logger.addHandler(fh)
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
    assert API_SECRET , "API_SECRET is required"
    
    cb_client = RESTClient(api_key=API_KEY, api_secret=API_SECRET)
    mongo_client = MongoClient(MONGO_URI)
    
    cb_accounts = get_cb_accounts(cb_client)
    usdc_account = next((account for account in cb_accounts if account["currency"] == USDC_SYMBOL), None)
    if usdc_account is None:
        raise Exception(f"❌ could not find account for {USDC_SYMBOL}")
    usdc_account_id = usdc_account["uuid"]
    assets = parse_config(cb_accounts)

    while True:
        for asset_config in assets:
            transaction_id = uuid.uuid4()
            trxId = str(transaction_id)
            logger = setup_logger(trxId)  
            decisionMaker = DecisionMaker(
                logger, 
                Enviorment.DRYRUN, 
                cb_client, 
                mongo_client,
                DB_NAME,
                DB_COLLECTION,
                asset_config,
                usdc_account_id
            )
            decisionMaker.compute_decisions()
            logger.info(f"finished making decisions :)")
        time.sleep(DECISION_BUFFER)

if __name__ == "__main__":
    main()