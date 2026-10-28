import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime, timedelta

TOPDIR = "./test"

def make_day_data(YYYY, MM, DD, SWITCH, DIR, PORT):
   FILE_NAME = f"{DIR}/{PORT}.csv"

   # 日付オブジェクトを作成（曜日判定や異常値のシードに使用）
   date_obj = datetime(int(YYYY), int(MM), int(DD))
   day_of_week = date_obj.weekday()  # 0:月曜日 ~ 6:日曜日

   # 1. 24時間（5分刻み ＝ 288行）の時間軸を生成
   dr = pd.date_range(start=f"{YYYY}-{MM}-{DD} 00:00:00", end=f"{YYYY}-{MM}-{DD} 23:55:00", freq="5min")
   rows = len(dr)

   # 2. 時間帯に応じたベース波形の作成 (正午12:00をピークにする)
   hours = dr.hour + dr.minute / 60.0
   peak_center = 12.0
   peak_width = 3.5
   time_weight = np.exp(-((hours - peak_center) ** 2) / (2 * (peak_width ** 2)))
   time_weight = np.maximum(time_weight, 0.05)

   # 休日低減 (土日の場合はトラフィックを通常の35%に抑える)
   is_weekend = day_of_week in [5, 6]
   holiday_factor = 0.35 if is_weekend else 1.0
   time_weight = time_weight * holiday_factor

   # 3. 複数のランダム要素の生成
   # ① 細かいノイズ
   micro_noise_in = np.random.uniform(0.85, 1.15, size=rows)
   micro_noise_out = np.random.uniform(0.85, 1.15, size=rows)

   # ② マクロな変動
   macro_wave = (
       np.sin(hours * 2.0) * 0.15 +
       np.cos(hours * 5.0) * 0.10 +
       np.sin(hours * 0.5) * 0.05
   )
   macro_noise_in = 1.0 + macro_wave + np.random.normal(0, 0.05, size=rows)
   macro_noise_out = 1.0 + macro_wave + np.random.normal(0, 0.05, size=rows)

   # ③ 突発的なスパイク
   spike_in = np.where(np.random.rand(rows) < 0.03, np.random.uniform(1.5, 2.5, size=rows), 1.0)
   spike_out = np.where(np.random.rand(rows) < 0.03, np.random.uniform(1.5, 2.5, size=rows), 1.0)

   # ★修正：特定の曜日（例: 金曜日=4）だけ、完全にランダムな時間帯にバーストを発生させる
   # 初期値はバーストなし（1.0倍）
   burst_wave_in = np.ones(rows)
   burst_wave_out = np.ones(rows)

   # 曜日を設定（0:月, 1:火, 2:水, 3:木, 4:金, 5:土, 6:日）
   # 例として「金曜日」のみ発生させる場合 (複数指定したい場合は [4, 5] のように記述)
   TARGET_DAYS = [4]

   if day_of_week in TARGET_DAYS:
       # 開始時間を 0:00 〜 20:00 の間でランダムに決定
       burst_start = np.random.uniform(0.0, 20.0)
       # 継続時間を 1時間 〜 4時間 の間でランダムに決定
       burst_duration = np.random.uniform(1.0, 4.0)
       burst_end = burst_start + burst_duration

       # ランダムに決まった時間帯だけバースト（通常の1.8〜2.5倍）を発生させる
       is_burst_time = (hours >= burst_start) & (hours <= burst_end)
       burst_wave_in = np.where(is_burst_time, np.random.uniform(1.8, 2.5, size=rows), 1.0)
       burst_wave_out = np.where(is_burst_time, np.random.uniform(1.8, 2.5, size=rows), 1.0)

       # デバッグ確認用（必要に応じてコメントアウトしてください）
       # print(f"  [バースト設定] 開始:{burst_start:.2f}時, 継続:{burst_duration:.2f}時間")

   # 4. SNMPトラフィックデータの合成
   MAX_BYTES_SEC = 100_000_000  # 約800Mbpsベース

   # ベース波形 × 休日要因 × マクロ × ミクロ × スパイク × バースト
   bytes_in = MAX_BYTES_SEC * time_weight * macro_noise_in * micro_noise_in * spike_in * burst_wave_in
   bytes_out = (MAX_BYTES_SEC * 0.3) * time_weight * macro_noise_out * micro_noise_out * spike_out * burst_wave_out

   # 異常値データの盛り込み (日付やポートの組み合わせでランダムに発生)
   anomaly_roll = np.random.rand()
   anomaly_type = "NORMAL"

   if anomaly_roll < 0.01:
       anomaly_type = "SILENT_DROP"
       bytes_in = np.where((hours >= 10.0) & (hours <= 16.0), np.random.uniform(0, 1000, size=rows), bytes_in)
       bytes_out = np.where((hours >= 10.0) & (hours <= 16.0), np.random.uniform(0, 1000, size=rows), bytes_out)

   elif anomaly_roll < 0.02:
       anomaly_type = "FLOODING"
       bytes_in = np.where((hours >= 14.0) & (hours <= 14.5), 125_000_000, bytes_in)
       bytes_out = np.where((hours >= 14.0) & (hours <= 14.5), 125_000_000, bytes_out)

   # 1Gbps（125,000,000 バイト/秒）を上限としてクリッピング
   bytes_in = np.clip(bytes_in, 0, 125_000_000).astype(int)
   bytes_out = np.clip(bytes_out, 0, 125_000_000).astype(int)

   # データフレームの作成
   df = pd.DataFrame({
       "timestamp": dr,
       "index": 1,
       "name": SWITCH,
       "state": 1,
       "ifInOctets": pd.Series(bytes_in * 300).cumsum(),
       "ifOutOctets": pd.Series(bytes_out * 300).cumsum()
   })

   # CSV出力
   df.to_csv(FILE_NAME, index=False)

   # ログ出力
   if anomaly_type != "NORMAL":
       print(f"生成完了: {FILE_NAME} ({len(df)}行) [異常発生: {anomaly_type}]")
   elif day_of_week in TARGET_DAYS:
       print(f"生成完了: {FILE_NAME} ({len(df)}行) [バースト発生: {burst_start:.1f}h〜{burst_end:.1f}h]")
   else:
       print(f"生成完了: {FILE_NAME} ({len(df)}行)")

