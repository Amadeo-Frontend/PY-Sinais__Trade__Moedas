#!/usr/bin/env python3
"""
Sinal Bot – Versão completa (WebSocket Exnova)
=================================================
* Feed: WebSocket Exnova (iqoptionapi)
* Pares: EURUSD, EURJPY, USDJPY, AUDCAD
* TFs: M1 & M5
* Estratégia: EMA20×SMA200 + BB 20/2σ + RSI 14 + MACD + Hammer + “Rombada” EMA9
* Mensagem: timestamp GMT‑3, expiração (3 velas), MG1, análise rápida.

Requisitos: veja comentários `.env` e `pyproject.toml` no topo.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Literal, Optional, Tuple, Set

import numpy as np
# --- Compat: pandas_ta < 0.4 espera numpy.NaN (removido em NumPy 2.x) -----
if not hasattr(np, "NaN"):
    np.NaN = np.nan  # type: ignore[attr-defined]

import aiohttp
import pandas as pd
import pandas_ta as ta
from dotenv import load_dotenv
from iqoptionapi.stable_api import IQ_Option

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv()
TG_TOKEN: str = os.getenv("TG_TOKEN", "")
TG_CHAT_ID: str = os.getenv("TG_CHAT_ID", "")
EXNOVA_EMAIL: str = os.getenv("EXNOVA_EMAIL", "")
EXNOVA_PASS: str = os.getenv("EXNOVA_PASS", "")
EXNOVA_SSID: str = os.getenv("EXNOVA_SSID", "")

if not TG_TOKEN or not TG_CHAT_ID:
    raise RuntimeError("Defina TG_TOKEN e TG_CHAT_ID no .env")

PAIRS = ["EURUSD", "EURJPY", "USDJPY", "AUDCAD"]
TIMEFRAMES = [1, 5]          # minutos
LEAD_SECONDS = 3             # antecedência do aviso
MAX_CANDLES = 400
CHECK_INTERVAL = 30          # segundos entre verificações

EMA_FAST = 20
SMA_SLOW = 200
EMA_ROMBADA = 9
RSI_LEN = 14
BB_LENGTH = 20
BB_STD = 2

SP_TZ = timezone(timedelta(hours=-3))

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("SinalBot")

# ---------------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------------
SignalDir = Literal["CALL", "PUT"]


@dataclass
class Signal:
    pair: str
    tf: int
    direction: SignalDir
    entry_time: datetime
    expiry_time: datetime
    mg1_time: datetime
    analysis: str
    confidence: int  # 1-5 estrelas

    def render(self) -> str:
        stamp = self.entry_time.astimezone(SP_TZ).strftime("🕒 %H:%M GMT-3")
        direction_icon = "✅ CALL" if self.direction == "CALL" else "🔻 PUT"
        confidence_stars = "⭐" * self.confidence

        core = (
            f"<b>{self.pair} | M{self.tf}</b>\n"
            f"{direction_icon} | Força: {confidence_stars}\n"
            f"⏱ Expira: {self.expiry_time.astimezone(SP_TZ).strftime('%H:%M:%S')}\n"
            f"🎯 MG1: {self.mg1_time.astimezone(SP_TZ).strftime('%H:%M:%S')}"
        )

        body = f"{stamp}\n{core}"
        if self.analysis:
            body += f"\n\n🔍 {self.analysis}"

        return body

    def unique_key(self) -> str:
        """Chave única para evitar duplicatas"""
        return f"{self.pair}-M{self.tf}-{self.entry_time.timestamp()}-{self.direction}"


# ---------------------------------------------------------------------------
# WebSocket Exnova helpers
# ---------------------------------------------------------------------------
_EX_API: IQ_Option | None = None
_LOGIN_LOCK = asyncio.Lock()
ACTIVE_ID_MAP: Dict[str, int] = {"EURUSD": 1,
                                 "USDJPY": 2, "EURJPY": 3, "AUDCAD": 180}

# Cache de sinais enviados (evitar repetições)
sent_signals: Set[str] = set()


async def _ensure_login() -> IQ_Option:
    global _EX_API
    async with _LOGIN_LOCK:
        if _EX_API and _EX_API.check_connect():
            return _EX_API

        loop = asyncio.get_running_loop()
        if EXNOVA_SSID:
            api = IQ_Option("", "")
            ok, reason = await loop.run_in_executor(None, api.connect)
            if not ok:
                raise RuntimeError(f"Falha socket: {reason}")
            # type: ignore[attr-defined,protected-access]
            api._ssid = EXNOVA_SSID
            api.bind_ssid()
        else:
            if not (EXNOVA_EMAIL and EXNOVA_PASS):
                raise RuntimeError("Defina EXNOVA_EMAIL/PASS ou EXNOVA_SSID")
            api = IQ_Option(EXNOVA_EMAIL, EXNOVA_PASS)
            ok, reason = await loop.run_in_executor(None, api.connect)
            if not ok:
                raise RuntimeError(f"Login recusado: {reason}")

        _EX_API = api
        log.info("Conectado Exnova.")
        return api

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


async def fetch_candles(pair: str, tf_min: int, n: int = MAX_CANDLES) -> pd.DataFrame:
    api = await _ensure_login()
    aid = ACTIVE_ID_MAP[pair]
    loop = asyncio.get_running_loop()
    now = int(datetime.now(timezone.utc).timestamp())  # CORREÇÃO AQUI
    candles = await loop.run_in_executor(None, api.get_candles, aid, tf_min * 60, n, now)
    if not candles:
        raise RuntimeError(f"Candles vazios para {pair}")
    df = pd.DataFrame(candles)
    df.rename(columns={"open_time": "time",
              "min": "low", "max": "high"}, inplace=True)
    df = df[["time", "open", "high", "low", "close", "volume"]]
    df.sort_values("time", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df

# ---------------------------------------------------------------------------
# Indicadores
# ---------------------------------------------------------------------------


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.set_index(pd.to_datetime(df["time"], unit="s", utc=True), inplace=True)

    # Tendência principal
    df["ema20"] = ta.ema(df["close"], length=EMA_FAST)
    df["sma200"] = ta.sma(df["close"], length=SMA_SLOW)

    # Bollinger Bands
    bb = ta.bbands(df["close"], length=BB_LENGTH, std=BB_STD)
    df = pd.concat([df, bb], axis=1)

    # Osciladores
    df["rsi"] = ta.rsi(df["close"], length=RSI_LEN)
    macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
    df = pd.concat([df, macd], axis=1)

    # Rombada EMA9
    df["ema9"] = ta.ema(df["close"], length=EMA_ROMBADA)

    return df.dropna()


def is_hammer(row: pd.Series) -> Optional[SignalDir]:
    body_size = abs(row.close - row.open)
    total_range = row.high - row.low

    if total_range == 0 or body_size == 0:
        return None

    body_ratio = body_size / total_range
    lower_shadow = min(row.open, row.close) - row.low
    upper_shadow = row.high - max(row.open, row.close)

    # Hammer (verde) - CALL
    if row.close > row.open:
        if lower_shadow >= 2 * body_size and upper_shadow <= body_size * 0.3:
            return "CALL"

    # Shooting star (vermelha) - PUT
    else:
        if upper_shadow >= 2 * body_size and lower_shadow <= body_size * 0.3:
            return "PUT"

    return None


def ema9_breakout(row: pd.Series) -> Optional[SignalDir]:
    threshold = 0.0008  # 0.08% do valor
    if row.close > row.ema9 * (1 + threshold):
        return "CALL"
    if row.close < row.ema9 * (1 - threshold):
        return "PUT"
    return None


def calculate_confidence(
    trend_dir: SignalDir,
    bb_extreme: bool,
    rsi_ok: bool,
    macd_ok: bool,
    has_hammer: bool,
    has_rombada: bool
) -> int:
    """Calcula confiança de 1-5 estrelas baseado em confluências"""
    points = 0

    # Tendência principal (2 pontos)
    points += 2

    # Bollinger extremo (1 ponto)
    if bb_extreme:
        points += 1

    # RSI (1 ponto)
    if rsi_ok:
        points += 1

    # MACD (1 ponto)
    if macd_ok:
        points += 1

    # Padrão de vela (1 ponto)
    if has_hammer:
        points += 1

    # Rombada EMA9 (1 ponto)
    if has_rombada:
        points += 1

    # Normalizar para escala 1-5
    return min(5, max(1, round(points / 2)))


def generate_signal(pair: str, tf: int, df: pd.DataFrame) -> Optional[Signal]:
    last = df.iloc[-1]
    prev = df.iloc[-2]  # Vela anterior

    # Direção da tendência
    trend_dir: SignalDir = "CALL" if last.ema20 > last.sma200 else "PUT"

    # Verificar condições dos indicadores
    bb_extreme = (
        (last.close <= last["BBL_20_2.0"] and trend_dir == "CALL") or
        (last.close >= last["BBU_20_2.0"] and trend_dir == "PUT")
    )

    rsi_ok = (
        (trend_dir == "CALL" and last.rsi < 35) or
        (trend_dir == "PUT" and last.rsi > 65)
    )

    macd_ok = (
        (trend_dir == "CALL" and last.MACD_12_26_9 > last.MACDs_12_26_9) or
        (trend_dir == "PUT" and last.MACD_12_26_9 < last.MACDs_12_26_9)
    )

    hammer_dir = is_hammer(last)
    rombada_dir = ema9_breakout(last)

    # Confluência mínima necessária
    if not (bb_extreme and rsi_ok and macd_ok):
        return None

    # Verificar se os padrões confirmam a tendência
    valid_hammer = hammer_dir == trend_dir if hammer_dir else True
    valid_rombada = rombada_dir == trend_dir if rombada_dir else True

    if not (valid_hammer and valid_rombada):
        return None

    # Construir análise descritiva
    analysis_parts = []

    if bb_extreme:
        side = "inferior" if trend_dir == "CALL" else "superior"
        analysis_parts.append(f"BB {side}")

    if rsi_ok:
        rsi_status = "sobrevendido" if trend_dir == "CALL" else "sobrecomprado"
        analysis_parts.append(f"RSI {rsi_status} ({last.rsi:.1f})")

    if macd_ok:
        macd_status = "alta" if trend_dir == "CALL" else "baixa"
        analysis_parts.append(f"MACD {macd_status}")

    if hammer_dir:
        analysis_parts.append("Padrão Hammer" if trend_dir ==
                              "CALL" else "Shooting Star")

    if rombada_dir:
        analysis_parts.append("ROMBADA EMA9")

    analysis = " | ".join(analysis_parts)

    # Calcular confiança
    confidence = calculate_confidence(
        trend_dir=trend_dir,
        bb_extreme=bb_extreme,
        rsi_ok=rsi_ok,
        macd_ok=macd_ok,
        has_hammer=hammer_dir is not None,
        has_rombada=rombada_dir is not None
    )

    # Calcular tempos
    now_utc = datetime.now(timezone.utc)
    entry_time = now_utc + timedelta(seconds=LEAD_SECONDS)
    expiry_minutes = tf * 3  # Expira em 3 velas do timeframe
    expiry_time = entry_time + timedelta(minutes=expiry_minutes)
    mg1_time = expiry_time + timedelta(minutes=tf)

    return Signal(
        pair=pair,
        tf=tf,
        direction=trend_dir,
        entry_time=entry_time,
        expiry_time=expiry_time,
        mg1_time=mg1_time,
        analysis=analysis,
        confidence=confidence
    )

# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------


_TELEGRAM_SESSION: aiohttp.ClientSession | None = None


async def send_telegram(msg: str) -> None:
    global _TELEGRAM_SESSION
    if _TELEGRAM_SESSION is None or _TELEGRAM_SESSION.closed:
        _TELEGRAM_SESSION = aiohttp.ClientSession()

    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        async with _TELEGRAM_SESSION.post(url, json=payload) as resp:
            if resp.status != 200:
                log.error("Falha Telegram: %s", await resp.text())
            else:
                log.info("Mensagem enviada com sucesso")
    except Exception as e:
        log.error("Erro no envio Telegram: %s", str(e))

# ---------------------------------------------------------------------------
# Loop Principal
# ---------------------------------------------------------------------------


async def monitor_market():
    """Monitora todos os pares e timeframes periodicamente"""
    log.info("Iniciando monitoramento...")

    while True:
        try:
            tasks = []
            for pair in PAIRS:
                for tf in TIMEFRAMES:
                    tasks.append(check_pair(pair, tf))

            await asyncio.gather(*tasks)
            log.info("Verificação completa. Aguardando próxima...")
            await asyncio.sleep(CHECK_INTERVAL)

        except Exception as e:
            log.error("Erro no loop principal: %s", str(e))
            await asyncio.sleep(60)  # Espera antes de tentar novamente


async def check_pair(pair: str, tf: int):
    try:
        df = await fetch_candles(pair, tf)
        df = add_indicators(df)
        signal = generate_signal(pair, tf, df)

        if signal:
            signal_key = signal.unique_key()

            # Evitar sinais duplicados
            if signal_key not in sent_signals:
                sent_signals.add(signal_key)
                msg = signal.render()
                log.info("Sinal detectado: %s M%d %s",
                         pair, tf, signal.direction)
                await send_telegram(msg)
            else:
                log.debug("Sinal duplicado ignorado: %s", signal_key)
        else:
            log.debug("Nenhum sinal para %s M%d", pair, tf)

    except Exception as e:
        log.error("Erro em %s M%d: %s", pair, tf, str(e))


async def shutdown():
    """Encerra recursos abertos"""
    global _TELEGRAM_SESSION
    if _TELEGRAM_SESSION:
        await _TELEGRAM_SESSION.close()
    log.info("Recursos liberados")

# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    try:
        asyncio.run(monitor_market())
    except KeyboardInterrupt:
        log.info("Bot interrompido pelo usuário")
    finally:
        asyncio.run(shutdown())
