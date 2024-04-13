from collections import defaultdict

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
    # Read the file and split the content into blocks
    with open(f'pairings/{asset}_results.txt', 'r') as file:
        content = file.read()

    blocks = content.strip().split('\n\n')
    # print(blocks[0])
    # print('------------------')

    # Initialize dictionaries to store counts and averages
    sell_counts = defaultdict(int)
    lot_times = {}

    # Parse each block and update the dictionaries
    for block in blocks:
        lines = block.split('\n')
        buy_threshold = int(lines[0].split(':')[1].split('%')[0])
        sell_threshold = int(lines[0].split(':')[2].split('%')[0])
        sell_count = int(float(lines[3].split(': ')[1].split()[0]))
        lot_time = float(lines[4].split(': ')[1].split()[0].replace('%', ''))

        # print(f"Buy Threshold: {buy_threshold}, Sell Threshold: {sell_threshold}, Sell Count: {sell_count}, Lot Time: {lot_time}")

        sell_counts[(buy_threshold, sell_threshold)] += sell_count
        if (buy_threshold, sell_threshold) not in lot_times or lot_time < lot_times[(buy_threshold, sell_threshold)]:
            lot_times[(buy_threshold, sell_threshold)] = lot_time

    # Find the buy and sell thresholds with the most number of sells
    max_sell_pair = max(sell_counts, key=sell_counts.get)

    # Find the pairing with the lowest average lot time
    min_lot_time_pair = min(lot_times, key=lot_times.get)
    print(f"--- {asset} ---")
    print(f"Buy Threshold, Sell Threshold with most sells: {max_sell_pair}, {sell_counts[max_sell_pair]} sells")
    print(f"Pairing with lowest average lot time: {min_lot_time_pair}, {lot_times[min_lot_time_pair]:.2f} days")
    print()
