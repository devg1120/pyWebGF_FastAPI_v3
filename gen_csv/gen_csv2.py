import pandas as pd
import numpy as np
import sys

# 引数チェック（CSVファイル名が指定されていない場合はデフォルト名を使用）
FILE_NAME = sys.argv[1] if len(sys.argv) > 1 else "snmp_traffic_noon_peak.csv"

# 1. 24時間（5分刻み ＝ 288行）の時間軸を生成
dr = pd.date_range(start="2026-10-03 00:00:00", end="2026-10-03 23:55:00", freq="5min")
rows = len(dr)

# 2. 時間帯に応じたベース波形の作成 (正午12:00をピークにする)
# 時間（0〜23.91）を計算
hours = dr.hour + dr.minute / 60.0

# 正午（12.0）を中心としたガウス分布（正規分布）の形状で山を作成
peak_center = 12.0
peak_width = 3.5   # 8:00と18:00にピークの半分〜1/3程度まで落ちるなだらかな山に設定
time_weight = np.exp(-((hours - peak_center) ** 2) / (2 * (peak_width ** 2)))

# 深夜〜早朝の最低ライン（ベーストラフィック）として0.05(5%)を確保
time_weight = np.maximum(time_weight, 0.05)

# 3. SNMPトラフィックデータの生成（最大1Gbps = 125,000,000 バイト/秒 相当）
MAX_BYTES_SEC = 100_000_000  # 約800Mbpsを上限の目安とする

# ランダムなノイズ（0.8 〜 1.2の倍率）
noise_in = np.random.uniform(0.8, 1.2, size=rows)
noise_out = np.random.uniform(0.8, 1.2, size=rows)

# In（ダウンロード側：正午に最高ピーク）
bytes_in = MAX_BYTES_SEC * time_weight * noise_in

# Out（アップロード側：一般的にInより少なめ、正午に連動して上昇）
bytes_out = (MAX_BYTES_SEC * 0.3) * time_weight * noise_out

# 整数型（int）に変換
bytes_in = bytes_in.astype(int)
bytes_out = bytes_out.astype(int)

# データフレームの作成
df = pd.DataFrame({
    "timestamp": dr,
    "ifInOctets_rate": bytes_in,
    "ifOutOctets_rate": bytes_out
})

# CSV出力
df.to_csv(FILE_NAME, index=False)

print(f"生成完了: {FILE_NAME} ({len(df)}行)")

