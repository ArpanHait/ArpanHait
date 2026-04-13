import os
import requests
import sys
from datetime import datetime

USERNAME = "ArpanHait"
TOKEN = os.getenv("METRICS_TOKEN")

headers = {
    "Accept": "application/vnd.github.v3+json",
}

# 1. TEST IF THE TOKEN IS ACTUALLY LOADING
if TOKEN:
    headers["Authorization"] = f"token {TOKEN}"
    print("✅ Token successfully loaded from environment.")
else:
    print("❌ WARNING: METRICS_TOKEN is missing or empty! GitHub will block this with a Rate Limit.")

def fetch_paginated_count(url):
    count = 0
    page = 1
    while True:
        sep = "&" if "?" in url else "?"
        response = requests.get(f"{url}{sep}per_page=100&page={page}", headers=headers)
        
        # 2. LOUD ERROR REPORTING
        if response.status_code != 200:
            print(f"❌ API ERROR on {url}: Status {response.status_code}")
            print(f"Details: {response.text}")
            break
            
        data = response.json()
        if not data:
            break
        count += len(data)
        if len(data) < 100:
            break
        page += 1
    return count

def main():
    try:
        print("Fetching GitHub Stats...")
        
        # 1. Fetch Events
        commits = 0
        pr_reviews = 0
        pr_opened = 0
        issues = 0
        comments = 0
        
        # Dictionary to track commits by date for streaks and averages
        commits_per_day = {}

        for page in range(1, 4):
            events_url = f"https://api.github.com/users/{USERNAME}/events?per_page=100&page={page}"
            events_response = requests.get(events_url, headers=headers)
            
            if events_response.status_code != 200:
                print(f"❌ API ERROR on Events: Status {events_response.status_code}")
                print(f"Details: {events_response.text}")
                break
                
            events = events_response.json()
            if not events:
                break
                
            for event in events:
                event_type = event.get("type")
                payload = event.get("payload", {})
                
                if event_type == "PushEvent":
                    commit_count = len(payload.get("commits", []))
                    commits += commit_count
                    
                    # Track dates for streaks and averages
                    date_str = event.get("created_at", "")[:10]
                    if date_str:
                        commits_per_day[date_str] = commits_per_day.get(date_str, 0) + commit_count
                        
                elif event_type == "PullRequestReviewEvent":
                    pr_reviews += 1
                elif event_type == "PullRequestEvent" and payload.get("action") == "opened":
                    pr_opened += 1
                elif event_type == "IssuesEvent" and payload.get("action") == "opened":
                    issues += 1
                elif event_type in ["IssueCommentEvent", "CommitCommentEvent", "PullRequestReviewCommentEvent"] and payload.get("action") == "created":
                    comments += 1

        # Calculate Streak, Highest, and Average based on recent events
        best_streak = 0
        highest_day = 0
        average_day = "0.00"

        if commits_per_day:
            highest_day = max(commits_per_day.values())
            avg = sum(commits_per_day.values()) / len(commits_per_day)
            average_day = f"{avg:.2f}"
            
            sorted_dates = sorted(commits_per_day.keys())
            current_streak = 1
            max_streak = 1
            for i in range(1, len(sorted_dates)):
                d1 = datetime.strptime(sorted_dates[i-1], "%Y-%m-%d")
                d2 = datetime.strptime(sorted_dates[i], "%Y-%m-%d")
                if (d2 - d1).days == 1:
                    current_streak += 1
                    max_streak = max(max_streak, current_streak)
                else:
                    current_streak = 1
            best_streak = max_streak

        # Add historical offset to commits
        commits += 300
        
        # 2. Fetch User basic info
        print("Fetching basic user info...")
        user_response = requests.get(f"https://api.github.com/users/{USERNAME}", headers=headers)
        if user_response.status_code != 200:
            print(f"❌ API ERROR on User Info: Status {user_response.status_code}")
            print(f"Details: {user_response.text}")
            user_data = {}
        else:
            user_data = user_response.json()
            
        following = user_data.get("following", 0)

        # 3. Fetch Orgs count
        print("Fetching orgs...")
        orgs = fetch_paginated_count(f"https://api.github.com/users/{USERNAME}/orgs")

        # 4. Fetch Starred count (repositories I starred)
        print("Fetching starred repos...")
        starred = fetch_paginated_count(f"https://api.github.com/users/{USERNAME}/starred")

        # 5. Fetch Subscriptions count (repositories I am watching)
        print("Fetching watched repos...")
        watching = fetch_paginated_count(f"https://api.github.com/users/{USERNAME}/subscriptions")

        # 6. Fetch Repos for total stargazers, watchers, and forks
        print("Fetching repo stats...")
        stargazers = 0
        total_watchers = 0
        forks = 0
        forked_by_me = 0
        repo_page = 1
        while True:
            repos_response = requests.get(f"https://api.github.com/users/{USERNAME}/repos?per_page=100&page={repo_page}", headers=headers)
            if repos_response.status_code != 200:
                print(f"❌ API ERROR on Repos: Status {repos_response.status_code}")
                print(f"Details: {repos_response.text}")
                break
                
            repos = repos_response.json()
            if not repos:
                break
            
            for repo in repos:
                stargazers += repo.get("stargazers_count", 0)
                total_watchers += repo.get("watchers_count", 0)
                forks += repo.get("forks_count", 0)
                if repo.get("fork") == True:
                    forked_by_me += 1
                
            if len(repos) < 100:
                break
            repo_page += 1

        # Read progress_template.svg
        template_filename = "progress_template.svg"
        output_filename = "progress.svg"
        if not os.path.exists(template_filename):
            print(f"❌ Error: {template_filename} does not exist in the current directory.")
            sys.exit(1)

        with open(template_filename, "r", encoding="utf-8") as f:
            svg_content = f.read()

        # Replace placeholders
        replacements = {
            "{{COMMITS}}": str(commits),
            "{{PR_REVIEWS}}": str(pr_reviews),
            "{{PR_OPENED}}": str(pr_opened),
            "{{ISSUES}}": str(issues),
            "{{COMMENTS}}": str(comments),
            "{{FOLLOWING}}": str(following),
            "{{ORGS}}": str(orgs),
            "{{STARRED}}": str(starred),
            "{{WATCHING}}": str(watching),
            "{{STARGAZERS}}": str(stargazers),
            "{{TOTAL_WATCHERS}}": str(total_watchers),
            "{{FORKS}}": str(forks),
            "{{FORKED_BY_ME}}": str(forked_by_me),
            "{{BEST_STREAK}}": str(best_streak),
            "{{HIGHEST_DAY}}": str(highest_day),
            "{{AVERAGE_DAY}}": str(average_day),
        }

        for placeholder, value in replacements.items():
            svg_content = svg_content.replace(placeholder, value)

        # Save the updated svg
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(svg_content)
            
        print(f"✅ Successfully updated {output_filename} with new stats.")
        print("Gathered Data:", replacements)

    except Exception as e:
        print(f"❌ An error occurred: {e}")
        sys.exit(1) # Force GitHub Action to turn Red if it crashes

if __name__ == "__main__":
    main()