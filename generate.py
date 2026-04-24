#!/usr/bin/env python3
"""
Emily 的投资早报 — 每日完整早报生成器
1. yfinance 抓取所有标的最新价格和涨跌幅（免费）
2. Google Gemini API 生成中文分析文字（免费）
3. 输出 data.json → GitHub Pages 读取，展示完整早报

运行方式：
  本地测试：GEMINI_API_KEY=你的key python generate_prices.py
  GitHub Actions：自动从 Secret 读取 GEMINI_API_KEY
"""

import json
import os
import sys
import requests
from datetime import datetime

try:
    import pytz
    import yfinance as yf
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yfinance", "pytz"])
    import pytz
    import yfinance as yf

VANCOUVER_TZ = pytz.timezone("America/Vancouver")
GEMINI_KEY   = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL   = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# ── 标的映射 ──────────────────────────────────────────────────────────────────
SYMBOLS = {
    "HUT":    "HUT",
    "IREN":   "IREN",
    "CIFR":   "CIFR",
    "WULF":   "WULF",
    "CRWV":   "CRWV",
    "NBIS":   "NBIS",
    "SPY":    "SPY",
    "QQQ":    "QQQ",
    "VIX":    "^VIX",
    "BTC":    "BTC-USD",
    "ETH":    "ETH-USD",
    "USDCAD": "USDCAD=X",
    "HUTTO":  "HUT.TO",
}


def safe_pct(new_val: float, old_val: float):
    if old_val and abs(old_val) > 1e-9:
        return round((new_val - old_val) / abs(old_val) * 100, 2)
    return None


def fetch(yf_sym: str, label: str):
    try:
        hist = yf.Ticker(yf_sym).history(period="12d", auto_adjust=True)
        if len(hist) < 2:
            print(f"  ⚠  {label}: 数据不足")
            return None
        price = round(float(hist["Close"].iloc[-1]), 4)
        ch1d  = safe_pct(price, float(hist["Close"].iloc[-2]))
        ch5d  = safe_pct(price, float(hist["Close"].iloc[-6])) if len(hist) >= 6 else None
        return {"price": price, "ch1d": ch1d, "ch5d": ch5d}
    except Exception as e:
        print(f"  ✗  {label}: {e}")
        return None


def fetch_all_prices(now: datetime) -> dict:
    result = {"updated_at": now.strftime("%Y-%m-%d %H:%M PT"), "tickers": {}}
    print("📈 抓取价格中...\n")

    for key in ["HUT", "IREN", "CIFR", "WULF", "CRWV", "NBIS", "SPY", "QQQ", "VIX"]:
        d = fetch(SYMBOLS[key], key)
        if d:
            result["tickers"][key] = d
            ch = f"{d['ch1d']:+.2f}%" if d["ch1d"] is not None else "n/a"
            print(f"  ✓  {key:<8} ${d['price']:.2f}  ({ch})")

    for key in ["BTC", "ETH"]:
        d = fetch(SYMBOLS[key], key)
        if d:
            result["tickers"][key] = d
            ch = f"{d['ch1d']:+.2f}%" if d["ch1d"] is not None else "n/a"
            print(f"  ✓  {key:<8} ${d['price']:,.0f}  ({ch})")

    usdcad = fetch(SYMBOLS["USDCAD"], "USD/CAD")
    if usdcad:
        result["usdcad"] = round(usdcad["price"], 4)
        print(f"  ✓  USD/CAD  {usdcad['price']:.4f}")

    hutto = fetch(SYMBOLS["HUTTO"], "HUT.TO")
    if hutto:
        result["tickers"]["HUT.TO"] = hutto
        ch = f"{hutto['ch1d']:+.2f}%" if hutto["ch1d"] is not None else "n/a"
        print(f"  ✓  HUT.TO   CA${hutto['price']:.2f}  ({ch})")
    elif "HUT" in result["tickers"] and "usdcad" in result:
        hut  = result["tickers"]["HUT"]
        rate = result["usdcad"]
        result["tickers"]["HUT.TO"] = {
            "price": round(hut["price"] * rate, 2),
            "ch1d":  hut["ch1d"],
            "ch5d":  hut["ch5d"],
            "fx_derived": True
        }
        print(f"  ✓  HUT.TO   CA${result['tickers']['HUT.TO']['price']:.2f}  (FX 计算)")

    return result


