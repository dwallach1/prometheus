import time
import os
import logging
from logging.handlers import RotatingFileHandler
import json
from enum import Enum
import math
from coinbase.rest import RESTClient
from json import dumps
from dotenv import dotenv_values
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import uuid
from decisions import Decision, DecisionType, Enviorment
from assets import Asset

# https://docs.cloud.coinbase.com/advanced-trade-api/docs/welcome
# https://docs.cloud.coinbase.com/exchange/docs/welcome
# https://docs.cloud.coinbase.com/advanced-trade-api/docs/sdk-overview


# https://docs.cloud.coinbase.com/advanced-trade-api/reference/retailbrokerageapi_getproduct

DEFAULT_CONFIG_PATH = "config.json"
USDC_SYMBOL = "USDC"
ONE_HOUR = 60 * 60
DECISION_BUFFER = ONE_HOUR
east_coast_tz = ZoneInfo("America/New_York")


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
        self.logger.info(f"💰 USDC balance: {usdc_balance} as of {datetime.now(tz=east_coast_tz)}")
        return usdc_balance
    
    def get_asset_balance(self) -> float:
        self.logger.info("Getting asset balances")
        account = self.cb_client.get_account(self.asset_config.account_id)
        asset_balance = account["account"]["available_balance"]["value"]
        self.logger.info(f"💰 {self.asset_config.symbol} balance: {asset_balance} as of {datetime.now(tz=east_coast_tz)}")
        return asset_balance

    def compute_decisions(self):
        now = datetime.now(tz=east_coast_tz)
        self.logger.info(f"💡 computing decisions for {self.asset_config.symbol} at {now}")
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
        self.logger.info("asset prices: {}".format({
            'current_price': current_price,
            'price_percentage_change_24h': price_percentage_change_24h,
            'volume_percentage_change_24h': volume_percentage_change_24h,
            'volume_24h': volume_24h
        }))


        if price_percentage_change_24h > self.asset_config.price_percentage_change_threshold:
            self.logger.info(f"📈 Price percentage change in 24h is above threshold")
            if has_enough_buying_power:
                self.logger.info(f"💰 Buying power is sufficient")
                open_buy_orders = self.make_buy_decisions()
                if len(open_buy_orders) > 0:
                    self.logger.info(f"🚀 Placing buy orders")
                    for order in open_buy_orders:
                        self.place_order(order)
                else:
                    self.logger.info(f"🛑 No buy orders to place")
            else:
                self.logger.warn(f"🛑 Not enough buying power to place buy orders")
        
        else:
            self.logger.info(f"🛑 Price percentage change in 24h is below threshold ({price_percentage_change_24h} > {self.asset_config.price_percentage_change_threshold})")


        # decide if we should buy based on rate_of_change
        # if theres too many open decisions, dont buy but make TOO_MANY_OPEN_BUYS decision to record hypothetically would have bought

        # else create SKIP decision to record the rate of change we skipped on

        # if theres open buys, see if we shuold make sell decisions.
        # for each open buy, see if we can sell for > 10% profit. If so, make a SELL decision
        # if no SELLs but yes there are open buys, record a BEST_MATCH_BELOW_THRESHOLD and record the hypotheticall profit percentage

    def get_open_decisions(self) -> [Decision]:
        # print ("todo: get open decisions")
        return []

    def make_sell_decisions(self) -> [Decision]:
        pass

    def make_buy_decisions(self) -> Decision:
        open_buy_orders = []
        return open_buy_orders

    def place_order(self, action):
        """save to mongo for now. In the future, we will place orders on coinbase as well"""
        if self.enviorment == Enviorment.DRYRUN:
            print(f"🛑 DRYRUN mode detected. Not placing any real orders")
            return
        #  conversion = self.cb_client.create_convert(from_currency=from_currency, to_currency=to_currency, amount=amount)
        pass
        
    def save_decisions_to_db(self, decisions: [Decision]):
        client = MongoClient('your_mongodb_uri')
        db = client.your_database_name
        decisions_collection = db.decisions
        decision_data = self.get_attributes()  # Get all attributes of the instance
        decisions_collection.insert_one(decision_data)
        print(f"Saved {self.decision_type} decision to database.")


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
            float(asset["price_percentage_change_threshold"]),
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
            logger.info(f"🥂 finished making decisions :)")
        time.sleep(DECISION_BUFFER)

if __name__ == "__main__":
    main()