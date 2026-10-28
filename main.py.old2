import warnings
# 将来の仕様変更に関する警告（FutureWarning）をすべて無視する
warnings.simplefilter(action='ignore', category=FutureWarning)

import io
import glob
import os
import platform
import json
import traceback
from typing import Optional
from socket import gethostname

import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import matplotlib.dates as mdates
from natsort import natsorted

# FastAPI関連
import urllib.parse
from fastapi import FastAPI, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.concurrency import run_in_threadpool

# Merlion 関連のインポート
#from merlion.utils import TimeSeries
#from merlion.models.anomaly.isolation_forest import IsolationForest, IsolationForestConfig
#from merlion.models.anomaly.stat_threshold import StatThreshold, StatThresholdConfig
#from merlion.post_process.threshold import AggregateAlarms

# 💡 外部ファイルから異常検知マネージャーをインポート
from detectors import AnomalyDetectors

# ─── OS自動判定による日本語文字化け対策 ───
matplotlib.use("Agg")
current_os = platform.system()
if current_os == "Windows":
    matplotlib.rcParams["font.family"] = "Yu Gothic"
elif current_os == "Linux":
    # 環境（CentOS等）にインストールされているフォント名を左から優先検索
    matplotlib.rcParams["font.family"] = ["VL Gothic", "IPAGothic", "IPAPGothic", "sans-serif"]
else:
    matplotlib.rcParams["font.family"] = "sans-serif"
matplotlib.rcParams["axes.unicode_minus"] = False

app = FastAPI()
print("HOSTNAME:", gethostname())

templates = Jinja2Templates(directory="templates")
templates.env.filters["urldecode"] = urllib.parse.unquote

# ─── 💡 【マルチ化】動的切替用のマッピング辞書 ───
BASE_DIRS = {
    #"default": "./test_data/test1",
    "test1": "./test_data/test1",
    "test2": "./test_data/test2",
    "test3": "./test_data/test3",
    "test4": "./test_data/test4",
    # "customer_a": "./gen_csv/month_data_build/customer_a", # 必要に応じて追加
}
DEFAULT_DIR = "test1"

def get_default_base_id() -> str:
    """ホスト名に基づきデフォルトのbase_idを決定するロジック"""
    #if gethostname() == "mokka21":
    #    return "mokka21_snmp"
    #return "default"
    print("DEFAULT_DIR")
    return DEFAULT_DIR

def get_base_dir_path(base_id: Optional[str] = None) -> str:
    """指定されたbase_idから実際の物理ディレクトリパスを安全に解決する"""
    if not base_id or base_id not in BASE_DIRS:
        base_id = get_default_base_id()
    return BASE_DIRS[base_id]

DASHBOARD_REGISTRY = []
# ─── 💡 BASE_DIRを引数ベースで動的に受けるように修正 ───
def get_date_tree(base_id: Optional[str] = None):
    """指定されたデータソースの階層構造（年月/日）をスキャンして辞書型で返す"""
    date_tree = {}
    actual_base = get_base_dir_path(base_id)
    
    yyyymm_dirs = sorted([d for d in glob.glob(os.path.join(actual_base, "*")) if os.path.isdir(d)])
    for ymd in yyyymm_dirs:
        ym_name = os.path.basename(ymd)
        dd_dirs = sorted([d for d in glob.glob(os.path.join(ymd, "*")) if os.path.isdir(d)])
        dd_list = [os.path.basename(d) for d in dd_dirs]
        if dd_list:
            date_tree[ym_name] = dd_list
    return date_tree


# 💡 FastAPIからレスポンスを操作するために Response をインポートに明示的に含めます（上部になければ自動で適用されます）
from fastapi import Response

@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    base_id: Optional[str] = None,
    mode: str = "single",
    yyyymm: str = "",
    dd: str = "",
    start_dd: str = "",
    end_dd: str = "",
    switch: str = "",
    cols: int = 2,
    start_hour: int = 8,
    end_hour: int = 18,
    yesterday: str = "2026-10-22",
    today: str = "2026-10-23",
):
    # ─── 1. 監視ルート(base_id)の安全な解決 ───
    if not base_id:
        base_id = get_default_base_id()
    actual_base = get_base_dir_path(base_id)
    
    # 選択された環境から日付ツリーをフレッシュに取得
    date_tree = get_date_tree(base_id)
    if not date_tree:
        return HTMLResponse(content=f"<h1>エラー: ディレクトリが見つかりません。({base_id})</h1>", status_code=500)

    # ─── 2. 対象月(yyyymm)の確定ロジック ───
    available_yyyymm = list(date_tree.keys())
    # 画面から届いた yyyymm が空、または現在の環境に存在しない場合は最新（末尾）をセット
    if not yyyymm or yyyymm == "" or yyyymm not in date_tree:
        yyyymm = available_yyyymm[-1] if available_yyyymm else ""

    # ─── 3. 【重要】確定した月をベースに、有効な日付リストを「ここで確実に生成」 ───
    available_dds = date_tree.get(yyyymm, [])
    if not available_dds:
        return HTMLResponse(content=f"<h1>エラー: 有効な日がありません。</h1>", status_code=500)

    # ─── 4. 対象日(dd)の確定ロジック ───
    # 画面から届いた dd が空、または現在の月リストの中に存在しない場合は最新（末尾）をセット
    if not dd or dd == "" or str(dd) not in available_dds:
        dd = available_dds[-1] if available_dds else ""

    # ─── 5. ディレクトリ配下のスイッチ・CSVファイルを再検索 ───
    selected_date = f"{yyyymm}/{dd}"
    date_dir = os.path.join(actual_base, selected_date)
    available_switches = sorted([os.path.basename(d) for d in glob.glob(os.path.join(date_dir, "*")) if os.path.isdir(d)])

    # スイッチが指定されていない、またはリストにない場合のフォールバック
    if not switch or switch not in available_switches:
        switch = available_switches[0] if available_switches else ""

    csv_filenames = []
    info_dic = {}
    if switch:
        target_dir = os.path.join(actual_base, selected_date, switch)
        csv_files = sorted(glob.glob(os.path.join(target_dir, "*.csv")))
        csv_filenames = natsorted([os.path.basename(f) for f in csv_files])
        info_json_path = os.path.join(target_dir, "info.json")
        if os.path.exists(info_json_path):
            with open(info_json_path, 'r', encoding='utf-8') as f:
                info_dic = json.load(f)

    # ─── 6. HTML（Jinja2）側へ、整合性を完全に合わせたコンテキストデータを引き渡す ───
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "base_ids": list(BASE_DIRS.keys()),     
            "selected_base_id": base_id,            
            "date_tree": date_tree, 
            "current_mode": mode,
            "selected_start_dd": start_dd, 
            "selected_end_dd": end_dd,
            
            # HTML側の変数判定（selected_yyyymm / selected_dd）へ確実にバインド
            "selected_yyyymm": yyyymm, 
            "selected_dd": dd, 
            "available_dds": available_dds,  # 👈 これでJinja2のループが絶対に破綻しません
            
            "switches": available_switches, 
            "selected_switch": switch, 
            "selected_cols": cols,
            
            # 時間の選択状態を維持
            "start_hour": int(start_hour), 
            "end_hour": int(end_hour), 
            
            "csv_filenames": csv_filenames,
            "info_dic": info_dic, 
            "registry": DASHBOARD_REGISTRY,
            "yesterday": yesterday,
            "today": today,
        }
    )

