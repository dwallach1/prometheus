import os
import pandas as pd
import matplotlib.pyplot as plt
import random

start_year = 2015
# ADA. AVAX, BTC, ETH, LINK, SOL, UNI, XRP, LTC, MATIC
# needs to have a file in historical_price_data/ with the name of the asset
assets = [
    "LINK",
    "BTC",
    "ETH",
    "ADA",
    "AVAX",
    "SOL",
    "ALGO",
    "DOGE",
    "MATIC"
]

for asset in assets:
    file = open(f"pairings/{asset}_results.txt", "w")
    df = pd.read_csv(f'historical_price_data/{asset}-USD.csv', index_col='Date', parse_dates=True)
    df['daily_change'] = df['Close'].pct_change()
    drop_windows = df[abs(df['daily_change']) >= 0.05][df['daily_change'] < 0]

    for buy_threshold in range(5, 26):
        for sell_threshold in range(10, 26):
            open_buys = []
            sell_events = []
            for i, row in drop_windows.iterrows():
                start_date = i
                end_date = df.loc[i:].head(1).index[0]        # Hypothetical buy of 500 USD
                buy_price = df.loc[i, 'Close']
                open_buys.append((i, buy_price, 500))

            for i, row in df.iterrows():
                for buy in open_buys[:]:
                    buy_date, buy_price, buy_amount = buy
                    if (row['Close'] - buy_price) / buy_price >= sell_threshold / 100 and (i - buy_date).days >= 1:
                        sell_ymin = random.uniform(0, 0.5)  # Random y-axis start position between 0 and 50% of the chart height
                        sell_ymax = random.uniform(0.5, 1)  # Random y-axis end position between 50% and 100% of the chart height
                        sell_color = f'#{random.randint(0, 0xFFFFFF):06x}'  # Random color
                        sell_date = i
                        sell_price = row['Close']
                        profit_pct = (sell_price - buy_price) / buy_price
                        profit_usd = buy_amount * profit_pct
                        sell_events.append((buy_date, sell_date, profit_pct, profit_usd))
                        open_buys.remove(buy)

            total_drop = df.loc[drop_windows.index]['daily_change'].sum()
            num_drop_windows = len(drop_windows)
            avg_drop_percentage = total_drop / num_drop_windows
            average_lot_time = sum([(sell_date - buy_date).days for buy_date, sell_date, _, _ in sell_events]) / len(sell_events)
            average_profit_percentage = sum([profit_pct for _, _, profit_pct, _ in sell_events]) / len(sell_events)

            print(f"[ {asset} ] Buy Threshold: {buy_threshold}%, Sell Threshold: {sell_threshold}%")
            print(f"Number of 24-hour windows with at least 5% price drop: {len(drop_windows)}")
            print(f"The average drop window percentage is: {avg_drop_percentage:.2%}")
            print(f"Number of successful sell events: {len(sell_events)}")
            print(f"The average lot time is: {average_lot_time:.2f} days")
            print(f"The average profit percentage is: {average_profit_percentage:.2%}")
            print()

            file.write(f"[ {asset} ] Buy Threshold: {buy_threshold}%, Sell Threshold: {sell_threshold}%\n")
            file.write(f"Number of 24-hour windows with at least 5% price drop: {len(drop_windows)}\n")
            file.write(f"The average drop window percentage is: {avg_drop_percentage:.2%}\n")
            file.write(f"Number of successful sell events: {len(sell_events)}\n")
            file.write(f"The average lot time is: {average_lot_time:.2f} days\n")
            file.write(f"The average profit percentage is: {average_profit_percentage:.2%}\n")
            file.write("\n")

    file.close()

print("Done!")
