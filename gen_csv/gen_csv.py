import pandas as pd
import numpy as np
import sys

# 1. 24時間（5分刻み ＝ 288行）の時間軸を生成
dr = pd.date_range(start="2026-10-03 00:00:00", end="2026-10-03 23:55:00", freq="5min")
rows = len(dr)

# 2. 最大値1,000,000,000 (1G) までのランダムな2要素（整数）を生成
# 最小値は仮に0としています
metric_a = np.random.randint(0, 1000000000, size=rows)
metric_b = np.random.randint(0, 1000000000, size=rows)

# データフレームの作成
df = pd.DataFrame({
    "timestamp": dr,
    "metric_a": metric_a,
    "metric_b": metric_b
})

# CSV出力
FILE_NAME = sys.argv[1]
df.to_csv(FILE_NAME, index=False)

print(f"生成完了: {FILE_NAME} ({len(df)}行)")