@app.get("/plot")
async def plot_graph(
    base_id: Optional[str] = None, # 💡 クエリパラメータを追加
    mode: str = "single", yyyymm: Optional[str] = None, dd: Optional[str] = None,
    switch: Optional[str] = None, filename: Optional[str] = None, cols: int = 2,
    start_hour: int = 8, end_hour: int = 18, desc: str = "", speed: str = "", start_dd: str = "", end_dd: str = "", 
):
    # 💡 パス解決
    actual_base = get_base_dir_path(base_id)

    fig_size = (14, 4.0) if cols == 1 else (6, 2.8) if cols == 4 else (8, 3.0)
    fig = Figure(figsize=fig_size)
    ax = fig.subplots()
    
    g_speed = ""
    if speed != "":
        g_speed = str(int(speed)//1000) + "Gbps"

    try:
        df_list = []
        
        # ─── 期間指定モード (range) ───
        if mode == "range" and start_dd and end_dd:
            start_date_obj = pd.to_datetime(start_dd.replace("/", "-"))
            end_date_obj = pd.to_datetime(end_dd.replace("/", "-"))
            dr = pd.date_range(start=start_date_obj, end=end_date_obj)
            
            for d in dr:
                ym_dir = d.strftime("%Y%m")
                d_single = str(d.day)        
                d_double = d.strftime("%d")  
                
                # 💡 actual_base を使用するように変更
                candidate_paths = [
                    os.path.join(actual_base, ym_dir, d_double, switch, filename),
                    os.path.join(actual_base, ym_dir, d_single, switch, filename),
                    os.path.join(actual_base, ym_dir, d_double, switch.upper(), filename),
                    os.path.join(actual_base, ym_dir, d_single, switch.upper(), filename),
                ]
                
                file_path = None
                for c_path in candidate_paths:
                    if os.path.exists(c_path):
                        file_path = c_path
                        break
                
                if file_path:
                    _df = await run_in_threadpool(pd.read_csv, file_path, engine="c")
                    if not _df.empty:
                        if len(_df.columns) >= 6:
                            _df.columns = ["日時", "INDEX", "NAME", "STATUS", "項目A", "項目B"] + list(_df.columns[6:])
                        elif len(_df.columns) >= 3:
                            _df.columns = ["日時", "項目A", "項目B"] + list(_df.columns[3:])
                        df_list.append(_df)

            if df_list:
                df = pd.concat(df_list, ignore_index=True)
            else:
                raise FileNotFoundError("データファイルが見つかりません。")

            start_time = start_date_obj + pd.Timedelta(hours=start_hour)
            end_time = end_date_obj + pd.Timedelta(hours=end_hour, minutes=55)
            x_label_text = f"{start_date_obj.strftime('%Y-%m-%d')} ～ {end_date_obj.strftime('%Y-%m-%d')}"
            x_tick_format = "%m/%d %H:%M"

        # ─── 通常単日モード (single) ───
        else:
            # 💡 actual_base を使用するように変更
            file_path = os.path.join(actual_base, yyyymm, dd, switch, filename)
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"ファイルなし: {yyyymm}/{dd}")

            df = await run_in_threadpool(pd.read_csv, file_path, engine="c")
            
            if len(df.columns) >= 6:
                df.columns = ["日時", "INDEX", "NAME", "STATUS", "項目A", "項目B"] + list(df.columns[6:])
            elif len(df.columns) >= 3:
                df.columns = ["日時", "項目A", "項目B"] + list(df.columns[3:])

            base_date = pd.to_datetime(f"{yyyymm[:4]}-{yyyymm[4:]}-{dd}").normalize()
            start_time = base_date + pd.Timedelta(hours=start_hour)
            end_time = base_date + pd.Timedelta(hours=end_hour, minutes=55)
            x_label_text = f"{yyyymm[:4]}-{yyyymm[4:6]}-{dd}"
            x_tick_format = "%H:%M"

        # ─── データ整形・ソート ───
        df["日時"] = pd.to_datetime(df["日時"], format="mixed", errors='coerce')
        df = df.dropna(subset=["日時"]).sort_values("日時").reset_index(drop=True)

        # ─── ギャップ・日またぎガード ───
        time_diff_sec = df["日時"].diff().dt.total_seconds()
        is_missing = (time_diff_sec > 330) | (time_diff_sec < 0)

        df["差分A"] = df["項目A"].diff().clip(lower=0)
        df.loc[is_missing, "差分A"] = None  
        df["bps_A"] = (df["差分A"] * 8) / 300

        if "項目B" in df.columns:
            df["差分B"] = df["項目B"].diff().clip(lower=0)
            df.loc[is_missing, "差分B"] = None
            df["bps_B"] = (df["差分B"] * 8) / 300
        else:
            df["bps_B"] = 0

        df_filtered = df[(df["日時"] >= start_time) & (df["日時"] <= end_time)]
        
        fig.set_facecolor("#f0f0f0")
        ax.set_facecolor("#ffffff")

        # ─── 描画 ───
        if not df_filtered.empty:
            ax.fill_between(df_filtered["日時"], df_filtered["bps_A"], color="#00eb0c", alpha=0.9, label="In (bps)")
            ax.plot(df_filtered["日時"], df_filtered["bps_A"], color="#006600", linewidth=0.8)
            if "bps_B" in df_filtered.columns:
                ax.plot(df_filtered["日時"], df_filtered["bps_B"], color="#1000ff", linewidth=1.8, label="Out (bps)")
        else:
            ax.text(0.5, 0.5, "データがありません", ha="center", va="center", color="red")

        ax.grid(True, which="both", color="#cccccc", linestyle="-", linewidth=0.5)
        ax.set_xlim(start_time, end_time)
        ax.xaxis.set_major_formatter(mdates.DateFormatter(x_tick_format))
        if mode == "range":
           for label in ax.get_xticklabels():
               label.set_rotation(30)
               label.set_horizontalalignment("right")
        #"""
        max_val = max(df_filtered["bps_A"].max(), df_filtered["bps_B"].max()) if not df_filtered.empty else 0
        if max_val >= 2_000_000_000:
            MAX_BPS = 10_000_000_000
            ax.set_ylim(0, MAX_BPS)
            ax.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f"{x / 1_000_000_000:,.1f} G"))
            ax.set_ylabel("転送速度 (Gbps)")
            ax.tick_params(axis='y', colors="red")
        elif max_val >= 1_000_000_000:
            MAX_BPS = 2_000_000_000
            ax.set_ylim(0, MAX_BPS)
            ax.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f"{x / 1_000_000_000:,.1f} G"))
            ax.set_ylabel("転送速度 (Gbps)")
            ax.tick_params(axis='y', colors="#0080FF")
        else:
            MAX_BPS = 1_000_000_000
            ax.set_ylim(0, MAX_BPS)
            ax.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f"{x / 1_000_000_000:,.1f} G"))
            ax.set_ylabel("転送速度 (Gbps)")
        #"""
        """

        # ─── 💡 【main.py 修正箇所】Y軸の最大値制限と単位表示を Mbps ベースへ最適化 ───
        max_val = max(df_filtered["bps_A"].max(), df_filtered["bps_B"].max()) if not df_filtered.empty else 0
        
        if max_val >= 2_000_000_000:
            # 2Gbpsを超える本番データなどの場合のみ「G」表記にする
            MAX_BPS = 10_000_000_000
            ax.set_ylim(0, MAX_BPS)
            ax.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f"{x / 1_000_000_000:,.1f} G"))
            ax.set_ylabel("転送速度 (Gbps)")
            ax.tick_params(axis='y', colors="red")

        elif max_val >= 1_000_000_000:
            # 1Gbps超〜2Gbps未満の場合
            MAX_BPS = 2_000_000_000
            ax.set_ylim(0, MAX_BPS)
            ax.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f"{x / 1_000_000_000:,.1f} G"))
            ax.set_ylabel("転送速度 (Gbps)")
            ax.tick_params(axis='y', colors="#0080FF")

        else:
            # 💡 今回のターゲット（800Mbpsなど、1Gbps未満のデータ）
            # 上限を綺麗に「1,000 Mbps (1Gbps)」に設定し、目盛りを M (Mbps) 単位に統一します！
            MAX_BPS = 1_000_000_000  # 上限は 1,000M 固定
            ax.set_ylim(0, MAX_BPS)
            # 1,000,000 で割り算することで、目盛りを「200M」「400M」「600M」「800M」にします
            ax.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f"{x / 1_000_000:,.0f} M"))
            ax.set_ylabel("転送速度 (Mbps)") # 単位名も Mbps に変更
        """
        # ────────────────────────────────────────────────────────────────────────


        ax.get_yaxis().get_offset_text().set_visible(False)
        ax.set_title(f"[{base_id}] {switch}: {filename.replace('.csv', '')}  {g_speed}", fontsize=11, loc="left")
        ax.set_title(desc, fontsize=10, loc="right", color="#000000")
        ax.set_xlabel(x_label_text)

    except Exception as e:
        traceback.print_exc()
        ax.text(0.5, 0.5, f"Error: {type(e).__name__}", ha="center", va="center", color="red")

    fig.legend(bbox_to_anchor=(0.13, -0.09), loc='lower left', ncol=2, frameon=True, facecolor="#ffffff", edgecolor="#cccccc")
    plt.subplots_adjust(bottom=0.25)
    fig.tight_layout()

    img = io.BytesIO()
    await run_in_threadpool(fig.savefig, img, format="png", bbox_inches="tight", dpi=120)
    img.seek(0)
    fig.clear()
    return StreamingResponse(img, media_type="image/png")
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request, 
    base_id: Optional[str] = None, # 💡 追加
    mode: str = "single", yyyymm: str = "", dd: str = "",
    start_dd: str = "", end_dd: str = "", cols: int = 2, start_hour: int = 8, end_hour: int = 18,
):
    if not base_id:
        base_id = get_default_base_id()

    date_tree = get_date_tree(base_id) # 💡 引数追加
    available_yyyymm = list(date_tree.keys())
    if not yyyymm or yyyymm not in date_tree:
        yyyymm = available_yyyymm[-1] if available_yyyymm else "" 

    available_dds = date_tree.get(yyyymm, [])
    if not dd or dd not in available_dds:
        dd = available_dds[-1] if available_dds else ""  

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "base_ids": list(BASE_DIRS.keys()),     # 💡 追加
            "selected_base_id": base_id,            # 💡 追加
            "registry": DASHBOARD_REGISTRY, "date_tree": date_tree,
            "current_mode": mode, "selected_start_dd": start_dd, "selected_end_dd": end_dd,
            "selected_yyyymm": yyyymm, "selected_dd": dd, "available_dds": available_dds,
            "selected_cols": cols, "start_hour": start_hour, "end_hour": end_hour,
        }
    )


