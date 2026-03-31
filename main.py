import feedparser
import requests
import time
import os
import json

# ---- CẤU HÌNH ----
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

NITTER_INSTANCES = [
    "https://rss.xcancel.com",
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://nitter.1d4.us",
]

CHECK_INTERVAL = 600  # 10 phút/lần
SEEN_IDS_FILE = "seen_ids.json"

# ---- LOAD / SAVE SEEN IDS ----
def load_seen_ids():
    try:
        with open(SEEN_IDS_FILE) as f:
            return json.load(f)
    except:
        return {}

def save_seen_ids(data):
    with open(SEEN_IDS_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ---- ĐỌC DANH SÁCH TÀI KHOẢN ----
def load_accounts(filepath="accounts.txt"):
    with open(filepath) as f:
        return [
            line.strip()
            for line in f
            if line.strip() and not line.startswith("#")
        ]

# ---- LẤY RSS FEED ----
def get_rss_feed(username):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    for instance in NITTER_INSTANCES:
        try:
            url = f"{instance}/{username}/rss"
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                feed = feedparser.parse(response.content)
                if feed.entries:
                    return feed.entries
                else:
                    print(f"  ⚠️  {instance} — feed trống cho @{username}")
            else:
                print(f"  ⚠️  {instance} — HTTP {response.status_code}")
        except Exception as e:
            print(f"  ⚠️  {instance} lỗi: {e}")
    return []

# ---- GỬI TELEGRAM ----
def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        })
        if r.status_code != 200:
            print(f"  ❌ Telegram lỗi {r.status_code}: {r.text}")
    except Exception as e:
        print(f"  ❌ Lỗi gửi Telegram: {e}")

# ---- MAIN ----
def main():
    print("🚀 Khởi động X Monitor (Nitter RSS)...")
    ACCOUNTS = load_accounts()
    print(f"📋 Đang theo dõi {len(ACCOUNTS)} tài khoản: {', '.join('@' + a for a in ACCOUNTS)}")

    seen_ids = load_seen_ids()

    # Khởi tạo seen_ids lần đầu (bỏ qua tweet cũ)
    print("📥 Đang khởi tạo, bỏ qua tweet cũ...")
    for username in ACCOUNTS:
        if username not in seen_ids:
            entries = get_rss_feed(username)
            if entries:
                seen_ids[username] = entries[0].id
                print(f"  ✅ @{username} — bỏ qua {len(entries)} tweet cũ (last id: {entries[0].id})")
            else:
                print(f"  ⚠️  @{username} — không lấy được feed lúc khởi động")
    save_seen_ids(seen_ids)

    send_telegram(
        "✅ <b>X Monitor đã khởi động!</b>\n"
        f"Đang theo dõi <b>{len(ACCOUNTS)}</b> tài khoản:\n" +
        "\n".join(f"• @{u}" for u in ACCOUNTS)
    )
    print(f"\n✅ Bắt đầu vòng lặp, quét mỗi {CHECK_INTERVAL // 60} phút...\n")

    while True:
        print(f"\n🔄 Bắt đầu quét lúc {time.strftime('%H:%M:%S')}...")
        for username in ACCOUNTS:
            try:
                entries = get_rss_feed(username)
                if not entries:
                    print(f"  ⚠️  @{username} — không lấy được feed, bỏ qua")
                    time.sleep(3)
                    continue

                last_seen = seen_ids.get(username)

                # DEBUG: in ra để so sánh
                print(f"  🔍 @{username} — tweet mới nhất : {entries[0].id}")
                print(f"  🔍 @{username} — last seen      : {last_seen}")

                new_entries = []
                for entry in entries:
                    if entry.id == last_seen:
                        break
                    new_entries.append(entry)

                if new_entries:
                    print(f"  ✅ @{username} — có {len(new_entries)} tweet mới!")
                    seen_ids[username] = entries[0].id
                    save_seen_ids(seen_ids)

                    for entry in reversed(new_entries):
                        # Chuyển link nitter → x.com
                        link = entry.link
                        for instance in NITTER_INSTANCES:
                            if instance in link:
                                link = link.replace(instance, "https://x.com")
                                break

                        msg = (
                            f"🐦 <b>@{username}</b> vừa đăng:\n\n"
                            f"{entry.title}\n\n"
                            f"🔗 {link}"
                        )
                        send_telegram(msg)
                        print(f"  📨 Đã gửi tweet từ @{username}")
                else:
                    print(f"  — @{username} — không có gì mới")

                time.sleep(3)  # Nghỉ 3s giữa các tài khoản

            except Exception as e:
                print(f"  ⚠️  Lỗi khi check @{username}: {e}")

        print(f"😴 Chờ {CHECK_INTERVAL // 60} phút...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