def build_prompt(prices: dict) -> str:
    lines = []
    for sym, d in prices["tickers"].items():
        ch  = f"{d['ch1d']:+.2f}%" if d.get("ch1d") is not None else "N/A"
        ch5 = f"{d['ch5d']:+.2f}%" if d.get("ch5d") is not None else "N/A"
        p   = d["price"]
        if sym == "HUT.TO":
            ps = f"CA${p:.2f}"
        elif p > 5000:
            ps = f"${p:,.0f}"
        else:
            ps = f"${p:.2f}"
        lines.append(f"{sym}: {ps} | 24h {ch} | 5D {ch5}")

    return f"""你是专业投资分析师，专注加密矿工股和AI基础设施股票。
今日：{prices["updated_at"]}  USD/CAD：{prices.get("usdcad", 1.37):.4f}

今日价格：
{chr(10).join(lines)}

标的背景：HUT/HUT.TO=BTC矿工(双交易所)，IREN=矿工转AI数据中心，CIFR=矿工+AWS合约，WULF=矿工+核能，CRWV=CoreWeave AI云，NBIS=Nebius AI云(前Yandex)，BTC/ETH=加密货币，QQQ=纳指ETF，SPY=标普ETF，VIX=恐慌指数

请根据今日实际价格，生成完整投资早报。严格返回以下 JSON，全部中文，不要任何其他文字：

{{
  "market_pulse": "市场一句话总结，包含关键数字，60字以内",
  "market_sentiment": "风险偏好|震荡|风险规避（只选一个）",
  "ticker_notes": {{
    "HUT": "要点分析，含涨跌原因或关键价位，25字以内",
    "HUT.TO": "加元价及汇率影响说明，25字以内",
    "IREN": "要点，25字以内",
    "CIFR": "要点，25字以内",
    "WULF": "要点，25字以内",
    "CRWV": "要点，25字以内",
    "NBIS": "要点，25字以内",
    "BTC": "含关键支撑/阻力位，25字以内",
    "ETH": "要点，25字以内",
    "QQQ": "要点，25字以内",
    "SPY": "要点，25字以内",
    "VIX": "含情绪判断，25字以内"
  }},
  "watchlist": [
    {{
      "sym": "今日最值得关注的标的名（选4个，用其 ticker 代码，如 HUT、BTC）",
      "emoji": "🟢(涨)或🔴(跌)或🟡(平/注意)或🔵(特殊)",
      "why": "为何今日值得关注，60字以内",
      "bull": ["看涨点1", "看涨点2", "看涨点3"],
      "bear": ["风险1", "风险2"],
      "inst": "机构观点或关键数据，30字以内",
      "quote": "市场热点观察，30字以内"
    }},
    {{...}},
    {{...}},
    {{...}}
  ],
  "risks": [
    {{"icon": "😨", "title": "风险标题20字以内", "body": "风险说明50字以内"}},
    {{"icon": "📉", "title": "...", "body": "..."}},
    {{"icon": "💱", "title": "...", "body": "..."}},
    {{"icon": "⚡", "title": "...", "body": "..."}}
  ]
}}

要求：基于实际价格数据，watchlist 选今日涨跌最突出或有重要信号的4个，risks 列4个主要风险。"""


def call_gemini(prompt: str) -> dict:
    if not GEMINI_KEY:
        raise ValueError("GEMINI_API_KEY 环境变量未设置")
    url  = f"{GEMINI_URL}?key={GEMINI_KEY}"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.7,
            "maxOutputTokens": 4096
        }
    }
    resp = requests.post(url, json=body, timeout=90)
    resp.raise_for_status()
    raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(raw)


def main():
    now    = datetime.now(VANCOUVER_TZ)
    prices = fetch_all_prices(now)

    print("\n🤖 调用 Gemini 生成分析文字...")
    try:
        analysis = call_gemini(build_prompt(prices))
        print("  ✅ 分析完成")
    except Exception as e:
        print(f"  ⚠️  Gemini 调用失败（{e}），使用空分析")
        analysis = {}

    # ── 合并价格 + 分析 → data.json ──────────────────────────────────────────
    ticker_notes = analysis.get("ticker_notes", {})
    tickers_out  = {}
    for sym, d in prices["tickers"].items():
        tickers_out[sym] = {**d, "note": ticker_notes.get(sym, "")}

    # watchlist：从 Gemini 获取文字，用真实价格补全显示字段
    watchlist_out = []
    for w in analysis.get("watchlist", []):
        sym = w.get("sym", "")
        td  = prices["tickers"].get(sym, {})
        p   = td.get("price")
        if p is not None:
            if sym == "HUT.TO":
                price_str = f"CA${p:.2f}"
            elif p > 5000:
                price_str = f"${p:,.0f}"
            else:
                price_str = f"${p:.2f}"
        else:
            price_str = sym
        ch24_str = f"{td['ch1d']:.2f}" if td.get("ch1d") is not None else "0"
        watchlist_out.append({
            "sym":   sym,
            "price": price_str,
            "ch24":  ch24_str,
            "emoji": w.get("emoji", "🟡"),
            "why":   w.get("why", ""),
            "bull":  w.get("bull", []),
            "bear":  w.get("bear", []),
            "inst":  w.get("inst", ""),
            "quote": w.get("quote", "")
        })

    data = {
        "updated_at":       prices["updated_at"],
        "market_pulse":     analysis.get("market_pulse", ""),
        "market_sentiment": analysis.get("market_sentiment", "震荡"),
        "usdcad":           prices.get("usdcad", 1.37),
        "tickers":          tickers_out,
        "watchlist":        watchlist_out,
        "risks":            analysis.get("risks", [])
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    syms = len(data["tickers"])
    wl   = len(data["watchlist"])
    rs   = len(data["risks"])
    print(f"\n✅ data.json 已保存（{syms} 标的，{wl} 关注，{rs} 风险，{data['updated_at']}）")


if __name__ == "__main__":
    main()
