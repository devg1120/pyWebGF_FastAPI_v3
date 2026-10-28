import os
import sys
import matplotlib.pyplot as plt
import pandas as pd


def plot_day_traffic(csv_path):
    # 1. ファイルの存在チェック
    if not os.path.exists(csv_path):
        print(f"エラー: ファイルが見つかりません -> {csv_path}")
        return

    # 2. CSVデータの読み込み
    # timestamp列を日時型としてパースします
    df = pd.read_csv(csv_path, parse_dates=["timestamp"])

    if df.empty:
        print("エラー: CSVデータが空です。")
        return

    # ファイル名からタイトル用の情報を取得
    file_name = os.path.basename(csv_path)

    # 3. 累積値（Octets）から5分間の差分（Bytes）を計算
    # diff()を使うことで、前の行との差分を計算します。先頭行はNaNになるので0で埋めます。
    df["diff_In"] = df["ifInOctets"].diff().fillna(0)
    df["diff_Out"] = df["ifOutOctets"].diff().fillna(0)

    # 💡 最初の5分間だけ累積の初期値がそのまま入って跳ね上がるのを防ぐため、
    # 　 生成スクリプトの数理モデルの仕様（初期値=0からスタート）に合わせて1行目を0にリセットします
    df.loc[0, "diff_In"] = 0
    df.loc[0, "diff_Out"] = 0

    # 4. バイト数から「Mbps (Megabits per second)」に変換
    # 5分間（300秒）の転送量から1秒あたりのビット数（bps）を出し、1,000,000で割ってMbpsにします
    # 計算式: Bytes * 8 (bit) / 300 (秒) / 1,000,000
    conversion_factor = 8 / 300 / 1_000_000
    df["Mbps_In"] = df["diff_In"] * conversion_factor
    df["Mbps_Out"] = df["diff_Out"] * conversion_factor

    # 5. グラフの描画設定
    plt.figure(figsize=(12, 6))

    # In（下り）と Out（上り）のラインをプロット
    plt.plot(
        df["timestamp"],
        df["Mbps_In"],
        label="Inbound (Traffic In)",
        color="tab:blue",
        linewidth=1.5,
    )
    plt.plot(
        df["timestamp"],
        df["Mbps_Out"],
        label="Outbound (Traffic Out)",
        color="tab:orange",
        linewidth=1.5,
    )

    # グラフの見た目の調整
    date_str = df["timestamp"].dt.strftime("%Y-%m-%d").iloc[0]
    plt.title(
        f"24-Hour Traffic Trend ({date_str}) - {file_name}",
        fontsize=14,
        fontweight="bold",
    )
    plt.xlabel("Time of Day (24H)", fontsize=11)
    plt.ylabel("Traffic Rate (Mbps)", fontsize=11)

    # 軸の範囲とグリッド線の設定
    plt.xlim(df["timestamp"].min(), df["timestamp"].max())
    plt.ylim(bottom=0)  # Y軸の下限を0に固定
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(loc="upper right", fontsize=10)

    # 時間軸（X軸）のフォーマットを「HH:MM」に整形
    plt.gca().xaxis.set_major_formatter(
        plt.matplotlib.dates.DateFormatter("%H:%M")
    )
    plt.gcf().autofmt_xdate()  # 文字重なりを防ぐために斜めにする

    # 6. グラフの表示（または画像保存）
    plt.tight_layout()
    plt.show()

    # もし画像ファイルとして自動保存したい場合は、plt.show() の代わりに以下を有効にしてください
    # save_path = csv_path.replace(".csv", ".png")
    # plt.savefig(save_path, dpi=150)
    # print(f"グラフを保存しました: {save_path}")


if __name__ == "__main__":
    # コマンドライン引数からCSVのパスを受け取る
    if len(sys.argv) < 2:
        print("使用方法: python plot_traffic.py <対象のCSVファイルパス>")
        print("例: python plot_traffic.py ./data/202611/01/SWITCH_1/Port1.csv")
    else:
        plot_day_traffic(sys.argv[1])
