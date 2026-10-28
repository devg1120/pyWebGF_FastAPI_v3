import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime, timedelta

TOPDIR = "./test3"

def make_day_data(YYYY,MM,DD,SWITCH ,DIR, PORT):
   FILE_NAME = f"{DIR}/{PORT}.csv"

   # 引数チェック（CSVファイル名が指定されていない場合はデフォルト名を使用）
   #FILE_NAME = sys.argv[1] if len(sys.argv) > 1 else "snmp_traffic_highly_random.csv"
   
   # 1. 24時間（5分刻み ＝ 288行）の時間軸を生成
   dr = pd.date_range(start="2026-10-03 00:00:00", end="2026-10-03 23:55:00", freq="5min")
   dr = pd.date_range(start=f"{YYYY}-{MM}-{DD} 00:00:00", end=f"{YYYY}-{MM}-{DD} 23:55:00", freq="5min")
   rows = len(dr)
   
   # 2. 時間帯に応じたベース波形の作成 (正午12:00をピークにする)
   hours = dr.hour + dr.minute / 60.0
   peak_center = 12.0
   peak_width = 3.5
   time_weight = np.exp(-((hours - peak_center) ** 2) / (2 * (peak_width ** 2)))
   time_weight = np.maximum(time_weight, 0.05)
   
   # 3. 複数のランダム要素の生成
   # ① 細かいノイズ（常時発生する小さな揺らぎ: ±15%）
   micro_noise_in = np.random.uniform(0.85, 1.15, size=rows)
   micro_noise_out = np.random.uniform(0.85, 1.15, size=rows)
   
   # ② マクロな変動（数十分〜数時間単位で波が上下するネットワークのゆらぎ）
   # サイン波をランダムに重ね合わせて、予測しにくい中規模なうねりを作ります
   macro_wave = (
       np.sin(hours * 2.0) * 0.15 + 
       np.cos(hours * 5.0) * 0.10 + 
       np.sin(hours * 0.5) * 0.05
   )
   # 変動幅（0.7〜1.3倍程度）にスケーリング
   macro_noise_in = 1.0 + macro_wave + np.random.normal(0, 0.05, size=rows)
   macro_noise_out = 1.0 + macro_wave + np.random.normal(0, 0.05, size=rows)
   
   # ③ 突発的なスパイク（大容量ファイルのダウンロードやバックアップによる一時的な跳ね上がり）
   # 3%の確率で、通常の1.5倍〜2.5倍のトラフィックが瞬間的に発生
   spike_in = np.where(np.random.rand(rows) < 0.03, np.random.uniform(1.5, 2.5, size=rows), 1.0)
   spike_out = np.where(np.random.rand(rows) < 0.03, np.random.uniform(1.5, 2.5, size=rows), 1.0)
   
   # 4. SNMPトラフィックデータの合成
   MAX_BYTES_SEC = 100_000_000  # 約800Mbpsベース
   MAX_BYTES_SEC = 1_000_000_000  # 約800Mbpsベース
   
   # ベースの山形 × マクロ変動 × ミクロノイズ × 突発スパイク
   bytes_in = MAX_BYTES_SEC * time_weight * macro_noise_in * micro_noise_in * spike_in
   bytes_out = (MAX_BYTES_SEC * 0.3) * time_weight * macro_noise_out * micro_noise_out * spike_out
   
   # 1Gbps（125,000,000 バイト/秒）を上限としてクリッピング（溢れ防止）
   bytes_in = np.clip(bytes_in, 0, 125_000_000).astype(int)
   bytes_out = np.clip(bytes_out, 0, 125_000_000).astype(int)
   
   # データフレームの作成
   
   # --- 修正後：5分間（300秒）の合計トラフィックを算出して累積和（cumsum）をとる ---
   # 1秒あたりのバイト数(レート)を5分間(300秒)の総バイト数に変換してから積み上げます
   
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
   
   print(f"生成完了: {FILE_NAME} ({len(df)}行)")

def make_port_data(YYYY,MM,DD, SWITCH):
    ports = [
             "Port1",
             "Port2",
             "Port3",
             "Port4",
             "Port5",
             "Port6",
             "Port7",
             "Port8",
             "Port9",
             "Port10",
             "Port11",
             "Port12",
             "Port13",
             "Port14",
             "Port15",
             ]
    data_path = f"{TOPDIR}/{YYYY}{MM}/{DD}/{SWITCH}"
    os.makedirs(data_path, exist_ok=True)

    for PORT in ports:
        make_day_data(YYYY,MM,DD,SWITCH , data_path, PORT)

def make_switch_data(YYYY,MM,DD):
    switchs = [
             "SWITCH_1",
             "SWITCH_2",
             "SWITCH_3",
             "SWITCH_4",
             ]
    for SWITCH in switchs:
        make_port_data(YYYY,MM,DD,SWITCH)


def main():
    # 1. 開始日と終了日を定義
    start_str = "20260601"
    end_str = "20260831"
    
    # 2. 文字列を datetime オブジェクトに変換
    start_date = datetime.strptime(start_str, "%Y%m%d")
    end_date = datetime.strptime(end_str, "%Y%m%d")
    
    # 3. ループ処理で1日ずつ進めながら YYYYMMDD 形式で出力
    current_date = start_date
    while current_date <= end_date:
        #print(current_date.strftime("%Y%m%d"))
        yyyymmdd = current_date.strftime("%Y%m%d")
        yyyy = yyyymmdd[0:4]
        mm   = yyyymmdd[4:6]
        dd   = yyyymmdd[6:8]
        print(yyyy, mm, dd)
        make_switch_data(yyyy, mm, dd)
        current_date += timedelta(days=1)  # 1日進める
    
def main_():
    make_switch_data("2026","09","10")
     

if __name__ == "__main__":
    main()
