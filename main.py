import feedparser
import requests
import time
import os
import json

# ---- CẤU HÌNH ----
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# Danh sách Nitter instances (dự phòng nếu 1 instance bị down)
NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.catsarch.com",
    "https://nitter.tiekoetter.com",
    "https://nitter.space"
]

CHECK_INTERVAL = 300  # 10 phút/lần
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
        json.dump(data, f)

# ---- ĐỌC DANH SÁCH TÀI KHOẢN ----
def load_accounts(filepath="accounts.txt"):
    with open(filepath) as f:
        return [
            line.strip()
            for line in f
            if line.strip() and not line.startswith("#")
        ]

# ---- LẤY RSS FEED (thử từng instance dự phòng) ----
def get_rss_feed(username):
    for instance in NITTER_INSTANCES:
        try:
            url = f"{instance}/{username}/rss"
            feed = feedparser.parse(url)
            if feed.entries:
                return feed.entries
        except Exception as e:
            print(f"  ⚠️  Instance {instance} lỗi: {e}")
    return []

# ---- GỬI TELEGRAM ----
def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        })
    except Exception as e:
        print(f"  ❌ Lỗi gửi Telegram: {e}")

# ---- MAIN ----
def main():
    print("🚀 Khởi động X Monitor (Nitter RSS)...")
    ACCOUNTS = load_accounts()
    print(f"📋 Đang theo dõi {len(ACCOUNTS)} tài khoản: {', '.join('@' + a for a in ACCOUNTS)}")

    seen_ids = load_seen_ids()

    # Khởi tạo seen_ids lần đầu (bỏ qua tweet cũ, không gửi spam)
    print("📥 Đang khởi tạo, bỏ qua tweet cũ...")
    for username in ACCOUNTS:
        if username not in seen_ids:
            entries = get_rss_feed(username)
            if entries:
                seen_ids[username] = entries[0].id
                print(f"  ✅ @{username} — bỏ qua {len(entries)} tweet cũ")
            else:
                print(f"  ⚠️  @{username} — không lấy được feed")
    save_seen_ids(seen_ids)

    send_telegram(
        "✅ <b>X Monitor đã khởi động!</b>\n"
        f"Đang theo dõi <b>{len(ACCOUNTS)}</b> tài khoản:\n" +
        "\n".join(f"• @{u}" for u in ACCOUNTS)
    )
    print(f"\n✅ Bắt đầu vòng lặp, quét mỗi {CHECK_INTERVAL // 60} phút...\n")

    while True:
        for username in ACCOUNTS:
            try:
                entries = get_rss_feed(username)
                if not entries:
                    continue

                last_seen = seen_ids.get(username)
                new_entries = []

                for entry in entries:
                    if entry.id == last_seen:
                        break
                    new_entries.append(entry)

                if new_entries:
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

                time.sleep(3)  # Cách nhau 3s giữa các tài khoản, tránh bị block

            except Exception as e:
                print(f"  ⚠️  Lỗi khi check @{username}: {e}")

        print(f"😴 Chờ {CHECK_INTERVAL // 60} phút...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
