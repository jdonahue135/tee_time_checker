#!/usr/bin/env python3

import json
import requests
import smtplib
import os
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

SENDER_EMAIL = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

try:
    _config = json.loads(os.getenv("CONFIG", "{}"))
except (ValueError, TypeError):
    _config = {}

TO_EMAILS = _config.get("emailReceivers", "")
BOOKING_CLASS = _config.get("bookingClass", "XXXXX")
SCHEDULE_ID = _config.get("scheduleId", "XXXX")
SCHEDULE_IDS = _config.get("scheduleIds", "XXXX,XXXX").split(",")
SLOTS = _config.get("slots", [])

DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


def next_occurrence(day_name):
    """Return the next date (including today) matching day_name, formatted MM-DD-YYYY."""
    target = DAYS.index(day_name.lower())
    today = datetime.now()
    days_ahead = (target - today.weekday()) % 7
    result = today + timedelta(days=days_ahead)
    return result.strftime('%m-%d-%Y')


def tee_time_key(t):
    return f"{t.get('time')}|{t.get('course_name')}|{t.get('holes')}"


def load_seen_keys(slot_id):
    filename = f'last_sent_{slot_id}.txt'
    if not os.path.exists(filename):
        return set()
    with open(filename, 'r') as f:
        content = f.read().strip()
        if not content:
            return set()
        try:
            return set(json.loads(content))
        except (ValueError, TypeError):
            return set()


def save_seen_keys(keys, slot_id):
    filename = f'last_sent_{slot_id}.txt'
    with open(filename, 'w') as f:
        json.dump(list(keys), f)


def send_notification(new_tee_times, label):
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = TO_EMAILS
    msg['Subject'] = f"⛳️ Tee Time Alert — {label}"

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


def check_slot(slot):
    slot_id = slot['id']
    day = slot['day']
    time = slot['time']
    players = int(slot['players'])
    date = next_occurrence(day)
    label = f"{day.capitalize()} {time.capitalize()}"

    print(f"\n--- Checking slot: {label} ({players} players) on {date} ---")

    url = "https://foreupsoftware.com/index.php/api/booking/times"

    params = {
        "time": time,
        "date": date,
        "holes": "all",
        "players": players,
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
                seen = load_seen_keys(slot_id)
                new_times = [t for t in tee_times if tee_time_key(t) not in seen]
                if new_times:
                    print(f"🎉 Found {len(new_times)} new tee times!")
                    send_notification(new_times, label)
                    save_seen_keys({tee_time_key(t) for t in tee_times}, slot_id)
                else:
                    print(f"Found {len(tee_times)} tee times but none are new.")
            else:
                print("No tee times available.")
                save_seen_keys(set(), slot_id)
        else:
            print(f"Request failed with status code {response.status_code}")
    except Exception as e:
        print("Error checking tee times:", e)


def main():
    if not SLOTS:
        print("No search slots configured.")
        return

    for slot in SLOTS:
        check_slot(slot)


if __name__ == "__main__":
    main()
