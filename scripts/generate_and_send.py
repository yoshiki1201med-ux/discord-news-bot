import os
import sys
import json
import re
import urllib.request
import urllib.error
import time
import datetime

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
MODEL = "claude-sonnet-4-20250514"
CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")
NEWS_DIR = os.path.join(os.path.dirname(__file__), "..", "news")
MAX_EMBED_DESC = 4096
MAX_EMBEDS_PER_REQ = 10
EMBED_COLOR = 0x2F3136

def fetch_market_data():
    try:
        import yfinance as yf
    except ImportError:
        return None
    tickers = {
        "NASDAQ": "^IXIC",
        "DOW": "^DJI",
        "S&P500": "^GSPC",
        "日経225先物": "NKD=F",
        "VIX": "^VIX",
        "WTI原油": "CL=F",
        "米10年債利回り": "^TNX",
        "ドル円": "JPY=X",
    }
    results = {}
    for name, symbol in tickers.items():
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="2d")
            if len(hist) >= 1:
                latest = hist.iloc[-1]
                prev = hist.iloc[-2] if len(hist) >= 2 else latest
                close_val = latest["Close"]
                change = close_val - prev["Close"]
                change_pct = (change / prev["Close"]) * 100 if prev["Close"] != 0 else 0
                results[name] = {
                    "close": round(close_val, 2),
                    "change": round(change, 2),
                    "change_pct": round(change_pct, 2),
                }
        except Exception as e:
            print(f"Warning: {name} failed: {e}")
    return results

def format_market_data(data):
    if not data:
        return "(market data unavailable)"
    lines = []
    for name, vals in data.items():
        arrow = "🔺" if vals["change"] > 0 else "🔻" if vals["change"] < 0 else "➡️"
        sign = "+" if vals["change"] > 0 else ""
        lines.append(f"| {name} | {vals['close']:,.2f} | {arrow} {sign}{vals['change']:,.2f} ({sign}{vals['change_pct']:.2f}%) |")
    header = "| 指標 | 終値/現在値 | 前日比 |\n|------|-----------|--------|\n"
    return header + "\n".join(lines)

