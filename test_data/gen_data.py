import pandas as pd
import numpy as np
import sys
import os
import json
import re
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta  # pip install python-dateutil または標準ライブラリ代替

import argparse


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
   spike_in = np.where(np.random.rand(rows) < 0.03, np.random.uniform(1.2, 1.5, size=rows), 1.0)
   spike_out = np.where(np.random.rand(rows) < 0.03, np.random.uniform(1.2, 1.5, size=rows), 1.0)

   # ④ 金曜日のバースト波形
   burst_wave_in = np.ones(rows)
   burst_wave_out = np.ones(rows)
   TARGET_DAYS = [4]

   if day_of_week in TARGET_DAYS:
       burst_start = np.random.uniform(0.0, 20.0)
       burst_duration = np.random.uniform(1.0, 4.0)
       burst_end = burst_start + burst_duration
       is_burst_time = (hours >= burst_start) & (hours <= burst_end)
       burst_wave_in = np.where(is_burst_time, np.random.uniform(1.5, 2.0, size=rows), 1.0)
       burst_wave_out = np.where(is_burst_time, np.random.uniform(1.5, 2.0, size=rows), 1.0)

   # ─── 💡 【修正点】ピーク値を800Mbpsに固定する数理モデリング ───
   TARGET_PEAK_BPS = 800_000_000   # 800 Mbps
   TARGET_PEAK_BYTES = TARGET_PEAK_BPS / 8  # 100,000,000 バイト/秒

   # 一度、ノイズや波形をすべて掛け合わせた「生の相対トレンド」を計算する
   raw_trend_in = time_weight * macro_noise_in * micro_noise_in * spike_in * burst_wave_in
   raw_trend_out = time_weight * macro_noise_out * micro_noise_out * spike_out * burst_wave_out

   # 1日のうちの最大値（ピーク）を取得
   current_max_in = np.max(raw_trend_in)

   # 💡 最大値が「ちょうど100,000,000バイト（800Mbps）」になるように逆算して全体をスケーリング！
   # これにより、休日や平日、ノイズの乗り方に左右されず、1日の最大頂点が必ず800Mbpsに固定されます
   bytes_in = (raw_trend_in / current_max_in) * TARGET_PEAK_BYTES

   # Out（上り）は、通常はInの35%程度のピークを持つように同様にスケール
   bytes_out = (raw_trend_out / current_max_in) * (TARGET_PEAK_BYTES * 0.35)

   # 休日低減 (土日の場合は、最大ピークが通常の35%（280Mbps）に抑えられるように後から適用)
   is_weekend = day_of_week in [5, 6]
   if is_weekend:
       bytes_in = bytes_in * 0.35
       bytes_out = bytes_out * 0.35

   # ─── 4. 異常値データの盛り込み ───
   anomaly_roll = np.random.rand()
   anomaly_type = "NORMAL"

   if anomaly_roll < 0.01:
       anomaly_type = "SILENT_DROP"
       bytes_in = np.where((hours >= 10.0) & (hours <= 16.0), np.random.uniform(0, 1000, size=rows), bytes_in)
       bytes_out = np.where((hours >= 10.0) & (hours <= 16.0), np.random.uniform(0, 1000, size=rows), bytes_out)

   elif anomaly_roll < 0.02:
       anomaly_type = "FLOODING"
       # FLOODING（回線輻輳）の時は、1Gbps（125MB/s）の限界値まで跳ね上がらせる
       bytes_in = np.where((hours >= 14.0) & (hours <= 14.5), 125_000_000, bytes_in)
       bytes_out = np.where((hours >= 14.0) & (hours <= 14.5), 125_000_000, bytes_out)

   # 1Gbps（125,000,000 バイト/秒）を上限としてクリッピング
   #bytes_in = np.clip(bytes_in, 0, 125_000_000).astype(int)
   #bytes_out = np.clip(bytes_out, 0, 125_000_000).astype(int)

   bytes_in = np.clip(bytes_in, 0, 125_000_000).astype(np.int64)
   bytes_out = np.clip(bytes_out, 0, 125_000_000).astype(np.int64)

   # データフレームの作成
   
   df = pd.DataFrame({
       "timestamp": dr,
       "index": 1,
       "name": SWITCH,
       "state": 1,
       "ifInOctets": (pd.Series(bytes_in) * 300).cumsum(),  # 5分間(300秒)の累積
       "ifOutOctets": (pd.Series(bytes_out) * 300).cumsum()
   })
   """
   df = pd.DataFrame({
       "日時": dr,                             # 1列目 (main.py の df.columns[0] に直結)
       "INDEX": 1,                            # 2列目
       "NAME": SWITCH,                         # 3列目
       "STATUS": 1,                           # 4列目
       "項目A": (pd.Series(bytes_in) * 300).cumsum(),   # 5列目 (★重要: 確実にこれが項目Aに割り当たります)
       "項目B": (pd.Series(bytes_out) * 300).cumsum()  # 6列目 (★重要: 確実にこれが項目Bに割り当たります)
   })
   """

   # CSV出力
   df.to_csv(FILE_NAME, index=False)

   # ログ出力
   if anomaly_type != "NORMAL":
       print(f"生成完了: {FILE_NAME} ({len(df)}行) [異常発生: {anomaly_type}]")
   elif day_of_week in TARGET_DAYS:
       print(f"生成完了: {FILE_NAME} ({len(df)}行) [バースト発生: {burst_start:.1f}h〜{burst_end:.1f}h]")
   else:
       print(f"生成完了: {FILE_NAME} ({len(df)}行) [Peak: {np.max(bytes_in)*8/1_000_000:.1f} Mbps]")


