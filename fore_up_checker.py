#!/usr/bin/env python3

import json
import requests
import smtplib
import os
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

# Email configuration
SENDER_EMAIL = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
TO_EMAILS = os.getenv("EMAIL_RECEIVERS", "")

# Booking configuration
DATE = os.getenv("TARGET_DATE", "")
TIME = os.getenv("TIME_OF_DAY", "all")
PLAYERS = int(os.getenv("PLAYERS", "2"))
BOOKING_CLASS = os.getenv("BOOKING_CLASS", "XXXXX")
SCHEDULE_ID = os.getenv("SCHEDULE_ID", "XXXX")
SCHEDULE_IDS = os.getenv("SCHEDULE_IDS", "XXXX,XXXX").split(",")

SEEN_FILE = 'last_sent.txt'


def tee_time_key(t):
    return f"{t.get('time')}|{t.get('course_name')}|{t.get('holes')}"


def load_seen_keys():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, 'r') as f:
        content = f.read().strip()
        if not content:
            return set()
        try:
            return set(json.loads(content))
        except (ValueError, TypeError):
            return set()


def save_seen_keys(keys):
    with open(SEEN_FILE, 'w') as f:
        json.dump(list(keys), f)


def send_notification(new_tee_times):
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = TO_EMAILS
    msg['Subject'] = "⛳️ Tee Time Alert!"

    body = "New tee times just opened up!\n\n"
    for t in new_tee_times:
        body += f"Available Spots: {t.get('available_spots')}, Time: {t.get('time')}, Holes: {t.get('holes')}, Course: {t.get('course_name')}\n"
    body += f"\nBook here: https://foreupsoftware.com/index.php/booking/XXXXX/{SCHEDULE_ID}#/teetimes"

    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, EMAIL_PASSWORD)
            server.send_message(msg)
        print("✅ Notification sent.")
    except Exception as e:
        print("❌ Failed to send notification:", e)


def check_tee_times():
    url = "https://foreupsoftware.com/index.php/api/booking/times"

    params = {
        "time": TIME,
        "date": DATE,
        "holes": "all",
        "players": PLAYERS,
        "booking_class": BOOKING_CLASS,
        "schedule_id": SCHEDULE_ID,
        "schedule_ids[]": SCHEDULE_IDS,
        "specials_only": 0,
        "api_key": "",
    }

    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "accept-language": "en-US,en;q=0.9,pt;q=0.8",
        "api-key": "",
        "priority": "u=1, i",
        "referer": f"https://foreupsoftware.com/index.php/booking/XXXXX/{SCHEDULE_ID}",
        "sec-ch-ua": '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        "x-fu-golfer-location": "foreup",
        "x-requested-with": "XMLHttpRequest",
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        print(f"Checked at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if response.ok:
            tee_times = response.json()
            if tee_times:
                seen = load_seen_keys()
                new_times = [t for t in tee_times if tee_time_key(t) not in seen]
                if new_times:
                    print(f"🎉 Found {len(new_times)} new tee times!")
                    send_notification(new_times)
                    save_seen_keys({tee_time_key(t) for t in tee_times})
                else:
                    print(f"Found {len(tee_times)} tee times but none are new.")
            else:
                print("No tee times available.")
                save_seen_keys(set())
        else:
            print(f"Request failed with status code {response.status_code}")
    except Exception as e:
        print("Error checking tee times:", e)


def main():
    check_tee_times()


if __name__ == "__main__":
    main()