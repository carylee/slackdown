import requests
import time
import json
import datetime
import argparse
from dotenv import load_dotenv
import os
import sys
import re
from pathlib import Path

# Load .env config
load_dotenv()
SLACK_TOKEN = os.getenv('SLACK_TOKEN')

if not SLACK_TOKEN:
    raise ValueError("SLACK_TOKEN must be set in your .env file.")

HEADERS = {'Authorization': f'Bearer {SLACK_TOKEN}'}

# Path for storing user data
USER_DATA_PATH = Path(os.path.expanduser("~/.slackdown/users.json"))

# Constants for JSON to Markdown conversion
MAX_MSG_LENGTH = 2000
JIRA_COMMENT_RE = re.compile(r"@?.+ commented on OH-\d+ .+")

def check_response(resp):
    if not resp.get("ok"):
        error = resp.get("error")
        if error == "ratelimited":
            retry_after = int(resp.get("retry_after", 1))
            print(f"⏰ Rate limited by Slack API. Waiting {retry_after} seconds...")
            time.sleep(retry_after)
            return False
        print("❌ Slack API error:", error)
        raise Exception("Slack API error: " + str(error))
    return True

def save_users(user_map, metadata=None):
    """Save user data to local file system."""
    if metadata is None:
        metadata = {}
    
    # Ensure directory exists
    USER_DATA_PATH.parent.mkdir(exist_ok=True, parents=True)
    
    data = {
        "users": user_map,
        "timestamp": datetime.datetime.now().isoformat(),
        "metadata": metadata
    }
    
    with open(USER_DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"💾 User data saved locally ({len(user_map)} users)")

def load_users():
    """Load user data from local file if available."""
    try:
        if USER_DATA_PATH.exists():
            with open(USER_DATA_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"📂 Loaded {len(data['users'])} users from local cache")
                print(f"   Cache timestamp: {data['timestamp']}")
                return data['users'], data.get('metadata', {})
    except Exception as e:
        print(f"⚠️ Failed to load local user data: {e}")
    
    return None, None

def fetch_user_map(force_refresh=False):
    """Get users, using local cache if available unless force_refresh is True."""
    if not force_refresh:
        user_map, metadata = load_users()
        if user_map:
            print("ℹ️ Using cached user data. Use --refresh-users to fetch fresh data.")
            return user_map
    
    print("🔍 Fetching users from Slack API...")
    user_map = {}
    cursor = None
    total_users = 0
    metadata = {}

    while True:
        params = {'limit': 200}
        if cursor:
            params['cursor'] = cursor

        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            res = requests.get("https://slack.com/api/users.list", headers=HEADERS, params=params)
            data = res.json()
            
            if check_response(data):
                break
            
            retry_count += 1
            if retry_count >= max_retries:
                print(f"❌ Failed after {max_retries} attempts to fetch users")
                raise Exception("Maximum retries exceeded while fetching users")

        users = data.get("members", [])
        for user in users:
            user_map[user["id"]] = user.get("real_name", user.get("name"))
        total_users += len(users)

        print(f"  ➕ Fetched {len(users)} users (total: {total_users})")

        cursor = data.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
        
        # Respect rate limits - add small delay between pagination requests
        time.sleep(0.5)

    if not user_map:
        print("⚠️ No users fetched. Check your token scopes (`users:read`).")
    else:
        # Save users to local cache
        save_users(user_map, {"total_users": total_users})
        
    return user_map

def get_channel_name(channel_id):
    print(f"🔍 Getting channel info for {channel_id}...")
    params = {'channel': channel_id}
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        res = requests.get("https://slack.com/api/conversations.info", headers=HEADERS, params=params)
        data = res.json()
        
        if check_response(data):
            channel_name = data.get('channel', {}).get('name', channel_id)
            print(f"📚 Channel name: {channel_name}")
            return channel_name
        
        retry_count += 1
        if retry_count >= max_retries:
            print(f"❌ Failed after {max_retries} attempts to get channel info")
            return channel_id

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

        max_retries = 5
        retry_count = 0
        success = False
        
        while retry_count < max_retries and not success:
            res = requests.get("https://slack.com/api/conversations.history", headers=HEADERS, params=params)
            data = res.json()
            
            if check_response(data):
                success = True
                batch = data.get("messages", [])
                total += len(batch)
                print(f"  ➕ Fetched {len(batch)} messages (total: {total})")
                messages.extend(batch)
                
                cursor = data.get("response_metadata", {}).get("next_cursor")
                if not data.get("has_more"):
                    break
            else:
                retry_count += 1
                if retry_count >= max_retries:
                    print(f"❌ Failed after {max_retries} attempts to fetch messages")
                    break
        
        if not success:
            break
            
        # Always add a delay between requests to prevent rate limiting
        time.sleep(1.2)  # Slightly longer delay to be safer with rate limits

    if not messages:
        print("⚠️ No messages returned. Check channel ID, date range, or bot permissions.")
    return messages

