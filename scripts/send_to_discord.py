"""
AI朝刊 → Discord 自動配信スクリプト
GitHub Actions から呼び出し、Markdownニュースレターを
Discord Webhook 経由で Embed 形式で投稿する。

Embed の description 上限は 4096 文字だが、安全マージンを取って
セクション単位（---区切り）で分割し、複数 Embed として送信する。
1リクエストあたり最大10 Embed（合計6000文字）なので、
それを超える場合は複数リクエストに分ける。
"""

import os
import sys
import json
import re
import urllib.request
import urllib.error
import time

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
MAX_EMBED_DESC = 4096       # Discord Embed description 上限
MAX_EMBEDS_PER_REQ = 10     # 1リクエストあたりの Embed 数上限
EMBED_COLOR = 0x2F3136       # ダークテーマに合う色


def read_markdown(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def extract_title(md: str) -> str:
    """最初の # 見出しをタイトルとして抽出"""
    for line in md.splitlines():
        if line.startswith("# "):
            return line.lstrip("# ").strip()
    return "AI朝刊"


def split_sections(md: str) -> list[str]:
    """
    --- (水平線) でセクション分割。
    各セクションが MAX_EMBED_DESC を超える場合はさらに分割。
    """
    raw_sections = re.split(r"\n---\n", md)
    sections = []
    for sec in raw_sections:
        sec = sec.strip()
        if not sec:
            continue
        if len(sec) <= MAX_EMBED_DESC:
            sections.append(sec)
        else:
            # 長いセクションは見出し単位 (##) でさらに分割
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


def build_embeds(sections: list[str], title: str) -> list[dict]:
    """セクションごとに Embed を構築"""
    embeds = []
    for i, sec in enumerate(sections):
        embed = {
            "description": sec[:MAX_EMBED_DESC],
            "color": EMBED_COLOR,
        }
        # 最初の Embed にだけタイトルを付ける
        if i == 0:
            embed["title"] = title
        # 最後の Embed にタイムスタンプとフッター
        if i == len(sections) - 1:
            embed["footer"] = {
                "text": "AI朝刊 ― 自動配信 via GitHub Actions"
            }
        embeds.append(embed)
    return embeds


def send_webhook(embeds: list[dict]) -> None:
    """Embed を MAX_EMBEDS_PER_REQ 個ずつバッチ送信"""
    for i in range(0, len(embeds), MAX_EMBEDS_PER_REQ):
        batch = embeds[i : i + MAX_EMBEDS_PER_REQ]
        payload = json.dumps({"embeds": batch}).encode("utf-8")

        req = urllib.request.Request(
            WEBHOOK_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                if resp.status == 204:
                    print(f"✅ Batch {i // MAX_EMBEDS_PER_REQ + 1} 送信成功")
                else:
                    print(f"⚠️ Status: {resp.status}")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            print(f"❌ HTTPError {e.code}: {body}", file=sys.stderr)
            sys.exit(1)

        # レートリミット回避
        if i + MAX_EMBEDS_PER_REQ < len(embeds):
            time.sleep(1)


def send_file_fallback(path: str) -> None:
    """
    Embed が何らかの理由で失敗した場合のフォールバック。
    Markdown ファイルをそのまま添付送信する。
    """
    import mimetypes

    boundary = "----FormBoundary7MA4YWxkTrZu0gW"
    filename = os.path.basename(path)
    mime = mimetypes.guess_type(path)[0] or "text/markdown"

    with open(path, "rb") as f:
        file_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="content"\r\n\r\n'
        f"📰 AI朝刊（ファイル添付）\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("utf-8") + file_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        WEBHOOK_URL,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        print(f"📎 ファイル送信: Status {resp.status}")


def main():
    if not WEBHOOK_URL:
        print("❌ DISCORD_WEBHOOK_URL が設定されていません", file=sys.stderr)
        sys.exit(1)

    # 引数でMarkdownファイルパスを受け取る
    if len(sys.argv) < 2:
        print("Usage: python send_to_discord.py <markdown_file>", file=sys.stderr)
        sys.exit(1)

    md_path = sys.argv[1]
    if not os.path.exists(md_path):
        print(f"❌ ファイルが見つかりません: {md_path}", file=sys.stderr)
        sys.exit(1)

    md = read_markdown(md_path)
    title = extract_title(md)
    sections = split_sections(md)

    print(f"📄 {title}")
    print(f"📦 {len(sections)} セクションに分割")

    embeds = build_embeds(sections, title)

    try:
        send_webhook(embeds)
        print("🎉 Discord 配信完了!")
    except Exception as e:
        print(f"⚠️ Embed送信失敗、ファイル添付にフォールバック: {e}")
        send_file_fallback(md_path)


if __name__ == "__main__":
    main()
