import json
from datetime import datetime

# Read the ndjson file
with open('log.ndjson', 'r') as file:
    logs = [json.loads(line) for line in file]

# Sort logs based on message time
sorted_logs = sorted(logs, key=lambda x: datetime.strptime(x['message'].split(' - ')[0], '%Y-%m-%d %H:%M:%S,%f'))

# Print sorted logs
for log in sorted_logs:
    print(log['message'])
