import subprocess
import sys
from pathlib import Path

def fetch_ticket(ticket_id):
    try:
        result = subprocess.run(
            ["jira", "issue", "view", "--comments", "20", ticket_id],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"[Error fetching {ticket_id}]\n{e.stderr}"

def main():
    if len(sys.argv) != 2:
        print("Usage: python fetch_jira_tickets.py tickets.txt")
        sys.exit(1)

    ticket_file = Path(sys.argv[1])
    if not ticket_file.exists():
        print(f"File not found: {ticket_file}")
        sys.exit(1)

    with ticket_file.open("r", encoding="utf-8") as f:
        for line in f:
            ticket_id = line.strip()
            if not ticket_id:
                continue

            print("----")
            print(ticket_id)
            print(fetch_ticket(ticket_id))

if __name__ == "__main__":
    main()