def make_day_data_(YYYY, MM, DD, SWITCH, DIR, PORT):
   #info = { "desc": "DESC_" + PORT, "speed" : 10000 , "etc" : "abcde"}
   #json_str = json.dumps(info, ensure_ascii=False)
   #with open(DIR + "/info.json","w") as o:
   #     print(json_str, file=o) 

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


# 以下の関数(make_port_data, make_switch_data, main)は提供コードのまま動作します
def make_port_data(TOPDIR, YYYY,MM,DD, SWITCH):
    DI = TOPDIR.replace('.','').replace('/','')
    #ports = [f"Port{i}" for i in range(1, 16)] # 記述をスッキリさせました
    ports = [f"{DI}_Port{i}" for i in range(1, 16)] # 記述をスッキリさせました
    data_path = f"{TOPDIR}/{YYYY}{MM}/{DD}/{SWITCH}"
    os.makedirs(data_path, exist_ok=True)

    for PORT in ports:
        make_day_data(YYYY,MM,DD,SWITCH , data_path, PORT)


    infos = {}
    for PORT in ports:
       info = { "desc": "DESC_" + SWITCH + "_" + PORT + "_" + MM + DD, "speed" : 10000 , "etc" : "abcde"}
       infos[PORT] = info
    json_str = json.dumps(infos, ensure_ascii=False)
    with open(data_path + "/info.json","w") as o:
        print(json_str, file=o) 


def make_switch_data(TOPDIR, YYYY,MM,DD, switchs):
    for SWITCH in switchs:
        make_port_data(TOPDIR, YYYY,MM,DD,SWITCH)

def validate_yyyymmdd__(date_str):
    """yyyymmdd形式の文字列をチェックし、datetimeオブジェクト（または文字列）を返す"""
    try:
        # パースに成功すれば正しい日付
        valid_date = datetime.strptime(date_str, "%Y%m%d")
        # そのままオブジェクトとして使いたい場合は valid_date を返す
        # 元の文字列のまま保持したい場合は date_str を返す
        return date_str
    except ValueError:
        # argparseの型エラーとして認識させる
        raise argparse.ArgumentTypeError(
            f"'{date_str}' は無効な日付です。yyyymmdd 形式で指定してください。"
        )



def validate_yyyymmdd(date_str):
    # 1. 厳密に「数字8桁」であるかを正規表現でチェック
    #    (月: 01-12, 日: 01-31 の範囲にあるかも簡易チェック)
    if not re.match(r"^\d{4}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])$", date_str):
        raise argparse.ArgumentTypeError(
            f"'{date_str}' は無効な形式です。4桁の年、2桁の月、2桁の日（例: 20260123）で指定してください。"
        )

    # 2. 存在しない日付（例: 20260230）をチェック
    try:
        datetime.strptime(date_str, "%Y%m%d")
        return date_str
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"'{date_str}' はカレンダー上に存在しない日付です。"
        )

def validate_period(period_str):
    try:
      _p = period_str.split(":")
      _str1 = validate_yyyymmdd(_p[0])
      _str2 = validate_yyyymmdd(_p[1])
      return period_str
    except ValueError :
        print("ValueError")
        sys.exit()

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', required=True, help="generate data dirname")
    parser.add_argument('--pastsize', type=int , default = 1,  help="past months size ")
    parser.add_argument('--period', type=validate_period, help="yyyymmdd:yyyymmdd")
    parser.add_argument('--exec',  action="store_true", help="real exec")
    args = parser.parse_args()

    topdir= args.dir
    start_str = "20261101"
    end_str = "20261121"

    if args.period:
        print("period", args.period)
        _p = args.period.split(':')
        start_str = _p[0]
        end_str   = _p[1]
        #print("  start", start_str)
        #print("    end",   end_str)
    else:
      if args.pastsize:
         print("pastsize", args.pastsize)
         pastsize = args.pastsize
         start = datetime.now().strftime("%Y%m%d")

         today = datetime.now()
         #ago = today - relativedelta(years=pastsize)
         ago = today - relativedelta(months=pastsize)

         # yyyymmdd形式に変換
         end_str   = today.strftime("%Y%m%d")
         start_str = ago.strftime("%Y%m%d")


    switchs = ["SWITCH_1", "SWITCH_2", "SWITCH_3", "SWITCH_4"]
    
    if topdir == ',' or  topdir == './' or topdir == '/':
          print("topdir error!", topdir)
          sys.exit()

    if os.path.isdir(topdir):
          print("topdir exist!!", topdir)
          sys.exit()


    print("dir", topdir)
    print("start", start_str)
    print("  end",   end_str)
    if not args.exec:
       print("-----------")
       sys.exit()

    #sys.exit()

    start_date = datetime.strptime(start_str, "%Y%m%d")
    end_date = datetime.strptime(end_str, "%Y%m%d")
    
    current_date = start_date
    while current_date <= end_date:
        yyyymmdd = current_date.strftime("%Y%m%d")
        yyyy = yyyymmdd[0:4]
        mm   = yyyymmdd[4:6]
        dd   = yyyymmdd[6:8]
        print(yyyy, mm, dd)
        make_switch_data(topdir, yyyy, mm, dd, switchs)
        current_date += timedelta(days=1)

if __name__ == "__main__":
    main()
