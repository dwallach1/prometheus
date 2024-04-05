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

Example Market PREVIEW buy ($10 USD worth of BTC)
```python
cb_client.preview_market_order_buy("BTC-USD", "10")
```
response =>
```json
{
    "order_total": "10.00000000000000004545",
    "commission_total": "0.05469915464942814545",
    "errs": [],
    "warning": [],
    "quote_size": "9.9453008453505719",
    "base_size": "0.0001465019262741",
    "best_bid": "67878.27",
    "best_ask": "67885.12",
    "is_max": false,
    "order_margin_total": "0",
    "leverage": "0",
    "long_leverage": "0",
    "short_leverage": "0",
    "slippage": "0.0000000000002152"
}
```

Example Market buy response (success) ($500 USD worth of SOL)
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

Example Market PREVIEW sell (0.0001 BTC for USD)
```python
cb_client.preview_market_order_sell("BTC-USD", "0.0001")
```
response =>
```json
{
    "order_total": "6.7447079505",
    "commission_total": "0.0373010495",
    "errs": [],
    "warning": [],
    "quote_size": "6.782009",
    "base_size": "0.0001",
    "best_bid": "67820.09",
    "best_ask": "67825.33",
    "is_max": false,
    "order_margin_total": "0",
    "leverage": "0",
    "long_leverage": "0",
    "short_leverage": "0",
    "slippage": "0"
}
```

Example Market sell response (success) (0.0005 BTC for USD)
```json
{
    "success": true,
    "failure_reason": "UNKNOWN_FAILURE_REASON",
    "order_id": "595979f7-50b4-4b51-af4e-f644286bb63f",
    "success_response": {
        "order_id": "595979f7-50b4-4b51-af4e-f644286bb63f",
        "product_id": "BTC-USD",
        "side": "SELL",
        "client_order_id": "27309299-76b8-4401-9161-2692fbe22ada"
    },
    "order_configuration": {
        "market_market_ioc": {
            "base_size": "0.0005"
        }
    }
}
```