def load_holdings():
    path = os.path.join(CONFIG_DIR, "holdings.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("holdings", [])

def fetch_holdings_data(holdings):
    if not holdings:
        return "(holdings not configured)"
    try:
        import yfinance as yf
    except ImportError:
        return "(yfinance not installed)"
    lines = []
    for h in holdings:
        try:
            t = yf.Ticker(h["ticker"])
            hist = t.history(period="5d")
            if len(hist) < 2:
                lines.append(f"| {h['name']} | - | - | - |")
                continue
            latest = hist.iloc[-1]
            prev = hist.iloc[-2]
            close_val = latest["Close"]
            change_pct = ((close_val - prev["Close"]) / prev["Close"]) * 100
            if len(hist) >= 5:
                week_change = ((close_val - hist.iloc[0]["Close"]) / hist.iloc[0]["Close"]) * 100
            else:
                week_change = change_pct
            score = change_pct * 0.6 + week_change * 0.4
            if score >= 3:
                weather = "☀️快晴"
            elif score >= 1:
                weather = "🌤️晴れ"
            elif score >= -1:
                weather = "⛅曇り"
            elif score >= -3:
                weather = "🌧️雨"
            else:
                weather = "⛈️嵐"
            sign = "+" if change_pct > 0 else ""
            wsign = "+" if week_change > 0 else ""
            lines.append(f"| {weather} {h['name']} | {close_val:,.1f} | {sign}{change_pct:.2f}% | {wsign}{week_change:.1f}% |")
        except Exception as e:
            lines.append(f"| ? {h['name']} | - | error | - |")
            print(f"Warning: {h['name']} failed: {e}")
    header = "| 銘柄 | 終値 | 前日比 | 週間 |\n|------|------|--------|------|\n"
    return header + "\n".join(lines)

def generate_article(market_text, holdings_text):
    today = datetime.date.today().strftime("%Y年%m月%d日")
    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    dow = weekdays[datetime.date.today().weekday()]
    system_prompt = f"""あなたは日本株投資家向けのAI朝刊ニュースレターのライターです。
今日は{today}（{dow}）です。

以下のフォーマットでMarkdownの朝刊を作成してください。

# 📰 AI朝刊 ― {today}（{dow}）

> **[今日の一行サマリー]**

---

## 🌍 市況サマリー

{market_text}

---

## 🔑 今日の結論
[今日の相場をどう見るか、3-5行で簡潔に]

---

## 📈 注目セクター・テーマ
[強い領域・弱い領域を簡潔に整理]

---

## 📌 注目ニュース
[最新のニュースから3-5本、それぞれ2-3行で要点整理]

---

## 🌤️ 手持ち株 天気予報

{holdings_text}

---

*⚠️ 本記事はAIによる自動生成です。特定銘柄の売買推奨ではありません。投資判断はご自身でお願いします。*

ルール:
- Web検索で最新のニュースを調べてから書くこと
- 日本株市場に影響する海外ニュース、地政学、政策、決算を中心に
- 簡潔に、箇条書きや表を活用して読みやすく
- 推測や予想は断定しない
"""
    payload = {
        "model": MODEL,
        "max_tokens": 4096,
        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
        "messages": [{"role": "user", "content": "今日の日本株朝刊ニュースレターを作成してください。最新ニュースをWeb検索して、投資家目線で重要なポイントを整理してください。"}],
        "system": system_prompt,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"Claude API Error {e.code}: {body}", file=sys.stderr)
        sys.exit(1)
    text_parts = []
    for block in result.get("content", []):
        if block.get("type") == "text":
            text_parts.append(block["text"])
    return "\n".join(text_parts)

def save_article(md):
    os.makedirs(NEWS_DIR, exist_ok=True)
    today = datetime.date.today().strftime("%Y-%m-%d")
    path = os.path.join(NEWS_DIR, f"{today}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Saved: {path}")
    return path

def split_sections(md):
    raw_sections = re.split(r"\n---\n", md)
    sections = []
    for sec in raw_sections:
        sec = sec.strip()
        if not sec:
            continue
        if len(sec) <= MAX_EMBED_DESC:
            sections.append(sec)
        else:
            subsections = re.split(r"\n(?=## )", sec)
            buf = ""
            for sub in subsections:
                if len(buf) + len(sub) + 2 > MAX_EMBED_DESC:
                    if buf:
                        sections.append(buf.strip())
                    buf = sub
                else:
                    buf = buf + "\n\n" + sub if buf else sub
            if buf.strip():
                sections.append(buf.strip())
    return sections

def extract_title(md):
    for line in md.splitlines():
        if line.startswith("# "):
            return line.lstrip("# ").strip()
    return "AI朝刊"

def send_to_discord(md):
    title = extract_title(md)
    sections = split_sections(md)
    print(f"Title: {title}")
    print(f"Sections: {len(sections)}")
    embeds = []
    for i, sec in enumerate(sections):
        embed = {"description": sec[:MAX_EMBED_DESC], "color": EMBED_COLOR}
        if i == 0:
            embed["title"] = title
        if i == len(sections) - 1:
            embed["footer"] = {"text": "AI朝刊 - 毎朝自動配信 via GitHub Actions"}
        embeds.append(embed)
    for i in range(0, len(embeds), MAX_EMBEDS_PER_REQ):
        batch = embeds[i : i + MAX_EMBEDS_PER_REQ]
        payload = json.dumps({"embeds": batch}).encode("utf-8")
        req = urllib.request.Request(
            DISCORD_WEBHOOK_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "DiscordBot (https://github.com, 1.0)",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                print(f"Discord batch {i // MAX_EMBEDS_PER_REQ + 1} sent: {resp.status}")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            print(f"Discord Error {e.code}: {body}", file=sys.stderr)
            sys.exit(1)
        if i + MAX_EMBEDS_PER_REQ < len(embeds):
            time.sleep(1)

def main():
    if not ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    if not DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL not set", file=sys.stderr)
        sys.exit(1)
    print("=" * 50)
    print("AI朝刊 自動生成・配信")
    print("=" * 50)
    print("\n[1/4] 市場データ取得中...")
    market_data = fetch_market_data()
    market_text = format_market_data(market_data)
    print(market_text)
    print("\n[2/4] 手持ち株データ取得中...")
    holdings = load_holdings()
    holdings_text = fetch_holdings_data(holdings)
    print(holdings_text)
    print("\n[3/4] Claude APIで記事生成中...")
    article = generate_article(market_text, holdings_text)
    save_article(article)
    print(f"記事生成完了 ({len(article)} 文字)")
    print("\n[4/4] Discord配信中...")
    send_to_discord(article)
    print("\nDone!")

if __name__ == "__main__":
    main()
