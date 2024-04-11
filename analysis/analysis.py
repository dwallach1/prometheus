import pandas as pd
import matplotlib.pyplot as plt
import random
import warnings
warnings.filterwarnings("ignore", category=UserWarning, message="Boolean Series key will be reindexed to match DataFrame index")
warnings.filterwarnings("ignore", category=FutureWarning, message="The default fill_method='pad' in Series.pct_change is deprecated and will be removed in a future version.")

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
]

for asset in assets:
    years = ["ALL", "2015", "2016", "2017", "2018", "2019", "2020", "2021", "2022", "2023", "2024"]
    file = open(f"results/{asset}_results.txt", "w")
    for year in years:
        df = pd.read_csv(f'historical_price_data/{asset}-USD.csv', index_col='Date', parse_dates=True)
        if year != "ALL":
            try:
                df = df.loc[f'{year}']
            except KeyError:
                print(f"No data available for {asset} in {year}. Skipping...")
                continue
        if df.empty:
            print(f"No data available for {asset} in {start_year}. Skipping...")
            continue
        df['daily_change'] = df['Close'].pct_change()
        drop_windows = df[abs(df['daily_change']) >= 0.05][df['daily_change'] < 0]

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(df.index, df['Close'])

        # Draw boxes for the 24-hour drop windows
        open_buys = []
        sell_events = []

        for i, row in drop_windows.iterrows():
            start_date = i
            end_date = df.loc[i:].head(1).index[0]
            ax.axvspan(start_date, end_date, alpha=0.3, color='red')

            # Hypothetical buy of 500 USD
            buy_price = df.loc[i, 'Close']
            open_buys.append((i, buy_price, 500))

        # Check for sell opportunities and plot them
        for i, row in df.iterrows():
            for buy in open_buys[:]:
                buy_date, buy_price, buy_amount = buy
                if (row['Close'] - buy_price) / buy_price >= 0.12 and (i - buy_date).days >= 1:
                    # Sell the buy
                    sell_ymin = random.uniform(0, 0.5)  # Random y-axis start position between 0 and 50% of the chart height
                    sell_ymax = random.uniform(0.5, 1)  # Random y-axis end position between 50% and 100% of the chart height
                    sell_color = f'#{random.randint(0, 0xFFFFFF):06x}'  # Random color
                    ax.axvspan(buy_date, i, alpha=0.3, ymin=sell_ymin, ymax=sell_ymax, color=sell_color)
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

        print(f"[ {asset} {year} ]")
        print(f"Number of 24-hour windows with at least 5% price drop: {len(drop_windows)}")
        print(f"The average drop window percentage is: {avg_drop_percentage:.2%}")
        print(f"Number of successful sell events: {len(sell_events)}")
        print(f"The average lot time is: {average_lot_time:.2f} days")
        print(f"The average profit percentage is: {average_profit_percentage:.2%}")
        print()

        file.write(f"[ {asset} {year} ]\n")
        file.write(f"Number of 24-hour windows with at least 5% price drop: {len(drop_windows)}\n")
        file.write(f"The average drop window percentage is: {avg_drop_percentage:.2%}\n")
        file.write(f"Number of successful sell events: {len(sell_events)}\n")
        file.write(f"The average lot time is: {average_lot_time:.2f} days\n")
        file.write(f"The average profit percentage is: {average_profit_percentage:.2%}\n")
        file.write("\n")

        ax.set_title(f'{asset} Price Chart w Trades {year}')
        ax.set_xlabel('Date')
        ax.set_ylabel('Price (USD)')
        # plt.show()
        plt.savefig(f"imgs/{asset}_{year}.png", dpi=300)

    file.close()

print("Done!")
