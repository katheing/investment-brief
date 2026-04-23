#!/usr/bin/env python3
"""
Daily Investment Brief — GitHub Pages generator
Uses yfinance (stocks) + CoinGecko (crypto, free tier) for live prices.
Falls back to seed data if any fetch fails.
"""
import datetime, json, sys

try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False
    print("WARNING: yfinance not installed — using seed prices for stocks")

try:
    import requests
    HAS_REQ = True
except ImportError:
    HAS_REQ = False
    print("WARNING: requests not installed — using seed prices for crypto")

# ── Date ──────────────────────────────────────────────────────────────────────
today = datetime.date.today()
today_str  = today.strftime("%Y-%m-%d")
today_cn   = today.strftime("%Y/%m/%d") + " 早报"
weekday_cn = ["周一","周二","周三","周四","周五","周六","周日"][today.weekday()]

# ── Ticker definitions ────────────────────────────────────────────────────────
# sent = LunarCrush sentiment score (updated manually when available)
TICKERS = [
    {"sym":"HUT",    "yf":"HUT",   "price":80.74,  "ch24": 5.43, "ch7": 9.20, "sent":91, "rank":"#46",  "exch":"NASDAQ", "note":"矿工股龙头；BTC 反弹直接受益；Piper Sandler PT $93；Anthropic 合作催化"},
    {"sym":"HUT.TO", "yf":None,    "price":110.36, "ch24": 5.43, "ch7": 9.00, "sent":91, "rank":"#46",  "exch":"TSX",    "note":"TSX 加元挂牌，同 NASDAQ:HUT；今日同步触 52W 新高区间", "hutca":True, "cad":True},
    {"sym":"IREN",   "yf":"IREN",  "price":48.39,  "ch24": 7.13, "ch7": 1.00, "sent":82, "rank":"#9",   "exch":"NASDAQ", "note":"Sweetwater 通电催化 + Anthropic 合作预期；$6B ATM 增发悬顶"},
    {"sym":"CIFR",   "yf":"CIFR",  "price":19.44,  "ch24": 7.76, "ch7": 4.50, "sent":92, "rank":"#66",  "exch":"NASDAQ", "note":"AI/HPC 数据中心新合约；AWS 15 年租约；Strong Buy PT $23.45"},
    {"sym":"WULF",   "yf":"WULF",  "price":20.55,  "ch24": 3.95, "ch7":-8.00, "sent":91, "rank":"#103", "exch":"NASDAQ", "note":"随 BTC 反弹；CEO 减持悬顶"},
    {"sym":"CRWV",   "yf":"CRWV",  "price":122.54, "ch24": 6.41, "ch7":-2.50, "sent":79, "rank":"#106", "exch":"NASDAQ", "note":"机构共识买入 PT $116；高债务风险仍存"},
    {"sym":"NBIS",   "yf":"NBIS",  "price":156.14, "ch24":-0.26, "ch7":-4.66, "sent":None,"rank":"—",   "exch":"NASDAQ", "note":"AI 全栈云基础设施（GPU 集群）；1年 +614%；PT $168.67；5/19 财报"},
    {"sym":"BTC",    "yf":None,    "price":78387,  "ch24": 3.36, "ch7": 4.50, "sent":77, "rank":"#3",   "exch":"Crypto", "note":"突破 $78K；机构 ETF 净流入持续", "crypto":True},
    {"sym":"ETH",    "yf":None,    "price":2389,   "ch24": 3.05, "ch7": 2.50, "sent":82, "rank":"#4",   "exch":"Crypto", "note":"随 BTC 上涨；Pectra 升级预期支撑", "crypto":True},
    {"sym":"QQQ",    "yf":"QQQ",   "price":472.0,  "ch24": 1.73, "ch7": 0.99, "sent":83, "rank":"—",   "exch":"ETF",    "note":"追踪 NASDAQ 100；科技股风向标"},
    {"sym":"SPY",    "yf":"SPY",   "price":711.21, "ch24": 1.01, "ch7": 0.15, "sent":79, "rank":"—",   "exch":"ETF",    "note":"S&P 500；接近历史高位"},
    {"sym":"VIX",    "yf":"^VIX",  "price":18.92,  "ch24":-2.97, "ch7":None,  "sent":70, "rank":"—",   "exch":"Index",  "note":"恐慌指数；回落趋稳；仍高于均值 15-16"},
]

