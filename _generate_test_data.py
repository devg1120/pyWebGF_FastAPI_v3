import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import json

BASE_DIR = "./gen_csv/month_data_build/test"
TARGET_YM = "202606"
TARGET_DD = "01"
SWITCH_NAME = "SWITCH_1"

output_dir = os.path.join(BASE_DIR, TARGET_YM, TARGET_DD, SWITCH_NAME)
os.makedirs(output_dir, exist_ok=True)

start_time = datetime(2026, 6, 1, 8, 0)
end_time = datetime(2026, 6, 1, 18, 55)
time_indices = []
current = start_time
while current <= end_time:
    time_indices.append(current)
    current += timedelta(minutes=5)

num_records = len(time_indices)

# 平坦なベーストラフィック (3Mbps)
np.random.seed(42)
base_traffic = np.full(num_records, 3_000_000.0) + np.random.normal(0, 50000, num_records)

def generate_cumulative_data(traffic_array):
    bytes_array = (traffic_array * 300) / 8
    return np.cumsum(bytes_array)

# 1. Port01: 完全な一瞬のトゲ (13:00に 60Mbps のスパイク、それ以外は綺麗に3Mbps)
traffic_spike = base_traffic.copy()
traffic_spike[60] = 60_000_000.0

pd.DataFrame({
    "日時": [t.strftime("%Y-%m-%d %H:%M:%S") for t in time_indices],
    "INDEX": 1, "NAME": "Port01", "STATUS": "Up",
    "項目A": generate_cumulative_data(traffic_spike).astype(np.int64), "項目B": 0
}).to_csv(os.path.join(output_dir, "Port01.csv"), index=False, encoding="utf-8")

# 2. Port02: 綺麗な長時間のバースト山 (15:00~16:00の1時間、30Mbpsを高止まり維持)
traffic_burst = base_traffic.copy()
traffic_burst[84:96] = 30_000_000.0

pd.DataFrame({
    "日時": [t.strftime("%Y-%m-%d %H:%M:%S") for t in time_indices],
    "INDEX": 2, "NAME": "Port02", "STATUS": "Up",
    "項目A": generate_cumulative_data(traffic_burst).astype(np.int64), "項目B": 0
}).to_csv(os.path.join(output_dir, "Port02.csv"), index=False, encoding="utf-8")

# 3. Port03: 全体的な絶対値の最高ピーク (17:30に 80Mbps の最大外れ値)
traffic_global = base_traffic.copy()
traffic_global[114:116] = 80_000_000.0

pd.DataFrame({
    "日時": [t.strftime("%Y-%m-%d %H:%M:%S") for t in time_indices],
    "INDEX": 3, "NAME": "Port03", "STATUS": "Up",
    "項目A": generate_cumulative_data(traffic_global).astype(np.int64), "項目B": 0
}).to_csv(os.path.join(output_dir, "Port03.csv"), index=False, encoding="utf-8")

# info.json
with open(os.path.join(output_dir, "info.json"), "w", encoding="utf-8") as f:
    json.dump({"switch_name": SWITCH_NAME, "description": "AI Test Data"}, f)

print("🎉 テストデータを極端なメリハリパターンで再生成しました！")
