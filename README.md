# slackdown

A simple command-line tool to fetch Slack channel history and export it to a Markdown file. Useful for archiving, searching, or documenting conversations offline.

## Features

*   Fetches messages from a specified public Slack channel.
*   Includes replies within threads.
*   Resolves user IDs to real names using the Slack API.
*   Caches user data locally (`~/.slackdown/users.json`) to speed up subsequent runs and reduce API calls.
*   Handles Slack API rate limits gracefully with exponential backoff.
*   Exports conversations to a structured Markdown file.
*   Configurable lookback period (number of days).
*   Optionally saves the intermediate JSON data.
*   Optionally filters out common Jira Cloud comment notifications.

## Prerequisites

*   **Python 3.13+**
*   **Slack Bot Token:** You need a Slack Bot token from an app you create in your workspace.
    *   Go to [api.slack.com/apps](https://api.slack.com/apps) and create a new app or use an existing one.
    *   Under "OAuth & Permissions", add the following Bot Token Scopes:
        *   `channels:history` (to read messages)
        *   `channels:read` (to get channel info like name)
        *   `users:read` (to resolve user IDs to names)
        *   *(Note: For private channels or DMs, you might need additional scopes like `groups:history`, `mpim:history`, `im:history`)*
    *   Install the app to your workspace.
    *   Copy the "Bot User OAuth Token" (it usually starts with `xoxb-`).

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/carylee/slackdown.git
    cd slackdown
    ```
2.  **Run with `uv`:**
    ```bash
    uv run slackdown -h
    ```
    *(This assumes you're using [uv](https://docs.astral.sh/uv/) to manage python projects).*

## Configuration

1.  Create a file named `.env` in the project's root directory.
2.  Add your Slack Bot Token to the `.env` file:
    ```dotenv
    SLACK_TOKEN=xoxb-your-slack-bot-token-here
    ```

## Usage

Run the script from your terminal, providing the Channel ID you want to export.

**Basic Usage (exports last 2 years to `slack_export_<channel_name>.md`):**

```bash
python slackdown.py <channel_id>
```

*   **How to find the Channel ID:** Open Slack in your browser, navigate to the channel, and look at the URL. It will be something like `https://app.slack.com/client/T0123456/CABCDEF12`. The Channel ID is `CABCDEF12`.

**Options:**

*   Specify the number of days to look back:
    ```bash
    python slackdown.py CABCDEF12 --days 90
    ```
*   Specify the output Markdown file name:
    ```bash
    python slackdown.py CABCDEF12 --output my_channel_export.md
    ```
*   Filter out Jira Cloud comment notifications:
    ```bash
    python slackdown.py CABCDEF12 --filter-jira-comments
    ```
*   Save the intermediate JSON data as well:
    ```bash
    python slackdown.py CABCDEF12 --json export_data.json
    ```
*   Force refresh the local user cache (fetch all users again from API):
    ```bash
    python slackdown.py CABCDEF12 --refresh-users
    ```

## Output Format

The script generates a Markdown file with messages formatted like this:

```markdown
## Slack Channel Transcript

**User Name** (YYYY-MM-DD HH:MM):
> Original message text...

  **Reply User Name** (YYYY-MM-DD HH:MM):
  > Reply message text...

  **Another Reply User Name** (YYYY-MM-DD HH:MM):
  > Another reply message text...

---

**Another User Name** (YYYY-MM-DD HH:MM):
> Another top-level message...

---
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
```
