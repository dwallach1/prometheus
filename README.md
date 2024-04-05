#  PROMETHEUS

>In summary, Prometheus was a prominent Titan figure in Greek mythology known for defying the gods to benefit humanity, an act for which he was severely punished, but which cemented his legacy as a champion and benefactor of humankind. 

Example asset config (config.json)
```json
{
    "assets": [
        {
            "name": "Bitcoin",
            "symbol": "BTC",
            "amount_to_buy_usd": 500,
            "buy_price_percentage_change_threshold": 5.0,
            "sell_price_percentage_change_threshold": 10.0,
            "max_open_buys": 5
        },
        {
            "name": "Ethereum",
            "symbol": "ETH",
            "amount_to_buy_usd": 500,
            "buy_price_percentage_change_threshold": 5.0,
            "sell_price_percentage_change_threshold": 10.0,
            "max_open_buys": 5
        }
    ]
}
```


Example Market buy response (success)
```json
{
    "success": true,
    "failure_reason": "UNKNOWN_FAILURE_REASON",
    "order_id": "30300590-9040-4f58-a0c0-a53cf97a3adf",
    "success_response": {
        "order_id": "30300590-9040-4f58-a0c0-a53cf97a3adf",
        "product_id": "SOL-USD",
        "side": "BUY",
        "client_order_id": "b3ff6bc3-8cb7-4347-bd2a-bd6c15985604"
    },
    "order_configuration": {
        "market_market_ioc": {
            "quote_size": "500.0000"
        }
    }
}
```