import os
import sys
import json
import re
import urllib.request
import urllib.error
import time

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
MAX_EMBED_DESC = 4096
MAX_EMBEDS_PER_REQ = 10
EMBED_COLOR = 0x2F3136

def read_markdown(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def extract_title(md):
    for line in md.splitlines():
        if line.startswith("# "):
            return line.lstrip("# ").strip()
    return "AI News"

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

def build_embeds(sections, title):
    embeds = []
    for i, sec in enumerate(sections):
        embed = {"description": sec[:MAX_EMBED_DESC], "color": EMBED_COLOR}
        if i == 0:
            embed["title"] = title
        if i == len(sections) - 1:
            embed["footer"] = {"text": "AI News - auto delivery via GitHub Actions"}
        embeds.append(embed)
    return embeds

def send_webhook(embeds):
    for i in range(0, len(embeds), MAX_EMBEDS_PER_REQ):
        batch = embeds[i : i + MAX_EMBEDS_PER_REQ]
        payload = json.dumps({"embeds": batch}).encode("utf-8")
        req = urllib.request.Request(
            WEBHOOK_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "DiscordBot (https://github.com, 1.0)",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                print(f"Batch {i // MAX_EMBEDS_PER_REQ + 1} sent: {resp.status}")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            print(f"HTTPError {e.code}: {body}", file=sys.stderr)
            sys.exit(1)
        if i + MAX_EMBEDS_PER_REQ < len(embeds):
            time.sleep(1)

def main():
    if not WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL not set", file=sys.stderr)
        sys.exit(1)
    if len(sys.argv) < 2:
        print("Usage: python send_to_discord.py <markdown_file>", file=sys.stderr)
        sys.exit(1)
    md_path = sys.argv[1]
    if not os.path.exists(md_path):
        print(f"File not found: {md_path}", file=sys.stderr)
        sys.exit(1)
    md = read_markdown(md_path)
    title = extract_title(md)
    sections = split_sections(md)
    print(f"Title: {title}")
    print(f"Sections: {len(sections)}")
    embeds = build_embeds(sections, title)
    send_webhook(embeds)
    print("Done!")

if __name__ == "__main__":
    main()