WATCHLIST = [
    {"sym":"HUT / HUT.TO","price_key":"HUT","ch_key":"HUT","emoji":"🟢",
     "why":"矿工股中基本面最强之一，双挂牌流动性好。Piper Sandler PT $93，Anthropic 潜在合作催化。",
     "bull":["Piper Sandler PT $93","Anthropic 合作催化","Data Center/AI 叙事","流动性好"],
     "bear":["高位可能回调","Uganda 运营指控未结案"],
     "inst":"Piper Sandler 重申买入，PT↑$93",
     "quote":"@McnallieM：\"$HUT: Piper Sandler raises — sees potential Anthropic partnership as major catalyst\""},
    {"sym":"NBIS","price_key":"NBIS","ch_key":"NBIS","emoji":"🔵",
     "why":"Nebius Group（前 Yandex）—— AI 全栈云基础设施（GPU 集群）。1年 +614%，营收增速 20x/年，不受 BTC 波动影响。",
     "bull":["1年 +614% 超强动能","AI GPU 云核心标的","营收增速 20x/年","招聘 YoY +196%"],
     "bear":["Q4 净亏 $250M","LT 债务 $4.1B","P/S 70x 估值极高"],
     "inst":"4 家 Buy｜PT 共识 $168.67；下一财报 2026-05-19",
     "quote":"Nebius 于 2024-08 从 Yandex 更名，剥离俄罗斯资产后专注全球 AI 云业务。"},
    {"sym":"IREN","price_key":"IREN","ch_key":"IREN","emoji":"🟢",
     "why":"BTC 上涨的直接受益者，可再生能源护城河。Sweetwater 通电 + Anthropic 合作是中期重大催化。",
     "bull":["BTC 反弹直接受益","Sweetwater 通电催化","可再生能源护城河"],
     "bear":["$6B ATM 增发随时执行","Cantor PT↓$61"],
     "inst":"Cantor Fitzgerald PT↓$61（from $82）｜中位 PT $77",
     "quote":"@EndicottInvests：\"Was $IREN tapping the ATM went down 5% in like 2 minutes\""},
    {"sym":"BTC","price_key":"BTC","ch_key":"BTC","emoji":"🟢",
     "why":"$80K 是下一个重要心理关口。机构 ETF 持续净流入，带动矿工股全线上涨。",
     "bull":["ETF 持续净流入","MicroStrategy 增持","$80K 突破预期"],
     "bear":["$80K 强阻力位","地缘风险随时反复"],
     "inst":"市场主导率 59.5%",
     "quote":"@coindesk：\"Strategy manufactures bitcoin: through convertibles, preferreds and equity\""},
]

RISKS = [
    {"icon":"📈","title":"BTC $80K 阻力 + 获利盘",    "body":"$80K 是重要心理关口。若未能突破，可能触发矿工股获利抛售，IREN/CIFR/WULF 均有大幅当日涨幅。"},
    {"icon":"🌍","title":"地缘政治消息依赖性风险",        "body":"近期涨幅部分受停火消息推动。地缘政治消息面变化极快，任何反复都可能令市场快速回撤。"},
    {"icon":"📉","title":"WULF CEO 减持信号",           "body":"CEO 大量减持 + 大额 put 期权成交是持续对冲信号。内部人行为往往先于价格走弱。"},
    {"icon":"💧","title":"IREN 稀释风险未消除",          "body":"$6B ATM 增发随时可能执行，BTC 上涨带来的反弹恰恰是管理层执行增发的最佳窗口。"},
    {"icon":"🔥","title":"NBIS 高烧钱 + 高估值风险",    "body":"P/S 70x，Q4 净亏 $250M，LT 债务 $4.1B，每季 CapEx 超 $2B。若 AI 云需求放缓，高估值可能快速回调。"},
]

# ── Fetch live prices ─────────────────────────────────────────────────────────
live_prices = {}  # yfSym -> (price, ch24_pct)
ch7_map     = {}  # yfSym -> ch7_pct

