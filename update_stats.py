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

# --- GRAPHQL FUNCTION FOR HEATMAP CONTRIBUTIONS ---
def fetch_language_stats():
    query = """
    query($username: String!) {
      user(login: $username) {
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
          nodes {
            languages(first: 10) {
              edges {
                size
                node {
                  name
                }
              }
            }
          }
        }
      }
    }
    """
    variables = {"username": USERNAME}
    
    graphql_headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}
    
    try:
        response = requests.post(
            "https://api.github.com/graphql",
            json={"query": query, "variables": variables},
            headers=graphql_headers
        )
        if response.status_code == 200:
            data = response.json()
            repos = data.get('data', {}).get('user', {}).get('repositories', {}).get('nodes', [])
            
            target_langs = {'Python', 'JavaScript', 'TypeScript', 'Java', 'HTML', 'CSS', 'SQL'}
            lang_bytes = {lang: 0 for lang in target_langs}
            
            for repo in repos:
                repo_langs = repo.get('languages') or {}
                lang_edges = repo_langs.get('edges') or []
                for edge in lang_edges:
                    node = edge.get('node') or {}
                    name = node.get('name')
                    size = edge.get('size', 0)
                    if name in target_langs:
                        lang_bytes[name] += size
                        
            return lang_bytes
        else:
            print(f"❌ GraphQL Language API ERROR: Status {response.status_code}")
            print(f"Details: {response.text}")
    except Exception as e:
        print(f"GraphQL Language Error: {e}")
    
    return {lang: 0 for lang in ['Python', 'JavaScript', 'TypeScript', 'Java', 'HTML', 'CSS', 'SQL']}

def fetch_graphql_contributions():
    query = """
    query($username: String!) {
      user(login: $username) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
                date
              }
            }
          }
        }
      }
    }
    """
    variables = {"username": USERNAME}
    
    # GraphQL specifically requires "Bearer" instead of "token" for authentication
    graphql_headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}
    
    try:
        response = requests.post(
            "https://api.github.com/graphql",
            json={"query": query, "variables": variables},
            headers=graphql_headers
        )
        if response.status_code == 200:
            data = response.json()
            calendar = data['data']['user']['contributionsCollection']['contributionCalendar']
            total_contributions = calendar['totalContributions']
            
            # Active days logic
            current_ym = datetime.now().strftime("%Y-%m")
            active_days = 0
            for week in calendar.get('weeks', []):
                for day in week.get('contributionDays', []):
                    if day.get('date', '').startswith(current_ym) and day.get('contributionCount', 0) > 0:
                        active_days += 1
                        
            return total_contributions, active_days
        else:
            print(f"❌ GraphQL API ERROR: Status {response.status_code}")
            print(f"Details: {response.text}")
    except Exception as e:
        print(f"GraphQL Error: {e}")
    return 0, 0

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

        if commits_per_day:
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

        # --- APPLY GRAPHQL TOTAL TO COMMITS ---
        print("Fetching Heatmap Contributions (GraphQL)...")
        heatmap_contributions, active_days = fetch_graphql_contributions()
        
        # Overwrite the old event-based commits with the real heatmap data + your 300 offset
        commits = heatmap_contributions + 300
        
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

        # 6. Fetch Repos for total stargazers, watchers, forks, and total repos
        print("Fetching repo stats...")
        stargazers = 0
        total_watchers = 0
        forks = 0
        forked_by_me = 0
        total_repos = 0  # --- NEW: Variable to hold total repository count ---
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
            
            # --- NEW: Add the number of repos on this page to the total ---
            total_repos += len(repos)
            
            for repo in repos:
                stargazers += repo.get("stargazers_count", 0)
                total_watchers += repo.get("watchers_count", 0)
                forks += repo.get("forks_count", 0)
                if repo.get("fork") == True:
                    forked_by_me += 1
                
            if len(repos) < 100:
                break
            repo_page += 1

        # 7. Fetch Language Stats
        print("Fetching language stats...")
        lang_bytes = fetch_language_stats()
        
        total_lang_bytes = sum(lang_bytes.values())
        if total_lang_bytes == 0:
            total_lang_bytes = 1 # Prevent division by zero
            
        py_width = round((lang_bytes.get('Python', 0) / total_lang_bytes) * 460, 1)
        js_width = round((lang_bytes.get('JavaScript', 0) / total_lang_bytes) * 460, 1)
        ts_width = round((lang_bytes.get('TypeScript', 0) / total_lang_bytes) * 460, 1)
        java_width = round((lang_bytes.get('Java', 0) / total_lang_bytes) * 460, 1)
        html_width = round((lang_bytes.get('HTML', 0) / total_lang_bytes) * 460, 1)
        css_width = round((lang_bytes.get('CSS', 0) / total_lang_bytes) * 460, 1)
        sql_width = round((lang_bytes.get('SQL', 0) / total_lang_bytes) * 460, 1)
        
        js_x = py_width
        ts_x = round(js_x + js_width, 1)
        java_x = round(ts_x + ts_width, 1)
        html_x = round(java_x + java_width, 1)
        css_x = round(html_x + html_width, 1)
        sql_x = round(css_x + css_width, 1)

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
            "{{ACTIVE_DAYS}}": str(active_days),
            "{{TOTAL_REPOS}}": str(total_repos),  # --- NEW: Added the placeholder replacement ---
            "{{PY_WIDTH}}": str(py_width),
            "{{JS_X}}": str(js_x),
            "{{JS_WIDTH}}": str(js_width),
            "{{TS_X}}": str(ts_x),
            "{{TS_WIDTH}}": str(ts_width),
            "{{JAVA_X}}": str(java_x),
            "{{JAVA_WIDTH}}": str(java_width),
            "{{HTML_X}}": str(html_x),
            "{{HTML_WIDTH}}": str(html_width),
            "{{CSS_X}}": str(css_x),
            "{{CSS_WIDTH}}": str(css_width),
            "{{SQL_X}}": str(sql_x),
            "{{SQL_WIDTH}}": str(sql_width),
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