@app.post("/dashboard/add")
async def dashboard_add(
    yyyymm: str = Form(...), dd: str = Form(...), switch: str = Form(...), filename: str = Form(...), desc: str = Form(""),
    base_id: str = Form("default"), # 💡 フォーム受け入れを追加
):
    if yyyymm and dd and switch and filename:
        exists = any(i["yyyymm"] == yyyymm and i["dd"] == dd and i["switch"] == switch and i["filename"] == filename and i["desc"] == desc and i.get("base_id") == base_id for i in DASHBOARD_REGISTRY)
        if not exists:
            DASHBOARD_REGISTRY.append({"yyyymm": yyyymm, "dd": dd, "switch": switch, "filename": filename, "desc": desc, "base_id": base_id})
    return RedirectResponse(url=f"/?base_id={base_id}&mode=single&yyyymm={yyyymm}&dd={dd}&switch={switch}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/dashboard/delete")
async def dashboard_delete(index: int = Form(...), base_id: str = Form("default")):
    if 0 <= index < len(DASHBOARD_REGISTRY):
        DASHBOARD_REGISTRY.pop(index)
    return RedirectResponse(url=f"/dashboard?base_id={base_id}", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/anomaly_dashboard", response_class=HTMLResponse)
async def anomaly_dashboard(
    request: Request,
    base_id: Optional[str] = None, # 💡 追加
    start_dd: str = "",
    end_dd: str = "",
    switch: str = "",
    logic: str = "stat_threshold",  
    start_hour: int = 8,
    end_hour: int = 18,
):
    if not base_id:
        base_id = get_default_base_id()
    actual_base = get_base_dir_path(base_id)

    date_tree = get_date_tree(base_id) # 💡 引数追加
    csv_filenames = []

    available_switches = []  # 💡 プルダウン用のスイッチリストを初期化

    # ─── 💡 ディレクトリツリーから存在するスイッチ構造を動的に全スキャン ───
    # 開始日が指定されている場合はその日を重点探索、無ければ直近の全データから重複なくスイッチ名を抽出
    scan_date_dirs = []
    if start_dd:
        try:
            p_date = pd.to_datetime(start_dd)
            scan_date_dirs.append(os.path.join(actual_base, p_date.strftime("%Y%m"), p_date.strftime("%d")))
            scan_date_dirs.append(os.path.join(actual_base, p_date.strftime("%Y%m"), str(p_date.day)))
        except:
            pass

    # 指定がない、または見つからない場合は全体から直近のディレクトリを探索して補完
    for ym, dds in date_tree.items():
        if dds:
            scan_date_dirs.append(os.path.join(actual_base, ym, dds[-1])) # 最新の日

    # 実際に物理ディレクトリを覗いて配下のスイッチ名をリスト化
    switch_set = set()
    for d_dir in scan_date_dirs:
        if os.path.exists(d_dir):
            for d in glob.glob(os.path.join(d_dir, "*")):
                if os.path.isdir(d):
                    switch_set.add(os.path.basename(d))
    available_switches = sorted(list(switch_set))
    if not switch or switch not in available_switches:
        switch = available_switches[0] if available_switches else ""

    if switch and start_dd:
        try:
            parsed_date = pd.to_datetime(start_dd)
            ym_dir = parsed_date.strftime("%Y%m")
            d_single = str(parsed_date.day)
            d_double = parsed_date.strftime("%d")
            
            # 💡 actual_base を使用するように変更
            candidate_dirs = [
                os.path.join(actual_base, ym_dir, d_single, switch),
                os.path.join(actual_base, ym_dir, d_double, switch),
                os.path.join(actual_base, ym_dir, d_single, switch.upper()),
                os.path.join(actual_base, ym_dir, d_double, switch.upper()),
            ]
            
            target_dir = None
            for c_dir in candidate_dirs:
                if os.path.exists(c_dir):
                    target_dir = c_dir
                    break
                    
            if target_dir:
                switch = os.path.basename(target_dir)
                csv_files = sorted(glob.glob(os.path.join(target_dir, "*.csv")))
                csv_filenames = natsorted([os.path.basename(f) for f in csv_files])
        except Exception as e:
            print(f"[エラー] パス解決処理中に障害が発生しました: {e}")

    return templates.TemplateResponse(
        request=request,
        name="anomaly_dashboard.html",
        context={
            "base_ids": list(BASE_DIRS.keys()),     # 💡 追加
            "selected_base_id": base_id,            # 💡 追加
            "actual_base_dir": actual_base,   
            "date_tree": date_tree,
            "available_switches": available_switches,
            "selected_start_dd": start_dd,
            "selected_end_dd": end_dd,
            "selected_switch": switch,
            "logics": AnomalyDetectors.get_available_logics(),
            "selected_logic": logic,  
            "start_hour": start_hour,
            "end_hour": end_hour,
            "csv_filenames": csv_filenames,
        }
    )


@app.get("/plot_anomaly")
async def plot_anomaly(
    base_id: Optional[str] = None,
    mode: str = "range", yyyymm: Optional[str] = None, dd: Optional[str] = None,
    switch: Optional[str] = None, filename: Optional[str] = None, cols: int = 2,
    start_hour: int = 8, end_hour: int = 18, start_dd: str = "", end_dd: str = "",
    logic: str = "stat_threshold",
):
    actual_base = get_base_dir_path(base_id)

    fig_size = (14, 4.0) if cols == 1 else (6, 2.8) if cols == 4 else (8, 3.0)
    fig = Figure(figsize=fig_size)
    ax = fig.subplots()

    df_filtered = pd.DataFrame()

    try:
        df_list = []
        if start_dd and end_dd:
            dr = pd.date_range(start=start_dd, end=end_dd)
            for d in dr:
                file_path = os.path.join(actual_base, d.strftime("%Y%m"), d.strftime("%d"), switch, filename)
                if os.path.exists(file_path):
                    _df = await run_in_threadpool(pd.read_csv, file_path, engine="c")
                    if not _df.empty:
                        df_list.append(_df)

            if df_list:
                df = pd.concat(df_list, ignore_index=True)
            else:
                raise FileNotFoundError("データファイルが見つかりません。")

            start_time = pd.to_datetime(start_dd) + pd.Timedelta(hours=start_hour)
            end_time = pd.to_datetime(end_dd) + pd.Timedelta(hours=end_hour, minutes=55)
            x_label_text = f"{start_dd} ～ {end_dd}"
            x_tick_format = "%m/%d %H:%M"
        else:
            raise ValueError("期間指定が必要です。")

        if len(df.columns) >= 6:
            df.columns = ["日時", "INDEX", "NAME", "STATUS", "項目A", "項目B"] + list(df.columns[6:])
        elif len(df.columns) >= 3:
            df.columns = ["日時", "項目A", "項目B"] + list(df.columns[3:])

        df["日時"] = pd.to_datetime(df["日時"], format="mixed", errors='coerce')
        df = df.dropna(subset=["日時"])
        df = df[(df["日時"] >= start_time) & (df["日時"] <= end_time)]
        df = df.sort_values("日時").reset_index(drop=True)

        time_diff_sec = df["日時"].diff().dt.total_seconds()
        is_missing = time_diff_sec > 330

        df["差分A"] = df["項目A"].diff().clip(lower=0)
        df.loc[is_missing, "差过A"] = None

        df["bps_A"] = (df["差分A"] * 8) / 300
        df = df.dropna(subset=["bps_A"]).reset_index(drop=True)

        fig.set_facecolor("#f0f0f0")
        ax.set_facecolor("#ffffff")

        if not df.empty:
            df = df[~df["日時"].duplicated(keep='first')].reset_index(drop=True)

            max_points = 1000
            if len(df) > max_points:
                step = len(df) // max_points
                df_filtered = df.iloc[::step].copy().reset_index(drop=True)
            else:
                df_filtered = df.copy()

            # 通常のトラフィック線（緑色）をプロット
            ax.plot(df_filtered.index, df_filtered["bps_A"], color="#006600", linewidth=0.8, label="In (bps)")
            ax.fill_between(df_filtered.index, df_filtered["bps_A"], color="#00eb0c", alpha=0.4)

            # ─── 🧠 💡【外部ファイル化】ロジック呼び出しを1行に集約 ───
            # logic に応じたパーセンタイル閾値の自動決定
            percentile_val = 0.95 if logic == "burst_detector" else 0.98 if logic == "z_score_outlier" else 0.99

            # 外部モジュール（detectors.py）を実行して赤ドット（異常値）の行を取得
            anomalies = AnomalyDetectors.detect(logic, df_filtered, percentile_val)

            # グラフ左上に表示する日本語タイトルを外部定義から自動取得
            title_prefix = AnomalyDetectors.get_available_logics().get(logic, "【異常検知】")

            # 🔴 異常値ポイントを赤ドットでプロット
            if not anomalies.empty:
                ax.scatter(anomalies.index, anomalies["bps_A"], color="red", s=15, zorder=5, label="Anomaly")

            ax.set_xlim(0, len(df_filtered) - 1)
            tick_indices = [0, len(df_filtered)//4, len(df_filtered)//2, (len(df_filtered)*3)//4, len(df_filtered)-1]
            tick_labels = [df_filtered["日時"].iloc[i].strftime(x_tick_format) for i in tick_indices if i < len(df_filtered)]
            ax.set_xticks(tick_indices)
            ax.set_xticklabels(tick_labels, rotation=30, ha="right")
        else:
            ax.text(0.5, 0.5, "データがありません", ha="center", va="center", color="red")
            title_prefix = "【異常検知】"

        max_val = df_filtered["bps_A"].max() if not df_filtered.empty else 0
        if max_val >= 1_000_000:
            ax.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f"{x / 1_000_000:,.1f} M"))
            ax.set_ylabel("転送速度 (Mbps)")
        elif max_val >= 1_000:
            ax.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f"{x / 1_000:,.0f} K"))
            ax.set_ylabel("転送速度 (Kbps)")
        else:
            ax.get_yaxis().set_major_formatter(matplotlib.ticker.StrMethodFormatter("{x:,.0f}"))
            ax.set_ylabel("転送速度 (bps)")

        ax.set_title(f"{title_prefix} {switch}: {filename.replace('.csv', '')}", fontsize=11, loc="left", color="darkred")
        ax.set_xlabel(x_label_text)
    except Exception as e:
        traceback.print_exc()
        ax.text(0.5, 0.5, f"Error: {type(e).__name__}", ha="center", va="center", color="red")

    fig.legend(bbox_to_anchor=(0.13, -0.04), loc='lower left', ncol=2, frameon=True)
    plt.subplots_adjust(bottom=0.25)
    fig.tight_layout()

    img = io.BytesIO()
    await run_in_threadpool(fig.savefig, img, format="png", bbox_inches="tight", dpi=120)
    img.seek(0)
    fig.clear()
    return StreamingResponse(img, media_type="image/png")