def fetch_thread(channel_id, thread_ts):
    print(f"🔁 Fetching thread replies for ts={thread_ts}...")
    params = {'channel': channel_id, 'ts': thread_ts}
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        res = requests.get("https://slack.com/api/conversations.replies", headers=HEADERS, params=params)
        data = res.json()
        
        if check_response(data):
            replies = data.get("messages", [])[1:]
            print(f"  ↪️ {len(replies)} replies")
            return replies
        
        retry_count += 1
        if retry_count >= max_retries:
            print(f"⚠️ Failed to fetch thread after {max_retries} attempts, skipping thread")
            return []
        
        # Add delay between retries
        time.sleep(1)

def resolve_user(user_id, user_map):
    return user_map.get(user_id, f"<@{user_id}>")

def structure_messages(messages, user_map, channel_id):
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
            entry['thread'] = fetch_thread(channel_id, msg['thread_ts'])

        structured.append(entry)
    return structured

# Functions from json_to_markdown.py

def format_timestamp(ts):
    if ts is None:
        return "unknown time"
    try:
        if isinstance(ts, float) or (isinstance(ts, str) and ts.replace(".", "", 1).isdigit()):
            return datetime.datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
        return datetime.datetime.fromisoformat(str(ts)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ts)

def escape_md(text):
    return text.replace('*', '\\*').replace('_', '\\_').replace('`', '\\`')

def truncate(text, max_len):
    return text if len(text) <= max_len else text[:max_len] + "..."


def is_jira_comment_message(msg):
    return (
        msg.get("user") == "Jira Cloud"
        and JIRA_COMMENT_RE.fullmatch(msg.get("text", "").strip())
    )

def json_to_markdown(data, filter_jira_comments=False):
    lines = ["## Slack Channel Transcript\n"]

    for entry in data:
        if filter_jira_comments and is_jira_comment_message(entry):
            continue

        user = entry.get("user", "Unknown")
        time_str = format_timestamp(entry.get("timestamp"))
        text = escape_md(entry.get("text", "").strip())
        text = truncate(text, MAX_MSG_LENGTH)

        lines.append(f"**{user}** ({time_str}):\n> {text}\n")

        for reply in entry.get("thread", []):
            reply_user = reply.get("user", "Unknown")
            reply_time = format_timestamp(reply.get("timestamp"))
            reply_text = escape_md(reply.get("text", "").strip())
            reply_text = truncate(reply_text, MAX_MSG_LENGTH)

            lines.append(f"  **{reply_user}** ({reply_time}):\n  > {reply_text}\n")

        lines.append("---\n")

    return "\n".join(lines)

def calculate_oldest_timestamp(days):
    return str(int(time.time() - days * 24 * 60 * 60))

def main():
    parser = argparse.ArgumentParser(description="Export Slack channel history to Markdown")
    parser.add_argument("channel_id", help="Slack channel ID")
    parser.add_argument("--days", type=int, default=365*2, help="Number of days to look back (default: 730 days/2 years)")
    parser.add_argument("--output", "-o", help="Output file path (default: based on channel name)")
    parser.add_argument("--filter-jira-comments", action="store_true", help="Filter out Jira Cloud comment notifications")
    parser.add_argument("--json", help="Also save the intermediate JSON representation to this path")
    parser.add_argument("--refresh-users", action="store_true", help="Force refresh user data instead of using cached data")
    args = parser.parse_args()
    
    try:
        channel_id = args.channel_id
        oldest_timestamp = calculate_oldest_timestamp(args.days)
        
        # Get channel name for the default output filename
        channel_name = get_channel_name(channel_id)
        
        # Set output filename
        if args.output:
            output_filename = args.output
        else:
            output_filename = f"slack_export_{channel_name}.md"
        
        # Get user map (from cache or API)
        user_map = fetch_user_map(force_refresh=args.refresh_users)
        
        # Fetch and structure messages
        messages = fetch_channel_messages(channel_id, oldest_timestamp)
        structured = structure_messages(messages, user_map, channel_id)
        
        # Save JSON if requested
        if args.json:
            json_filename = args.json
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(list(reversed(structured)), f, indent=2, ensure_ascii=False)
            print(f"💾 JSON data saved to {json_filename}")
            
        # Convert to markdown and save
        markdown = json_to_markdown(list(reversed(structured)), filter_jira_comments=args.filter_jira_comments)
        
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(markdown)

        print(f"✅ Export complete! {len(structured)} top-level messages saved to {output_filename}")

    except Exception as e:
        print("💥 An error occurred:", str(e))

if __name__ == "__main__":
    main()