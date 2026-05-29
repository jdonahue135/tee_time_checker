#!/usr/bin/env python3

import base64
import json
import requests
import smtplib
import os
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

SENDER_EMAIL = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
FOREUP_EMAIL = os.getenv("FOREUP_EMAIL")
FOREUP_PASSWORD = os.getenv("FOREUP_PASSWORD")

try:
    _config = json.loads(os.getenv("CONFIG", "{}"))
except (ValueError, TypeError):
    _config = {}

TO_EMAILS = _config.get("emailReceivers", "")
BOOKING_CLASS = _config.get("bookingClass", "8436")
SCHEDULE_ID = _config.get("scheduleId", "6992")
SCHEDULE_IDS = _config.get("scheduleIds", "6991,6992").split(",")
SLOTS = _config.get("slots", [])

DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


JWT_CACHE_FILE = "foreup_jwt.json"


def _jwt_exp(token):
    payload = token.split('.')[1]
    payload += '=' * (-len(payload) % 4)
    return json.loads(base64.b64decode(payload)).get('exp', 0)


def _load_cached_jwt():
    if not os.path.exists(JWT_CACHE_FILE):
        return None
    try:
        with open(JWT_CACHE_FILE) as f:
            token = json.load(f).get('jwt')
        if token and _jwt_exp(token) - time.time() > 300:
            return token
    except Exception:
        pass
    return None


def _save_jwt(token):
    with open(JWT_CACHE_FILE, 'w') as f:
        json.dump({'jwt': token}, f)


def login(course_id):
    cached = _load_cached_jwt()
    if cached:
        print("Using cached JWT.")
        return cached

    url = "https://foreupsoftware.com/index.php/api/booking/users/login"
    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "x-fu-golfer-location": "foreup",
        "x-requested-with": "XMLHttpRequest",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    }
    data = {"username": FOREUP_EMAIL, "password": FOREUP_PASSWORD, "course_id": course_id}
    resp = requests.post(url, headers=headers, data=data)
    resp.raise_for_status()
    token = resp.json().get("jwt")
    exp = datetime.utcfromtimestamp(_jwt_exp(token)).strftime('%Y-%m-%d %H:%M UTC')
    print(f"Logged in. JWT expires {exp}.")
    _save_jwt(token)
    return token


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


def fmt_time(raw):
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M', '%H:%M:%S', '%H:%M'):
        try:
            return datetime.strptime(raw, fmt).strftime('%I:%M %p').lstrip('0')
        except (ValueError, TypeError):
            pass
    return raw

def send_notification(new_tee_times, label, date, to_emails, booking_url, course_name=""):
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_emails
    subject_course = f" — {course_name}" if course_name else ""
    msg['Subject'] = f"⛳️ Tee Time Alert{subject_course} — {label} ({date})"

    body = "New tee times just opened up!\n\n"
    for t in new_tee_times:
        body += f"Available Spots: {t.get('available_spots')}, Time: {fmt_time(t.get('time'))}, Holes: {t.get('holes')}, Course: {t.get('course_name')}\n"
    body += f"\nBook here: {booking_url}"

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

    booking_class = slot.get('bookingClass', BOOKING_CLASS)
    schedule_id = slot.get('scheduleId', SCHEDULE_ID)
    schedule_ids = slot.get('scheduleIds', ','.join(SCHEDULE_IDS)).split(',')
    course_id = slot.get('courseId', '21120')
    course_name = slot.get('courseName', '')
    requires_auth = slot.get('requiresAuth', False)

    booking_url = f"https://foreupsoftware.com/index.php/booking/{course_id}/{schedule_id}#/teetimes"

    print(f"\n--- Checking slot: {label} ({players} players) on {date} ---")

    params = {
        "time": time,
        "date": date,
        "holes": "all",
        "players": players,
        "booking_class": booking_class,
        "schedule_id": schedule_id,
        "schedule_ids[]": schedule_ids,
        "specials_only": 0,
        "api_key": "",
    }

    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "accept-language": "en-US,en;q=0.9,pt;q=0.8",
        "api-key": "",
        "priority": "u=1, i",
        "referer": f"https://foreupsoftware.com/index.php/booking/{course_id}",
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

    if requires_auth:
        try:
            jwt = login(course_id)
            headers["x-authorization"] = f"Bearer {jwt}"
        except Exception as e:
            print(f"Login failed: {e}")
            return

    try:
        response = requests.get("https://foreupsoftware.com/index.php/api/booking/times", headers=headers, params=params)
        print(f"Checked at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if response.ok:
            tee_times = response.json()
            if tee_times:
                seen = load_seen_keys(slot_id)
                new_times = [t for t in tee_times if tee_time_key(t) not in seen]
                if new_times:
                    print(f"🎉 Found {len(new_times)} new tee times!")
                    slot_recips = slot.get('recipients', [])
                    to_emails = ','.join(slot_recips) if slot_recips else TO_EMAILS
                    if not to_emails:
                        print("No recipients configured, skipping notification.")
                    else:
                        send_notification(new_times, label, date, to_emails, booking_url, course_name)
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