"""
@app.get("/plot_anomaly")
async def plot_anomaly(
    base_id: Optional[str] = None,
    mode: str = "range", yyyymm: Optional[str] = None, dd: Optional[str] = None,
    switch: Optional[str] = None, filename: Optional[str] = None, cols: int = 2,
    start_hour: int = 8, end_hour: int = 18, start_dd: str = "", end_dd: str = "",
    logic: str = "stat_threshold",
):
    actual_base = get_base_dir_path(base_id)

    fig_size = (14, 4.0) if cols == 1 else (6, 2.8) if cols == 4 else (8, 3.0)
    fig = Figure(figsize=fig_size)
    ax = fig.subplots()

    df_filtered = pd.DataFrame()

    try:
        df_list = []
        if start_dd and end_dd:
            dr = pd.date_range(start=start_dd, end=end_dd)
            for d in dr:
                file_path = os.path.join(actual_base, d.strftime("%Y%m"), d.strftime("%d"), switch, filename)
                if os.path.exists(file_path):
                    _df = await run_in_threadpool(pd.read_csv, file_path, engine="c")
                    if not _df.empty:
                        df_list.append(_df)

            if df_list:
                df = pd.concat(df_list, ignore_index=True)
            else:
                raise FileNotFoundError("データファイルが見つかりません。")

            start_time = pd.to_datetime(start_dd) + pd.Timedelta(hours=start_hour)
            end_time = pd.to_datetime(end_dd) + pd.Timedelta(hours=end_hour, minutes=55)
            x_label_text = f"{start_dd} ～ {end_dd}"
            x_tick_format = "%m/%d %H:%M"
        else:
            raise ValueError("期間指定が必要です。")

        if len(df.columns) >= 6:
            df.columns = ["日時", "INDEX", "NAME", "STATUS", "項目A", "項目B"] + list(df.columns[6:])
        elif len(df.columns) >= 3:
            df.columns = ["日時", "項目A", "項目B"] + list(df.columns[3:])

        df["日時"] = pd.to_datetime(df["日時"], format="mixed", errors='coerce')
        df = df.dropna(subset=["日時"])
        df = df[(df["日時"] >= start_time) & (df["日時"] <= end_time)]
        df = df.sort_values("日時").reset_index(drop=True)

        time_diff_sec = df["日時"].diff().dt.total_seconds()
        is_missing = time_diff_sec > 330

        df["差分A"] = df["項目A"].diff().clip(lower=0)
        df.loc[is_missing, "差分A"] = None  

        df["bps_A"] = (df["差分A"] * 8) / 300
        df = df.dropna(subset=["bps_A"]).reset_index(drop=True)

        fig.set_facecolor("#f0f0f0")
        ax.set_facecolor("#ffffff")

        if not df.empty:
            df = df[~df["日時"].duplicated(keep='first')].reset_index(drop=True)

            max_points = 1000
            if len(df) > max_points:
                step = len(df) // max_points
                df_filtered = df.iloc[::step].copy().reset_index(drop=True)
            else:
                df_filtered = df.copy()

            # 通常のトラフィック線（緑色）をプロット
            ax.plot(df_filtered.index, df_filtered["bps_A"], color="#006600", linewidth=0.8, label="In (bps)")
            ax.fill_between(df_filtered.index, df_filtered["bps_A"], color="#00eb0c", alpha=0.4)

            # ─── 🧠 Merlionを完全に代替するPandas/NumPy異常検知ロジック ───
            anomalies = pd.DataFrame()

            if logic == "stat_threshold":
                title_prefix = "【異常検知: 直近急変重視】"
                # トラフィックの「前5分からの変化量（絶対値）」を計算
                df_filtered["diff_val"] = df_filtered["bps_A"].diff().abs().fillna(0)
                # 統計的な上位1%の急変（しきい値）を算出し、一定の通信量(10Mbps)以上の変動を検知
                threshold = df_filtered["diff_val"].quantile(0.99)
                anomalies = df_filtered[(df_filtered["diff_val"] >= threshold) & (df_filtered["diff_val"] > 10_000_000)]

            elif logic == "burst_detector":
                title_prefix = "【異常検知: 30分連続バースト重視】"
                # 30分間（5分×6点）の移動平均を計算
                df_filtered["rolling_mean"] = df_filtered["bps_A"].rolling(window=6, min_periods=1).mean()
                # 5分後の通信量が急落していないか確認するための先読みデータ
                df_filtered["next_bps"] = df_filtered["bps_A"].shift(-1).fillna(df_filtered["bps_A"])
                # 移動平均が上位5%かつ、現在も5分後も高負荷(15Mbps超)が維持されている点をバーストと判定
                threshold = df_filtered["rolling_mean"].quantile(0.95)
                anomalies = df_filtered[
                    (df_filtered["rolling_mean"] >= threshold) &
                    (df_filtered["bps_A"] > 15_000_000) &
                    (df_filtered["next_bps"] > 15_000_000)
                ]

            else:
                title_prefix = "【異常検知: 総合外れ値】"
                # 全体のトラフィックの平均値と標準偏差（σ）を使った統計的Zスコアモデル
                mean_bps = df_filtered["bps_A"].mean()
                std_bps = df_filtered["bps_A"].std()
                if std_bps > 0:
                    df_filtered["z_score"] = (df_filtered["bps_A"] - mean_bps) / std_bps
                else:
                    df_filtered["z_score"] = 0
                # 平均から2.55σ（概ね上位1%未満の外れ値）離れた高トラフィックを検知
                anomalies = df_filtered[(df_filtered["z_score"] > 2.55) & (df_filtered["bps_A"] > 20_000_000)]

            # 🔴 異常値ポイントを赤ドットでプロット
            if not anomalies.empty:
                ax.scatter(anomalies.index, anomalies["bps_A"], color="red", s=15, zorder=5, label="Anomaly")

            ax.set_xlim(0, len(df_filtered) - 1)
            tick_indices = [0, len(df_filtered)//4, len(df_filtered)//2, (len(df_filtered)*3)//4, len(df_filtered)-1]
            tick_labels = [df_filtered["日時"].iloc[i].strftime(x_tick_format) for i in tick_indices if i < len(df_filtered)]
            ax.set_xticks(tick_indices)
            ax.set_xticklabels(tick_labels, rotation=30, ha="right")
        else:
            ax.text(0.5, 0.5, "データがありません", ha="center", va="center", color="red")
            title_prefix = "【異常検知】"

        max_val = df_filtered["bps_A"].max() if not df_filtered.empty else 0
        if max_val >= 1_000_000:
            ax.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f"{x / 1_000_000:,.1f} M"))
            ax.set_ylabel("転送速度 (Mbps)")
        elif max_val >= 1_000:
            ax.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f"{x / 1_000:,.0f} K"))
            ax.set_ylabel("転送速度 (Kbps)")
        else:
            ax.get_yaxis().set_major_formatter(matplotlib.ticker.StrMethodFormatter("{x:,.0f}"))
            ax.set_ylabel("転送速度 (bps)")

        ax.set_title(f"{title_prefix} {switch}: {filename.replace('.csv', '')}", fontsize=11, loc="left", color="darkred")
        ax.set_xlabel(x_label_text)
    except Exception as e:
        traceback.print_exc()
        ax.text(0.5, 0.5, f"Error: {type(e).__name__}", ha="center", va="center", color="red")

    fig.legend(bbox_to_anchor=(0.13, -0.04), loc='lower left', ncol=2, frameon=True)
    plt.subplots_adjust(bottom=0.25)
    fig.tight_layout()

    img = io.BytesIO()
    await run_in_threadpool(fig.savefig, img, format="png", bbox_inches="tight", dpi=120)
    img.seek(0)
    fig.clear()
    return StreamingResponse(img, media_type="image/png")
"""

