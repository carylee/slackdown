import requests
import time
import json
import datetime
from dotenv import load_dotenv
import os

# Load .env config
load_dotenv()
SLACK_TOKEN = os.getenv('SLACK_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')

if not SLACK_TOKEN or not CHANNEL_ID:
    raise ValueError("SLACK_TOKEN and CHANNEL_ID must be set in your .env file.")

HEADERS = {'Authorization': f'Bearer {SLACK_TOKEN}'}
OLDEST_TIMESTAMP = str(int(time.time() - 365 * 24 * 60 * 60 * 2))  # 2 years ago

def check_response(resp):
    if not resp.get("ok"):
        print("❌ Slack API error:", resp.get("error"))
        raise Exception("Slack API error: " + str(resp.get("error")))

def fetch_user_map():
    print("🔍 Fetching user list...")
    user_map = {}
    cursor = None
    total_users = 0

    while True:
        params = {'limit': 200}
        if cursor:
            params['cursor'] = cursor

        res = requests.get("https://slack.com/api/users.list", headers=HEADERS, params=params)
        data = res.json()
        check_response(data)

        users = data.get("members", [])
        for user in users:
            user_map[user["id"]] = user.get("real_name", user.get("name"))
        total_users += len(users)

        print(f"  ➕ Fetched {len(users)} users (total: {total_users})")

        cursor = data.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    if not user_map:
        print("⚠️ No users fetched. Check your token scopes (`users:read`).")
    return user_map

def fetch_channel_messages(channel_id, oldest):
    print(f"💬 Fetching messages from channel {channel_id} since {datetime.datetime.fromtimestamp(int(oldest)).date()}...")
    messages = []
    cursor = None
    total = 0

    while True:
        params = {
            'channel': channel_id,
            'oldest': oldest,
            'limit': 200
        }
        if cursor:
            params['cursor'] = cursor

        res = requests.get("https://slack.com/api/conversations.history", headers=HEADERS, params=params)
        data = res.json()
        check_response(data)

        batch = data.get("messages", [])
        total += len(batch)
        print(f"  ➕ Fetched {len(batch)} messages (total: {total})")
        messages.extend(batch)

        cursor = data.get("response_metadata", {}).get("next_cursor")
        if not data.get("has_more"):
            break
        time.sleep(1)  # Respect rate limits

    if not messages:
        print("⚠️ No messages returned. Check channel ID, date range, or bot permissions.")
    return messages

def fetch_thread(channel_id, thread_ts):
    print(f"🔁 Fetching thread replies for ts={thread_ts}...")
    params = {'channel': channel_id, 'ts': thread_ts}
    res = requests.get("https://slack.com/api/conversations.replies", headers=HEADERS, params=params)
    data = res.json()
    check_response(data)

    replies = data.get("messages", [])[1:]
    print(f"  ↪️ {len(replies)} replies")
    return replies

def resolve_user(user_id, user_map):
    return user_map.get(user_id, f"<@{user_id}>")

def structure_messages(messages, user_map):
    structured = []
    print("🧱 Structuring messages...")

    for i, msg in enumerate(messages):
        if msg.get('subtype') == 'channel_join':
            continue

        print(f"🔹 Processing message {i+1}/{len(messages)} | ts={msg['ts']}")
        entry = {
            'user': resolve_user(msg.get('user', ''), user_map),
            'timestamp': datetime.datetime.fromtimestamp(float(msg['ts'])).isoformat(),
            'text': msg.get('text', ''),
            'thread': []
        }

        if 'thread_ts' in msg and msg['ts'] == msg['thread_ts']:
            entry['thread'] = fetch_thread(CHANNEL_ID, msg['thread_ts'])

        structured.append(entry)
    return structured

def main():
    try:
        user_map = fetch_user_map()
        messages = fetch_channel_messages(CHANNEL_ID, OLDEST_TIMESTAMP)
        structured = structure_messages(messages, user_map)

        output_filename = f"slack_export_{CHANNEL_ID}.json"
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(list(reversed(structured)), f, indent=2, ensure_ascii=False)

        print(f"✅ Export complete! {len(structured)} top-level messages saved to {output_filename}")

    except Exception as e:
        print("💥 An error occurred:", str(e))

if __name__ == "__main__":
    main()