"""
def make_day_data(YYYY, MM, DD, SWITCH, DIR, PORT):
   FILE_NAME = f"{DIR}/{PORT}.csv"
   
   # 日付オブジェクトを作成（曜日判定や異常値のシードに使用）
   date_obj = datetime(int(YYYY), int(MM), int(DD))
   day_of_week = date_obj.weekday()  # 0:月曜日 ~ 6:日曜日
   
   # 1. 24時間（5分刻み ＝ 288行）の時間軸を生成
   dr = pd.date_range(start=f"{YYYY}-{MM}-{DD} 00:00:00", end=f"{YYYY}-{MM}-{DD} 23:55:00", freq="5min")
   rows = len(dr)
   
   # 2. 時間帯に応じたベース波形の作成 (正午12:00をピークにする)
   hours = dr.hour + dr.minute / 60.0
   peak_center = 12.0
   peak_width = 3.5
   time_weight = np.exp(-((hours - peak_center) ** 2) / (2 * (peak_width ** 2)))
   time_weight = np.maximum(time_weight, 0.05)
   
   # ★機能追加①: 休日低減 (土日の場合はトラフィックを通常の35%に抑える)
   is_weekend = day_of_week in [5, 6]
   holiday_factor = 0.35 if is_weekend else 1.0
   time_weight = time_weight * holiday_factor
   
   # 3. 複数のランダム要素の生成
   # ① 細かいノイズ
   micro_noise_in = np.random.uniform(0.85, 1.15, size=rows)
   micro_noise_out = np.random.uniform(0.85, 1.15, size=rows)
   
   # ② マクロな変動
   macro_wave = (
       np.sin(hours * 2.0) * 0.15 + 
       np.cos(hours * 5.0) * 0.10 + 
       np.sin(hours * 0.5) * 0.05
   )
   macro_noise_in = 1.0 + macro_wave + np.random.normal(0, 0.05, size=rows)
   macro_noise_out = 1.0 + macro_wave + np.random.normal(0, 0.05, size=rows)
   
   # ③ 突発的なスパイク（既存のロジック）
   spike_in = np.where(np.random.rand(rows) < 0.03, np.random.uniform(1.5, 2.5, size=rows), 1.0)
   spike_out = np.where(np.random.rand(rows) < 0.03, np.random.uniform(1.5, 2.5, size=rows), 1.0)
   
   # ★機能追加②: バーストトラフィック (例: 夜間 21:00〜23:00 に定期的なバックアップバーストが発生)
   # 特定の時間帯だけ、ベースラインに大きなトラフィックを上乗せします
   burst_wave_in = np.where((hours >= 21.0) & (hours <= 23.0), np.random.uniform(1.8, 2.3, size=rows), 1.0)
   burst_wave_out = np.where((hours >= 21.0) & (hours <= 23.0), np.random.uniform(1.8, 2.3, size=rows), 1.0)
   
   # 4. SNMPトラフィックデータの合成
   MAX_BYTES_SEC = 100_000_000  # 約800Mbpsベース
   
   # ベース波形 × 休日要因 × マクロ × ミクロ × スパイク × バースト
   bytes_in = MAX_BYTES_SEC * time_weight * macro_noise_in * micro_noise_in * spike_in * burst_wave_in
   bytes_out = (MAX_BYTES_SEC * 0.3) * time_weight * macro_noise_out * micro_noise_out * spike_out * burst_wave_out
   
   # ★機能追加③: 異常値データの盛り込み (日付やポートの組み合わせでランダムに発生)
   # テスト用に約2%の確率で、その日のそのポートに致命的な「異常」を発生させる
   anomaly_roll = np.random.rand()
   anomaly_type = "NORMAL"
   
   if anomaly_roll < 0.01:
       # パターンA: サイレント障害 (10:00 〜 16:00 の間、トラフィックがほぼゼロになる)
       anomaly_type = "SILENT_DROP"
       bytes_in = np.where((hours >= 10.0) & (hours <= 16.0), np.random.uniform(0, 1000, size=rows), bytes_in)
       bytes_out = np.where((hours >= 10.0) & (hours <= 16.0), np.random.uniform(0, 1000, size=rows), bytes_out)
       
   elif anomaly_roll < 0.02:
       # パターンB: フラッディング・DoS攻撃 (14:00から30分間、帯域限界まで張り付く)
       anomaly_type = "FLOODING"
       bytes_in = np.where((hours >= 14.0) & (hours <= 14.5), 125_000_000, bytes_in)
       bytes_out = np.where((hours >= 14.0) & (hours <= 14.5), 125_000_000, bytes_out)
   
   # 1Gbps（125,000,000 バイト/秒）を上限としてクリッピング
   bytes_in = np.clip(bytes_in, 0, 125_000_000).astype(int)
   bytes_out = np.clip(bytes_out, 0, 125_000_000).astype(int)
   
   # 確実にPandasのSeriesに変換した上で cumsum() を実行する
   df = pd.DataFrame({
       "timestamp": dr,
       "index": 1,
       "name": SWITCH,
       "state": 1,
       "ifInOctets": pd.Series(bytes_in * 300).cumsum(),
       "ifOutOctets": pd.Series(bytes_out * 300).cumsum()
   })
   
   # CSV出力
   df.to_csv(FILE_NAME, index=False)
   
   # ログに異常パターンの発生を出力できるように変更
   if anomaly_type != "NORMAL":
       print(f"生成完了: {FILE_NAME} ({len(df)}行) [異常発生: {anomaly_type}]")
   else:
       print(f"生成完了: {FILE_NAME} ({len(df)}行)")
"""