"""
@app.get("/plot_anomaly")
async def plot_anomaly(
    base_id: Optional[str] = None, # 💡 追加
    mode: str = "range", yyyymm: Optional[str] = None, dd: Optional[str] = None,
    switch: Optional[str] = None, filename: Optional[str] = None, cols: int = 2,
    start_hour: int = 8, end_hour: int = 18, start_dd: str = "", end_dd: str = "",
    logic: str = "stat_threshold",
):
    actual_base = get_base_dir_path(base_id) # 💡 パス解決

    fig_size = (14, 4.0) if cols == 1 else (6, 2.8) if cols == 4 else (8, 3.0)
    fig = Figure(figsize=fig_size)
    ax = fig.subplots()

    df_filtered = pd.DataFrame()

    try:
        df_list = []
        if start_dd and end_dd:
            dr = pd.date_range(start=start_dd, end=end_dd)
            for d in dr:
                # 💡 actual_base へ変更
                file_path = os.path.join(actual_base, d.strftime("%Y%m"), d.strftime("%d"), switch, filename)
                if os.path.exists(file_path):
                    _df = await run_in_threadpool(pd.read_csv, file_path, engine="c")
                    if not _df.empty:
                        df_list.append(_df)

            if df_list:
                df = pd.concat(df_list, ignore_index=True)
            else:
                raise FileNotFoundError("データファイルが見つかりません。")

            start_time = pd.to_datetime(start_dd) + pd.Timedelta(hours=start_hour)
            end_time = pd.to_datetime(end_dd) + pd.Timedelta(hours=end_hour, minutes=55)
            x_label_text = f"{start_dd} ～ {end_dd}"
            x_tick_format = "%m/%d %H:%M"
        else:
            raise ValueError("期間指定が必要です。")

        if len(df.columns) >= 6:
            df.columns = ["日時", "INDEX", "NAME", "STATUS", "項目A", "項目B"] + list(df.columns[6:])
        elif len(df.columns) >= 3:
            df.columns = ["日時", "項目A", "項目B"] + list(df.columns[3:])

        df["日時"] = pd.to_datetime(df["日時"], format="mixed", errors='coerce')
        df = df.dropna(subset=["日時"])
        df = df[(df["日時"] >= start_time) & (df["日時"] <= end_time)]
        df = df.sort_values("日時").reset_index(drop=True)

        time_diff_sec = df["日時"].diff().dt.total_seconds()
        is_missing = time_diff_sec > 330

        df["差分A"] = df["項目A"].diff().clip(lower=0)
        df.loc[is_missing, "差分A"] = None  

        df["bps_A"] = (df["差分A"] * 8) / 300
        df = df.dropna(subset=["bps_A"]).reset_index(drop=True)

        fig.set_facecolor("#f0f0f0")
        ax.set_facecolor("#ffffff")

        if not df.empty:
            df = df[~df["日時"].duplicated(keep='first')].reset_index(drop=True)

            max_points = 1000
            if len(df) > max_points:
                step = len(df) // max_points
                df_filtered = df.iloc[::step].copy().reset_index(drop=True)
            else:
                df_filtered = df.copy()

            ax.plot(df_filtered.index, df_filtered["bps_A"], color="#006600", linewidth=0.8, label="In (bps)")
            ax.fill_between(df_filtered.index, df_filtered["bps_A"], color="#00eb0c", alpha=0.4)

            if logic == "stat_threshold":
                df_filtered["score-source"] = df_filtered["bps_A"].diff().abs().fillna(0)
                title_prefix = "【異常検知: 直近急変重視】"
                percentile_val = 0.99
            elif logic == "burst_detector":
                df_filtered["score-source"] = df_filtered["bps_A"].rolling(window=6, min_periods=1).mean()
                title_prefix = "【異常検知: 30分連続バースト重視】"
                percentile_val = 0.95
            else:
                df_filtered["score-source"] = df_filtered["bps_A"]
                title_prefix = "【異常検知: 総合外れ値】"
                percentile_val = 0.98

            merlion_df = df_filtered[["日時", "score-source"]].set_index("日時")

            if len(merlion_df) > 2:
                time_series = TimeSeries.from_pd(merlion_df)

                if logic == "stat_threshold":
                    config = StatThresholdConfig(alpha=3.0)
                    model = StatThreshold(config)
                else:
                    config = IsolationForestConfig()
                    model = IsolationForest(config)

                anom_scores = await run_in_threadpool(model.train, time_series)
                anom_scores_df = anom_scores.to_pd()

                scores_map = pd.DataFrame(anom_scores_df)
                scores_map.columns = ["score"]

                df_filtered = df_filtered.merge(scores_map, left_on="日時", right_index=True, how="left")
                df_filtered["score"] = df_filtered["score"].fillna(0)

                threshold = df_filtered["score"].quantile(percentile_val)

                if logic == "stat_threshold":
                    anomalies = df_filtered[(df_filtered["score"] >= threshold) & (df_filtered["bps_A"].diff().abs() > 10_000_000)]
                elif logic == "burst_detector":
                    df_filtered["next_bps"] = df_filtered["bps_A"].shift(-1).fillna(df_filtered["bps_A"])
                    anomalies = df_filtered[
                        (df_filtered["score"] >= threshold) &
                        (df_filtered["score-source"] > 15_000_000) &
                        (df_filtered["bps_A"] > 15_000_000) &
                        (df_filtered["next_bps"] > 15_000_000)  
                    ]
                else:
                    anomalies = df_filtered[(df_filtered["score"] >= threshold) & (df_filtered["bps_A"] > 20_000_000)]

                if not anomalies.empty:
                    ax.scatter(anomalies.index, anomalies["bps_A"], color="red", s=15, zorder=5, label="Anomaly")
            else:
                title_prefix = "【異常検知】"

            ax.set_xlim(0, len(df_filtered) - 1)
            tick_indices = [0, len(df_filtered)//4, len(df_filtered)//2, (len(df_filtered)*3)//4, len(df_filtered)-1]
            tick_labels = [df_filtered["日時"].iloc[i].strftime(x_tick_format) for i in tick_indices if i < len(df_filtered)]
            ax.set_xticks(tick_indices)
            ax.set_xticklabels(tick_labels, rotation=30, ha="right")
        else:
            ax.text(0.5, 0.5, "データがありません", ha="center", va="center", color="red")
            title_prefix = "【異常検知】"

        max_val = df_filtered["bps_A"].max() if not df_filtered.empty else 0
        if max_val >= 1_000_000:
            ax.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f"{x / 1_000_000:,.1f} M"))
            ax.set_ylabel("転送速度 (Mbps)")
        elif max_val >= 1_000:
            ax.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f"{x / 1_000:,.0f} K"))
            ax.set_ylabel("転送速度 (Kbps)")
        else:
            ax.get_yaxis().set_major_formatter(matplotlib.ticker.StrMethodFormatter("{x:,.0f}"))
            ax.set_ylabel("転送速度 (bps)")

        ax.set_title(f"{title_prefix} {switch}: {filename.replace('.csv', '')}", fontsize=11, loc="left", color="darkred")
        ax.set_xlabel(x_label_text)
    except Exception as e:
        traceback.print_exc()
        ax.text(0.5, 0.5, f"Error: {type(e).__name__}", ha="center", va="center", color="red")

    fig.legend(bbox_to_anchor=(0.13, -0.04), loc='lower left', ncol=2, frameon=True)
    plt.subplots_adjust(bottom=0.25)
    fig.tight_layout()

    img = io.BytesIO()
    await run_in_threadpool(fig.savefig, img, format="png", bbox_inches="tight", dpi=120)
    img.seek(0)
    fig.clear()
    return StreamingResponse(img, media_type="image/png")
"""

if __name__ == "__main__":
    import uvicorn
    # 💡 起動時にマッピングされている全てのBASE_DIRを走査し、無ければ自動生成する
    for name, path in BASE_DIRS.items():
        if not os.path.exists(path):
            os.makedirs(path)
    uvicorn.run("main:app", host="0.0.0.0", port=80, reload=True)