if HAS_YF:
    # All yfinance symbols — HUT.TO fetched independently (CAD, different from HUT USD)
    stock_syms = list({t["yf"] for t in TICKERS if t.get("yf")}) + ["HUT.TO"]

    # 1. Current price + 24h change via fast_info (updates ~15 min during market hours)
    print("Fetching current prices via fast_info...")
    for ysym in stock_syms:
        try:
            fi         = yf.Ticker(ysym).fast_info
            price      = fi.last_price
            prev_close = fi.previous_close
            if price and price > 0:
                ch24 = (price - prev_close) / prev_close * 100 if (prev_close and prev_close > 0) else None
                live_prices[ysym] = (price, ch24)
                tag = f"{ch24:+.2f}%" if ch24 is not None else "n/a"
                print(f"  {ysym}: {price:.2f}  24h={tag}")
        except Exception as e:
            print(f"  {ysym} fast_info error: {e}")

    # 2. 7-day change via 10-day daily history
    print("Fetching 7-day history...")
    try:
        raw    = yf.download(stock_syms, period="10d", progress=False, auto_adjust=True)
        closes = raw["Close"]
        # yfinance returns a Series (not DataFrame) when only 1 symbol — normalise
        if hasattr(closes, "squeeze") and len(stock_syms) == 1:
            closes = closes.to_frame(name=stock_syms[0])
        for ysym in stock_syms:
            try:
                series = (closes[ysym] if ysym in closes.columns else closes.squeeze()).dropna()
                if len(series) >= 6:
                    p_now = live_prices.get(ysym, (None,))[0] or float(series.iloc[-1])
                    p_7d  = float(series.iloc[-6])   # ~5 trading days ≈ 1 calendar week
                    ch7_map[ysym] = (p_now - p_7d) / p_7d * 100
                    print(f"  {ysym} 7d: {ch7_map[ysym]:+.2f}%")
            except Exception as e:
                print(f"  {ysym} 7d error: {e}")
    except Exception as e:
        print(f"7-day history download failed: {e}")

# ── Fetch live crypto via CoinGecko (free, no key) ────────────────────────────
if HAS_REQ:
    print("Fetching CoinGecko BTC/ETH...")
    try:
        url = ("https://api.coingecko.com/api/v3/simple/price"
               "?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true")
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        cg = resp.json()
        live_prices["BTC"] = (cg["bitcoin"]["usd"],  cg["bitcoin"].get("usd_24h_change"))
        live_prices["ETH"] = (cg["ethereum"]["usd"], cg["ethereum"].get("usd_24h_change"))
        print(f"  BTC: ${cg['bitcoin']['usd']:,.0f}  ETH: ${cg['ethereum']['usd']:,.0f}")
    except Exception as e:
        print(f"CoinGecko failed: {e}")

# ── Apply live prices to TICKERS ──────────────────────────────────────────────
price_display = {}  # sym -> display string

for t in TICKERS:
    sym   = t["sym"]
    # HUT.TO uses its own yfinance fetch; cryptos key by sym; others by yf field
    if sym == "HUT.TO":
        yfkey = "HUT.TO"
    elif t.get("crypto"):
        yfkey = sym
    else:
        yfkey = t.get("yf")

    if yfkey and yfkey in live_prices:
        p, ch24 = live_prices[yfkey]
        if p and p > 0:
            t["price"] = p
        if ch24 is not None:
            t["ch24"] = ch24
    if yfkey and yfkey in ch7_map:
        t["ch7"] = ch7_map[yfkey]

    # Build display string
    p = t["price"]
    if t.get("cad"):
        price_display[sym] = f"CA${p:.2f}"
    elif t.get("crypto"):
        price_display[sym] = f"${int(round(p)):,}"
    elif sym == "VIX":
        price_display[sym] = f"{p:.2f}"
    else:
        price_display[sym] = f"${p:.2f}"

# ── HTML helpers ──────────────────────────────────────────────────────────────
def fmt_pct(v):
    if v is None or (isinstance(v, float) and v != v):
        return "—"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}%"

def ch_style(v):
    if v is None:
        return "color:#888"
    return "color:#1a7a3c;font-weight:600" if v >= 0 else "color:#c02020;font-weight:600"

def sent_color(v):
    if v is None:
        return "#aaa"
    return "#1a7a3c" if v >= 85 else ("#e67e22" if v >= 70 else "#c02020")

def exch_style(exch):
    m = {"NASDAQ":"background:#e8f0fb;color:#1a3a5c",
         "TSX":   "background:#fff3e0;color:#b05000",
         "ETF":   "background:#f0f0f0;color:#555",
         "Index": "background:#f5e8fb;color:#6a1fa0",
         "Crypto":"background:#e6f4ec;color:#1a5c3a"}
    return m.get(exch, "background:#eee;color:#333")

# ── Market pulse summary ──────────────────────────────────────────────────────
btc_p_disp = price_display.get("BTC", "$—")
btc_ch = fmt_pct(next((t["ch24"] for t in TICKERS if t["sym"]=="BTC"), None))
hut_p  = price_display.get("HUT", "$—")
spy_p  = price_display.get("SPY", "$—")
vix_p  = price_display.get("VIX", "—")
nbis_p = price_display.get("NBIS","$—")

pulse = (f"<strong>市场环境：</strong>"
         f"<strong>BTC</strong> {btc_p_disp}（{btc_ch}）矿工股联动；"
         f"<strong>HUT</strong> {hut_p}；<strong>NBIS</strong> {nbis_p}（AI 云）。"
         f"<strong>SPY</strong> {spy_p}；<strong>VIX</strong> {vix_p}。")

