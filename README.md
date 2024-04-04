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

Tester:
```python
result = mongo_client[DB_NAME][DB_COLLECTION].find().sort("timestamp", -1).limit(1)
res = [r for r in result]
print (f"last decision: {res}")
last_decision_timestamp: datetime = res[0]["timestamp"]
now = datetime.utcnow()
print (f"decision_time: {last_decision_timestamp}, now: {now}")
time_delta = now - last_decision_timestamp
print (f"delta: {time_delta.total_seconds()}, buffer: {BUY_BUFFER}")
return
```