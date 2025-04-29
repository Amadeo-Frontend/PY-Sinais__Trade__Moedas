import os
import datetime as dt
import yfinance as yf
import pandas as pd
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

# -------- CONFIGURAÇÕES ---------
PAIRS = {
    'AUDCHF=X': 'AUDCHF', 'EURGBP=X': 'EURGBP', 'EURJPY=X': 'EURJPY',
    'EURUSD=X': 'EURUSD', 'GBPCAD=X': 'GBPCAD', 'GBPUSD=X': 'GBPUSD',
    'USDCHF=X': 'USDCHF', 'USDJPY=X': 'USDJPY'
}
OUTPUT_PATH = r"C:\Users\amade\OneDrive\Desktop\ExnovaBot\sinais"
OUTPUT_FILE = os.path.join(OUTPUT_PATH, "sinais.txt")

EMA_S, EMA_L = 9, 21
RSI_PER, RSI_LOW, RSI_HIGH = 14, 25, 75
ATR_PER, ATR_MIN = 14, 0.0008
MIN_EMA_DIST = 0.0005          # 0,05 %
SESSION_START, SESSION_END = 8, 17    # UTC
DEBUG = True                          # ← mude para False depois dos testes
# ---------------------------------


def _series_1d(df: pd.DataFrame, col: str) -> pd.Series:
    """Garante Series 1-D mesmo se yfinance devolver MultiIndex."""
    s = df[col]
    return s.iloc[:, 0] if isinstance(s, pd.DataFrame) else s.astype(float)


def is_reversal(o: float, h: float, l: float, c: float) -> bool:
    """Regra simples: candle com wick grande (martelo/pin)."""
    body = abs(c - o)
    wick = h - l
    return wick > 2 * body


def analisar(df: pd.DataFrame, label: str) -> list[str]:
    sigs = []

    close = _series_1d(df, 'Close')
    high = _series_1d(df, 'High')
    low = _series_1d(df, 'Low')
    open_ = _series_1d(df, 'Open')

    df['EMA_S'] = EMAIndicator(close, EMA_S).ema_indicator()
    df['EMA_L'] = EMAIndicator(close, EMA_L).ema_indicator()
    df['RSI'] = RSIIndicator(close, RSI_PER).rsi()
    df['ATR'] = AverageTrueRange(
        high, low, close, ATR_PER).average_true_range()

    if DEBUG:
        tot = f_sess = f_dist = f_rsi = f_atr = f_rev = 0

    for i in range(len(df) - 2):
        if DEBUG:
            tot += 1

        t = df.index[i + 1]
        hour = t.hour
        if not SESSION_START <= hour < SESSION_END:
            if DEBUG:
                f_sess += 1
            continue

        ema_s, ema_l = df['EMA_S'].iat[i], df['EMA_L'].iat[i]
        rsi = df['RSI'].iat[i]
        atr = df['ATR'].iat[i]
        price = close.iat[i]

        if pd.isna(ema_s) or pd.isna(ema_l) or pd.isna(rsi) or pd.isna(atr):
            continue

        dist_ok = abs(ema_s - ema_l) >= MIN_EMA_DIST * price
        atr_ok = atr >= ATR_MIN
        rsi_ok = (ema_s > ema_l and rsi < RSI_LOW) or (
            ema_s < ema_l and rsi > RSI_HIGH)
        rev_ok = is_reversal(
            open_.iat[i], high.iat[i], low.iat[i], close.iat[i])

        if DEBUG:
            if not dist_ok:
                f_dist += 1
            if not atr_ok:
                f_atr += 1
            if not rsi_ok:
                f_rsi += 1
            if not rev_ok:
                f_rev += 1

        if dist_ok and atr_ok and rsi_ok and rev_ok:
            direction = 'CALL' if ema_s > ema_l else 'PUT'
            nxt_idx, gale_idx = i + 1, i + 2

            sig_time = (df.index[nxt_idx] -
                        dt.timedelta(seconds=3)).strftime('%H:%M')
            sigs.append(f'{label};{sig_time};{direction}')

            win = (close.iat[gale_idx] > open_.iat[nxt_idx]) if direction == 'CALL' \
                else (close.iat[gale_idx] < open_.iat[nxt_idx])
            if not win:
                gale_time = (df.index[gale_idx] -
                             dt.timedelta(seconds=3)).strftime('%H:%M')
                sigs.append(f'{label};{gale_time};{direction};GALE1')

    if DEBUG:
        print(f"{label} | velas:{tot} | foraSess:{f_sess} | dist:{f_dist} | "
              f"rsi:{f_rsi} | atr:{f_atr} | rev:{f_rev}")

    return sigs


def gerar_sinais() -> list[str]:
    all_sigs = []
    for ticker, label in PAIRS.items():
        df = yf.download(ticker, period='3d', interval='5m',
                         auto_adjust=True, progress=False)
        if not df.empty:
            all_sigs.extend(analisar(df, label))
    return all_sigs


def salvar(linhas: list[str]):
    os.makedirs(OUTPUT_PATH, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(linhas))
    print(f'{len(linhas)} sinais gerados → {OUTPUT_FILE}')


if __name__ == '__main__':
    salvar(gerar_sinais())
