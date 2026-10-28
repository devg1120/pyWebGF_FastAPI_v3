import glob
import os
import re
import sys
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_switch_traffic(switch_dir_path):
    # 1. 指定されたディレクトリの存在チェック
    if not os.path.exists(switch_dir_path):
        print(f"エラー: ディレクトリが見つかりません -> {switch_dir_path}")
        return

    # 2. ディレクトリ内の全ポートCSVファイルを取得
    # 提供コードの仕様「{DI}_Port1.csv」などにマッチするファイルを検索
    csv_files = glob.glob(os.path.join(switch_dir_path, "*_Port*.csv"))

    if not csv_files:
        print(
            f"エラー: 指定されたディレクトリ内にポートCSVファイルが見つかりません。"
        )
        return

    # ポート番号順（Port1, Port2, ... Port15）に綺麗に並び替えるためのソート
    def extract_port_num(filepath):
        match = re.search(r"Port(\d+)\.csv$", filepath)
        return int(match.group(1)) if match else 0

    csv_files.sort(key=extract_port_num)

    num_files = len(csv_files)
    print(f"発見したポート数: {num_files} 件 のグラフを生成します。")

    # 3. サブプロットの配置（レイアウト）を自動決定
    # 例：15ポートなら 「5行 × 3列」 のグリッドにする
    cols = 3
    rows = int(np.ceil(num_files / cols))

    # 画面サイズをポート数に応じて調整 (1画面に収まるように大きめに設定)
    fig, axes = plt.subplots(
        rows, cols, figsize=(18, 3.5 * rows), sharex=True, sharey=True
    )
    axes = axes.flatten()  # 多次元配列を1次元化してループしやすくする

    # 4. 各CSVファイルを読み込んでプロット
    for i, csv_path in enumerate(csv_files):
        ax = axes[i]
        file_name = os.path.basename(csv_path)
        port_label = file_name.replace(".csv", "")  # グラフの見出し用

        # データ読み込み
        df = pd.read_csv(csv_path, parse_dates=["timestamp"])

        if df.empty:
            ax.text(
                0.5,
                0.5,
                "No Data",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            continue

        # 累積値（Octets）から5分間の差分（Bytes）を計算
        df["diff_In"] = df["ifInOctets"].diff().fillna(0)
        df["diff_Out"] = df["ifOutOctets"].diff().fillna(0)
        df.loc[0, "diff_In"] = 0
        df.loc[0, "diff_Out"] = 0

        # Mbpsに変換 (Bytes * 8 / 300秒 / 1,000,000)
        conversion_factor = 8 / 300 / 1_000_000
        df["Mbps_In"] = df["diff_In"] * conversion_factor
        df["Mbps_Out"] = df["diff_Out"] * conversion_factor

        # サブプロットに描画
        ax.plot(
            df["timestamp"],
            df["Mbps_In"],
            label="In",
            color="tab:blue",
            alpha=0.8,
        )
        ax.plot(
            df["timestamp"],
            df["Mbps_Out"],
            label="Out",
            color="tab:orange",
            alpha=0.8,
        )

        # 各サブプロットの装飾
        ax.set_title(port_label, fontsize=12, fontweight="bold")
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.set_xlim(df["timestamp"].min(), df["timestamp"].max())
        ax.set_ylim(bottom=0)

        # X軸（時間）の間引き表示とフォーマット（4時間刻み）
        ax.xaxis.set_major_formatter(
            plt.matplotlib.dates.DateFormatter("%H:%M")
        )

        # 凡例は最初の1つのグラフだけに表示（画面がごちゃつくのを防ぐため）
        if i == 0:
            ax.legend(loc="upper right", fontsize=9)

    # 5. 使わなかった余分なサブプロット枠を非表示にする
    for j in range(i + 1, len(axes)):
        fig.delaxes(axes[j])

    # 全体タイトルの設定（パスの末尾からスイッチ名や日付を抽出）
    dir_titles = [x for x in switch_dir_path.split("/") if x]
    title_suffix = (
        f" - {' / '.join(dir_titles[-3:])}" if len(dir_titles) >= 3 else ""
    )

    fig.suptitle(
        f"Switch Ports Traffic Monitor (Mbps){title_suffix}",
        fontsize=16,
        fontweight="bold",
        y=0.99,
    )

    # グラフ同士の重なりを防ぐ自動調整
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法: python plot_switch_subplot.py <対象のスイッチディレクトリパス>")
        print(
            "例: python plot_switch_subplot.py ./data/202611/01/SWITCH_1"
        )
    else:
        plot_switch_traffic(sys.argv[1])
