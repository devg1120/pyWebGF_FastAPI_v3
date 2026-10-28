import pandas as pd
import numpy as np

class AnomalyDetectors:
    """異常検知アルゴリズムを管理するクラス"""

    @classmethod
    def get_available_logics(cls) -> dict:
        """
        利用可能な検知ロジックの一覧と画面表示名
        💡 ここに3つの新しいロジックを追加しました
        """
        return {
            "stat_threshold": "【異常検知: 直近急変重視】",
            "burst_detector": "【異常検知: 30分連続バースト重視】",
            "z_score_outlier": "【異常検知: 総合外れ値】",
            "static_upper_limit": "【帯域監視: 限界しきい値超過】",
            "silent_drop_detector": "【死活監視: 通信ゼロ/途絶検知】",
            "volatility_anomaly": "【品質監視: トラフィック乱高下異常】"
        }

    @classmethod
    def detect(cls, logic_name: str, df: pd.DataFrame, percentile_val: float) -> pd.DataFrame:
        """
        指定されたロジック名に基づいて異常検知を計算し、異常行（anomalies）のDataFrameを返す
        """
        method = getattr(cls, f"_{logic_name}", None)
        if method is None:
            return pd.DataFrame()
        return method(df, percentile_val)

    # ─────────────────────────────────────────────────────────────────
    # 既存のロジック群
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _stat_threshold(df: pd.DataFrame, percentile_val: float) -> pd.DataFrame:
        df_cp = df.copy()
        df_cp["diff_val"] = df_cp["bps_A"].diff().abs().fillna(0)
        threshold = df_cp["diff_val"].quantile(percentile_val)
        return df_cp[(df_cp["diff_val"] >= threshold) & (df_cp["diff_val"] > 10_000_000)]

    @staticmethod
    def _burst_detector(df: pd.DataFrame, percentile_val: float) -> pd.DataFrame:
        df_cp = df.copy()
        df_cp["rolling_mean"] = df_cp["bps_A"].rolling(window=6, min_periods=1).mean()
        df_cp["next_bps"] = df_cp["bps_A"].shift(-1).fillna(df_cp["bps_A"])
        threshold = df_cp["rolling_mean"].quantile(percentile_val)
        return df_cp[
            (df_cp["rolling_mean"] >= threshold) &
            (df_cp["bps_A"] > 15_000_000) &
            (df_cp["next_bps"] > 15_000_000)
        ]

    @staticmethod
    def _z_score_outlier(df: pd.DataFrame, percentile_val: float) -> pd.DataFrame:
        df_cp = df.copy()
        mean_bps = df_cp["bps_A"].mean()
        std_bps = df_cp["bps_A"].std()
        df_cp["z_score"] = (df_cp["bps_A"] - mean_bps) / std_bps if std_bps > 0 else 0
        return df_cp[(df_cp["z_score"] > 2.55) & (df_cp["bps_A"] > 20_000_000)]

    # ─────────────────────────────────────────────────────────────────
    # ✨【新設】有効な追加ロジック群
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _static_upper_limit(df: pd.DataFrame, percentile_val: float) -> pd.DataFrame:
        """1. 固定しきい値超過（回線限界への到達を監視）"""
        df_cp = df.copy()
        # 💡 例として 800Mbps (800_000_000 bps) を絶対的な危険しきい値として定義
        # 環境に合わせてこの数値を 100M や 1G などに変更可能です
        DANGER_LIMIT_BPS = 800_000_000 
        return df_cp[df_cp["bps_A"] >= DANGER_LIMIT_BPS]

    @staticmethod
    def _silent_drop_detector(df: pd.DataFrame, percentile_val: float) -> pd.DataFrame:
        """2. サイレント障害（15分以上、通信が完全に途絶した状態を監視）"""
        df_cp = df.copy()
        # 5分間隔データ×3点 = 15分間連続で「ほぼ0（例: 10kbps未満）」かどうかを判定
        df_cp["is_zero"] = df_cp["bps_A"] < 10_000
        df_cp["zero_strike"] = df_cp["is_zero"].rolling(window=3).sum()
        # 3点連続で通信が死んでいるポイントを検知
        return df_cp[df_cp["zero_strike"] >= 3]

    @staticmethod
    def _volatility_anomaly(df: pd.DataFrame, percentile_val: float) -> pd.DataFrame:
        """3. トラフィック乱高下異常（ジッター・フラッフィングの監視）"""
        df_cp = df.copy()
        # 過去30分間（6点）のトラフィックの「標準偏差（ばらつき）」を動的に計算
        df_cp["rolling_std"] = df_cp["bps_A"].rolling(window=6, min_periods=1).std().fillna(0)
        # ばらつきが全体の統計値の上位2%を超えている箇所をフラッピング異常としてマーク
        std_threshold = df_cp["rolling_std"].quantile(0.98)
        return df_cp[(df_cp["rolling_std"] >= std_threshold) & (df_cp["bps_A"] > 5_000_000)]