# ── Build HTML ────────────────────────────────────────────────────────────────
CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, 'Segoe UI', Arial, sans-serif; background: #f0f4f8; color: #1a2332; font-size: 13px; }
.header { background: linear-gradient(135deg, #1a3a5c 0%, #2d6a9f 100%); color: #fff; padding: 16px 20px 14px; }
.header-top { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.header h1 { font-size: 18px; font-weight: 700; }
.date-badge { background: rgba(255,255,255,0.18); border-radius: 20px; padding: 4px 12px; font-size: 11px; color: #cde; }
.market-pulse { margin-top: 10px; background: rgba(255,255,255,0.1); border-radius: 8px; padding: 10px 14px; font-size: 12px; line-height: 1.65; color: #ddeeff; }
.market-pulse strong { color: #fff; }
.main { padding: 14px 16px; max-width: 980px; margin: 0 auto; }
.section-title { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; color: #1a3a5c; margin: 18px 0 8px; padding-bottom: 5px; border-bottom: 2px solid #2d6a9f; }
table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 6px rgba(0,0,0,0.07); }
th { background: #1a3a5c; color: #fff; padding: 8px 10px; font-size: 11px; font-weight: 600; white-space: nowrap; }
td { padding: 7px 10px; text-align: center; border-bottom: 1px solid #eef2f7; font-size: 12px; vertical-align: middle; }
tr:last-child td { border-bottom: none; }
tr:nth-child(even) td { background: #f7fafd; }
tr:hover td { background: #eef4fb; }
.hutca td { background: #fffbf0 !important; border-left: 3px solid #e67e22; }
.watch-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@media (max-width: 640px) { .watch-grid { grid-template-columns: 1fr; } }
.watch-card { background: #fff; border-radius: 10px; box-shadow: 0 1px 6px rgba(0,0,0,0.07); overflow: hidden; }
.wc-head { padding: 10px 14px 8px; border-bottom: 1px solid #eef2f7; display: flex; align-items: center; flex-wrap: wrap; gap: 4px; }
.wc-body { padding: 10px 14px; }
.wc-label { font-size: 10px; font-weight: 700; text-transform: uppercase; color: #2d6a9f; margin-top: 8px; margin-bottom: 3px; }
.wc-label:first-child { margin-top: 0; }
.wc-text { font-size: 12px; color: #445; line-height: 1.5; }
.wc-quote { background: #f5f7fa; border-left: 3px solid #2d6a9f; padding: 6px 10px; border-radius: 0 6px 6px 0; font-size: 11px; color: #556; line-height: 1.5; margin-top: 4px; font-style: italic; }
.wc-tag { display: inline-block; border-radius: 4px; padding: 2px 7px; font-size: 10.5px; font-weight: 600; margin: 2px 3px 2px 0; }
.bull { background: #e6f4ec; color: #1a7a3c; }
.bear { background: #fdecea; color: #c02020; }
.risk-list { display: flex; flex-direction: column; gap: 8px; }
.risk-item { background: #fff; border-radius: 8px; padding: 10px 14px; display: flex; gap: 10px; align-items: flex-start; box-shadow: 0 1px 4px rgba(0,0,0,0.05); border-left: 4px solid #e67e22; }
.risk-icon { font-size: 16px; flex-shrink: 0; line-height: 1.4; }
.risk-title { font-weight: 700; font-size: 12px; color: #c06000; }
.risk-body { font-size: 12px; color: #556; line-height: 1.5; }
.footer { text-align: center; color: #aab; font-size: 11px; padding: 16px 0 20px; }
a { color: #2d6a9f; }
"""

# Ticker table rows
rows = ""
for t in TICKERS:
    sym  = t["sym"]
    pdsp = price_display.get(sym, "—")
    ch24 = t.get("ch24")
    ch7  = t.get("ch7")
    sent = t.get("sent")
    sc   = sent_color(sent)
    hutca_cls = ' class="hutca"' if t.get("hutca") else ""
    price_col = f"color:#b05000;font-weight:500" if t.get("cad") else "font-weight:500"

    if sent is None:
        sent_html = '<span style="color:#888">—</span>'
    else:
        sent_html = (f'<div style="display:flex;align-items:center;gap:5px;justify-content:center">'
                     f'<div style="width:40px;height:6px;background:#e8ecf0;border-radius:3px;overflow:hidden">'
                     f'<div style="width:{sent}%;height:100%;background:{sc};border-radius:3px"></div></div>'
                     f'<span style="font-size:11px;font-weight:600;color:{sc}">{sent}%</span></div>')

    rows += f'<tr{hutca_cls}>'
    rows += f'<td style="text-align:left;font-weight:700;color:#1a3a5c">{sym}</td>'
    rows += f'<td style="text-align:left"><span style="font-size:9.5px;font-weight:600;border-radius:3px;padding:1px 5px;{exch_style(t["exch"])}">{t["exch"]}</span></td>'
    rows += f'<td style="{price_col}">{pdsp}</td>'
    rows += f'<td style="{ch_style(ch24)}">{fmt_pct(ch24)}</td>'
    rows += f'<td style="{ch_style(ch7)}">{fmt_pct(ch7)}</td>'
    rows += f'<td>{sent_html}</td>'
    rows += f'<td style="color:#888">{t["rank"]}</td>'
    rows += f'<td style="text-align:left;font-size:11.5px;color:#445;line-height:1.4">{t["note"]}</td>'
    rows += '</tr>\n'

# Watchlist cards
cards = ""
for w in WATCHLIST:
    sym      = w["sym"]
    pk       = w["price_key"]
    ck       = w["ch_key"]
    pdsp     = price_display.get(pk, "—")
    ch_val   = next((t["ch24"] for t in TICKERS if t["sym"] == ck), None)
    ch_str   = fmt_pct(ch_val)
    ch_st    = ch_style(ch_val)

    bull_tags = "".join(f'<span class="wc-tag bull">▲ {b}</span>' for b in w["bull"])
    bear_tags = "".join(f'<span class="wc-tag bear">▼ {b}</span>' for b in w["bear"])

    cards += f'''<div class="watch-card">
  <div class="wc-head">
    <span style="font-size:15px;font-weight:800;color:#1a3a5c">{w["emoji"]} {sym}</span>
    <span style="font-size:13px;font-weight:600;color:#333;margin-left:6px">{pdsp}</span>
    <span style="{ch_st};font-size:12px;margin-left:4px">{ch_str}</span>
  </div>
  <div class="wc-body">
    <div class="wc-label">为何值得关注</div><div class="wc-text">{w["why"]}</div>
    <div class="wc-label">观点</div><div style="line-height:1.8">{bull_tags}{bear_tags}</div>
    <div class="wc-label">机构动作</div><div class="wc-text">{w["inst"]}</div>
    <div class="wc-label">热门帖</div><div class="wc-quote">{w["quote"]}</div>
  </div>
</div>
'''

# Risk items
risk_html = ""
for r in RISKS:
    risk_html += f'''<div class="risk-item">
  <span class="risk-icon">{r["icon"]}</span>
  <div>
    <div class="risk-title">{r["title"]}</div>
    <div class="risk-body">{r["body"]}</div>
  </div>
</div>
'''

# Full page
html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Emily 的投资早报 — {today_str}</title>
<style>{CSS}</style>
</head>
<body>

<div class="header">
  <div class="header-top">
    <h1>📊 Emily 的投资早报</h1>
    <span class="date-badge">{today_cn} {weekday_cn}</span>
  </div>
  <div class="market-pulse">{pulse}</div>
</div>

<div class="main">
  <div class="section-title">持仓标的速览</div>
  <div style="overflow-x:auto">
  <table>
    <thead><tr>
      <th style="text-align:left">标的</th>
      <th style="text-align:left">交易所</th>
      <th>价格</th><th>24h</th><th>7日</th>
      <th>情绪*</th><th>AltRank</th>
      <th style="text-align:left">要点</th>
    </tr></thead>
    <tbody>
{rows}    </tbody>
  </table>
  </div>
  <div style="font-size:11px;color:#999;margin-top:5px;padding-left:4px;">
    价格来源：yfinance（股票）· CoinGecko（BTC/ETH）<br>
    * 情绪分来自 LunarCrush（手动更新）；NBIS 不在 LunarCrush 覆盖范围。
  </div>

  <div class="section-title">值得关注（按优先级）</div>
  <div class="watch-grid">
{cards}  </div>

  <div class="section-title">风险提示</div>
  <div class="risk-list">
{risk_html}  </div>
</div>

<div class="footer">
  数据来源：yfinance（股票实时）· CoinGecko（BTC/ETH 实时）<br>
  情绪分需手动更新 · 本报告由 GitHub Actions 自动生成，仅供参考，不构成投资建议。<br>
  最后更新：{today_str}
</div>

</body>
</html>"""

# ── Write to index.html ───────────────────────────────────────────────────────
with open("index.html", "w", encoding="utf-8") as f:
    f.write(html)
print(f"✅ index.html generated ({len(html):,} chars) for {today_str}")
