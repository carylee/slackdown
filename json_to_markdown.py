import json
import datetime
import sys
import re
from pathlib import Path

MAX_MSG_LENGTH = 2000
JIRA_COMMENT_RE = re.compile(r"@?.+ commented on OH-\d+ .+")


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

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("input_file", help="Path to the Slack export JSON file")
    parser.add_argument("--filter-jira-comments", action="store_true", help="Filter out Jira Cloud comment notifications")
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists() or not input_path.suffix == ".json":
        print("❌ Please provide a valid .json file path")
        sys.exit(1)

    output_path = input_path.with_suffix(".md")

    try:
        with input_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Failed to load JSON: {e}")
        sys.exit(1)

    markdown = json_to_markdown(data, filter_jira_comments=args.filter_jira_comments)

    with output_path.open("w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"✅ Markdown transcript saved to {output_path}")

if __name__ == "__main__":
    main()