# 以下の関数(make_port_data, make_switch_data, main)は提供コードのまま動作します
def make_port_data(YYYY,MM,DD, SWITCH):
    ports = [f"Port{i}" for i in range(1, 16)] # 記述をスッキリさせました
    data_path = f"{TOPDIR}/{YYYY}{MM}/{DD}/{SWITCH}"
    os.makedirs(data_path, exist_ok=True)

    for PORT in ports:
        make_day_data(YYYY,MM,DD,SWITCH , data_path, PORT)

def make_switch_data(YYYY,MM,DD):
    switchs = ["SWITCH_1", "SWITCH_2", "SWITCH_3", "SWITCH_4"]
    for SWITCH in switchs:
        make_port_data(YYYY,MM,DD,SWITCH)

def main():
    start_str = "20260601"
    end_str = "20260831"
    
    start_date = datetime.strptime(start_str, "%Y%m%d")
    end_date = datetime.strptime(end_str, "%Y%m%d")
    
    current_date = start_date
    while current_date <= end_date:
        yyyymmdd = current_date.strftime("%Y%m%d")
        yyyy = yyyymmdd[0:4]
        mm   = yyyymmdd[4:6]
        dd   = yyyymmdd[6:8]
        print(yyyy, mm, dd)
        make_switch_data(yyyy, mm, dd)
        current_date += timedelta(days=1)

if __name__ == "__main__":
    main()
