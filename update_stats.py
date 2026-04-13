import os
import requests
import sys

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
                    commits += len(payload.get("commits", []))
                elif event_type == "PullRequestReviewEvent":
                    pr_reviews += 1
                elif event_type == "PullRequestEvent" and payload.get("action") == "opened":
                    pr_opened += 1
                elif event_type == "IssuesEvent" and payload.get("action") == "opened":
                    issues += 1
                elif event_type in ["IssueCommentEvent", "CommitCommentEvent", "PullRequestReviewCommentEvent"] and payload.get("action") == "created":
                    comments += 1
        
        # Add historical offset to commits (Restored to 800 based on your original SVG)
        commits += 800

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

        # 6. Fetch Repos for total stargazers and watchers receiving
        print("Fetching repo stats...")
        stargazers = 0
        total_watchers = 0
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
                
            if len(repos) < 100:
                break
            repo_page += 1

        # Read progress.svg
        svg_filename = "progress.svg"
        if not os.path.exists(svg_filename):
            print(f"❌ Error: {svg_filename} does not exist in the current directory.")
            sys.exit(1)

        with open(svg_filename, "r", encoding="utf-8") as f:
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
        }

        for placeholder, value in replacements.items():
            svg_content = svg_content.replace(placeholder, value)

        # Save the updated svg
        with open(svg_filename, "w", encoding="utf-8") as f:
            f.write(svg_content)
            
        print(f"✅ Successfully updated {svg_filename} with new stats.")
        print("Gathered Data:", replacements)

    except Exception as e:
        print(f"❌ An error occurred: {e}")
        sys.exit(1) # Force GitHub Action to turn Red if it crashes

if __name__ == "__main__":
    main()
