import requests
import xml.etree.ElementTree as ET
import time
import json
import os
import subprocess
from datetime import datetime

# ==========================================
# CONFIGURATION
# ==========================================
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"
TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID_HERE"

CHECK_INTERVAL_MINUTES = 30  # Auto trigger interval (in minutes)
DB_FILE = "jobs_database.json"

KEYWORDS = [
    "flutter", "dart", "machine learning", "deep learning", "computer vision", 
    "vlsi", "risc-v", "fpga", "python developer",
    "research", "funding", "grant", "fellowship", "scholarship"
]

EXCLUDE_WORDS = [
    "senior", "staff", "principal", "lead", "manager", "director"
]

def load_db():
    """Loads the database of already found opportunities."""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_db(db):
    """Saves the database to keep track of active jobs."""
    with open(DB_FILE, 'w') as f:
        json.dump(db, f, indent=4)

def push_to_github():
    """Automatically pushes the updated database to GitHub so the live dashboard stays up to date."""
    print("Pushing updated database to GitHub Pages...")
    try:
        # Add only the database file
        subprocess.run(["git", "add", DB_FILE], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Commit the changes (this will return non-zero if nothing to commit, so check=False)
        result = subprocess.run(["git", "commit", "-m", "Auto-update: New opportunities found/closed"], 
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # If commit was successful, push it
        if result.returncode == 0:
            subprocess.run(["git", "push", "origin", "main"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("✅ Successfully updated live dashboard on GitHub!")
        else:
            print("No changes to push to GitHub.")
    except Exception as e:
        print(f"⚠️ Failed to push to GitHub: {e}")

def send_telegram_alert(message):
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("[Telegram Alert Skipped] Token not set.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload)
    except Exception:
        pass

def is_good_fit(title):
    title_lower = title.lower()
    if any(ex in title_lower for ex in EXCLUDE_WORDS):
        return False
    return True

def fetch_rss_feed(url, source_name):
    matched_jobs = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            for item in root.findall('.//item')[:20]:
                title = item.find('title').text or ""
                desc = item.find('description').text or ""
                link = item.find('link').text or ""
                if not is_good_fit(title):
                    continue
                if any(kw in title.lower() or kw in desc.lower() for kw in KEYWORDS):
                    matched_jobs.append({"title": title.strip(), "company": "Client", "link": link, "source": source_name})
    except Exception:
        pass
    return matched_jobs

def fetch_remotive_jobs():
    matched_jobs = []
    search_terms = ["flutter", "machine learning", "python"]
    try:
        for term in search_terms:
            response = requests.get(f"https://remotive.com/api/remote-jobs?search={term}", timeout=10)
            if response.status_code == 200:
                for job in response.json().get('jobs', []):
                    title = job['title']
                    if not is_good_fit(title):
                        continue
                    matched_jobs.append({"title": title, "company": job['company_name'], "link": job['url'], "source": "Remotive"})
    except Exception:
        pass
    return matched_jobs

def check_if_closed(url):
    """Visits the job URL to see if it gives a 404 or says 'closed'."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        
        # If the page doesn't exist anymore, the job is gone
        if response.status_code == 404:
            return True
            
        # Check the HTML text for common phrases
        text = response.text.lower()
        closed_phrases = [
            "this job is no longer available",
            "this position has been closed",
            "this posting is closed",
            "no longer accepting applications"
        ]
        if any(phrase in text for phrase in closed_phrases):
            return True
            
    except Exception:
        pass
    return False

def check_existing_jobs(db):
    """Checks previously found jobs to see if they are closed."""
    print("Checking if any older opportunities have closed...")
    closed_jobs = []
    
    for link, job_data in list(db.items()):
        # Check if closed
        if check_if_closed(link):
            closed_jobs.append(job_data)
            del db[link] # Remove from active list
            
            # Alert user that this opportunity is gone
            msg = f"❌ <b>Opportunity Closed:</b> {job_data['title']}\nThis job is no longer available!"
            print(msg.replace("<b>", "").replace("</b>", ""))
            send_telegram_alert(msg)
            time.sleep(1)
            
    if closed_jobs:
        save_db(db)
        push_to_github()

def main():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Auto-Trigger Started. It will check for jobs every {CHECK_INTERVAL_MINUTES} minutes.")
    
    while True:
        print(f"\n--- Running Job Search: {datetime.now().strftime('%H:%M:%S')} ---")
        db = load_db()
        
        # 1. First, check if any old jobs have closed
        if db:
            check_existing_jobs(db)
            
        # 2. Search for new jobs
        print("Looking for new opportunities...")
        all_jobs = []
        
        # Upwork RSS
        upwork_urls = [
            ("https://www.upwork.com/ab/feed/jobs/rss?q=flutter", "Upwork"),
            ("https://www.upwork.com/ab/feed/jobs/rss?q=machine+learning", "Upwork"),
            ("https://www.upwork.com/ab/feed/jobs/rss?q=research", "Upwork")
        ]
        for url, name in upwork_urls:
            all_jobs.extend(fetch_rss_feed(url, name))
            
        # Reddit RSS
        reddit_urls = [
            ("https://www.reddit.com/r/forhire/new/.rss", "Reddit"),
            ("https://www.reddit.com/r/slavelabour/new/.rss", "Reddit"),
            ("https://www.reddit.com/r/MachineLearning/search.rss?q=hiring&restrict_sr=on&sort=new&t=all", "Reddit")
        ]
        for url, name in reddit_urls:
            all_jobs.extend(fetch_rss_feed(url, name))
            
        # Remotive API
        all_jobs.extend(fetch_remotive_jobs())
        
        # 3. Process the new jobs
        new_jobs_found = 0
        for job in all_jobs:
            link = job['link']
            # If we haven't seen this job before
            if link not in db:
                db[link] = job
                new_jobs_found += 1
                
                msg = (
                    f"🚀 <b>NEW OPPORTUNITY</b>\n"
                    f"💼 <b>{job['title']}</b>\n"
                    f"🏢 <b>Client/Company:</b> {job['company']}\n"
                    f"🌐 <b>Source:</b> {job['source']}\n"
                    f"🔗 <b>Link:</b> {job['link']}\n"
                )
                print(msg.replace("<b>", "").replace("</b>", ""))
                send_telegram_alert(msg)
                time.sleep(1) # Prevent spamming Telegram API
                
        
        if new_jobs_found == 0:
            print("No new jobs found this round.")
        else:
            save_db(db)
            print(f"Found and saved {new_jobs_found} new jobs!")
            push_to_github() # Update live dashboard
            
        # 4. Wait for the next interval (Auto Trigger)
        print(f"Waiting for {CHECK_INTERVAL_MINUTES} minutes until the next scan...")
        time.sleep(CHECK_INTERVAL_MINUTES * 60)

if __name__ == "__main__":
    main()
