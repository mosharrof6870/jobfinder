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
    "research", "funding", "grant", "fellowship", "scholarship",
    "বৃত্তি", "ফেলোশিপ", "অনুদান", "গবেষণা", "আবেদন", "প্রশিক্ষণ"
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
            for item in root.findall('.//item')[:50]:
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

def fetch_bd_govt_jobs():
    print("Fetching from BD Government (ICT/BCC)...")
    matched_jobs = []
    
    from bs4 import BeautifulSoup
    import urllib3
    urllib3.disable_warnings()

    urls = [
        ("https://ictd.gov.bd/site/view/notices", "ICT Division BD"),
        ("http://www.bcc.gov.bd/site/view/notices", "BCC BD")
    ]
    
    for url, source_name in urls:
        try:
            response = requests.get(url, verify=False, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                table = soup.find("table")
                if table:
                    rows = table.find_all("tr")[1:15]
                    for r in rows:
                        cols = r.find_all("td")
                        if len(cols) >= 3:
                            title = cols[2].text.strip()
                            link_tag = cols[2].find('a')
                            link = link_tag['href'] if link_tag else url
                            
                            # Construct full URL if relative
                            if link.startswith('/'):
                                base = "https://ictd.gov.bd" if "ictd" in url else "http://www.bcc.gov.bd"
                                link = base + link
                                
                            if any(kw in title.lower() for kw in KEYWORDS):
                                matched_jobs.append({"title": title, "company": "Govt of Bangladesh", "link": link, "source": source_name})
        except Exception as e:
            print(f"  [!] Could not fetch {source_name}: {e}")
            
    return matched_jobs

def fetch_professors():
    print("Searching for Professors/Labs (CV/DL/LLM) via EuropePMC...")
    matched_jobs = []
    import re
    
    # Query EuropePMC for latest papers in these fields
    # It indexes many CS papers and includes verified author emails!
    query = '("computer vision" OR "deep learning" OR "llm" OR "vlm" OR "vlsi" OR "machine learning")'
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={query}&format=json&resultType=core&pageSize=50&sort_date:y"
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            for result in data.get("resultList", {}).get("result", []):
                paper_title = result.get("title", "")
                paper_link = f"https://europepmc.org/article/MED/{result.get('pmid', '')}"
                
                for author in result.get("authorList", {}).get("author", []):
                    if "authorAffiliationDetailsList" in author:
                        for aff in author["authorAffiliationDetailsList"]["authorAffiliation"]:
                            aff_str = aff.get("affiliation", "")
                            # Extract email if present
                            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', aff_str)
                            if emails:
                                email = emails[0]
                                # Clean affiliation name
                                uni_name = aff_str.split('.')[0] if '.' in aff_str else "University / Lab"
                                prof_name = f"{author.get('firstName', '')} {author.get('lastName', '')}".strip()
                                
                                # Avoid adding the exact same email twice
                                if not any(j['company'] == f"Email: {email}" for j in matched_jobs):
                                    matched_jobs.append({
                                        "title": f"Prof. {prof_name} ({uni_name[:40]}...)",
                                        "company": f"Email: {email}",
                                        "link": paper_link,
                                        "source": "Professors"
                                    })
                                    
                if len(matched_jobs) >= 20: # Cap at 20 per run so it doesn't flood everything at once
                    break
    except Exception as e:
        print(f"  [!] Could not search Professors API: {e}")
        
    return matched_jobs

def fetch_weworkremotely_jobs():
    print("Fetching from WeWorkRemotely (RSS)...")
    # Using our custom RSS parser since JSON API returns 404
    return fetch_rss_feed("https://weworkremotely.com/remote-jobs.rss", "WeWorkRemotely")

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

def fetch_nsf_awards():
    print("Fetching from NSF Awards (USA)...")
    matched_jobs = []
    url = "https://api.nsf.gov/services/v1/awards.json?keyword=computer+science"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for award in data.get('response', {}).get('award', []):
                title = award.get('title', '')
                pi = award.get('piFirstName', '') + ' ' + award.get('piLastName', '')
                inst = award.get('awardeeName', '')
                funds = award.get('fundsObligatedAmt', 'Unknown')
                link = f"https://www.nsf.gov/awardsearch/showAward?AWD_ID={award.get('id', '')}"
                
                display_title = f"NSF Grant: {title} (PI: {pi})"
                matched_jobs.append({
                    "title": display_title[:100] + ("..." if len(display_title)>100 else ""),
                    "company": f"{inst} (${funds})",
                    "link": link,
                    "source": "NSF USA"
                })
                if len(matched_jobs) >= 20: break
    except Exception as e:
        print(f"  [!] NSF Error: {e}")
    return matched_jobs

def fetch_ukri_projects():
    print("Fetching from UKRI (UK)...")
    matched_jobs = []
    url = "https://gtr.ukri.org/gtr/api/projects?q=computer+science"
    headers = {'Accept': 'application/json'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for proj in data.get('project', []):
                title = proj.get('title', '')
                funds = proj.get('fund', {}).get('valuePounds', 'Unknown')
                link = proj.get('url', url)
                
                matched_jobs.append({
                    "title": title[:100] + ("..." if len(title)>100 else ""),
                    "company": f"UKRI Grant (£{funds})",
                    "link": link,
                    "source": "UKRI"
                })
                if len(matched_jobs) >= 20: break
    except Exception as e:
        print(f"  [!] UKRI Error: {e}")
    return matched_jobs

def fetch_openalex_funders():
    print("Fetching from OpenAlex (Global)...")
    matched_jobs = []
    url = "https://api.openalex.org/funders?search=computer"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for funder in data.get('results', []):
                title = funder.get('display_name', '')
                desc = funder.get('description', '') or ''
                link = funder.get('homepage_url') or funder.get('id', url)
                country = funder.get('country_code', 'Global')
                
                matched_jobs.append({
                    "title": f"Funder: {title}",
                    "company": f"{country} - {desc[:50]}...",
                    "link": link,
                    "source": "OpenAlex"
                })
                if len(matched_jobs) >= 20: break
    except Exception as e:
        print(f"  [!] OpenAlex Error: {e}")
    return matched_jobs

def fetch_openaire_projects():
    print("Fetching from OpenAIRE (Europe)...")
    matched_jobs = []
    url = "https://api.openaire.eu/search/projects?keywords=computer%20science&format=json&size=20"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            results = data.get('response', {}).get('results', {}).get('result', [])
            for res in results:
                metadata = res.get('metadata', {}).get('oaf:entity', {}).get('oaf:project', {})
                title = metadata.get('title', '')
                if isinstance(title, dict):
                    title = title.get('$', '')
                link = metadata.get('websiteurl', '')
                if isinstance(link, dict):
                    link = link.get('$', '')
                if not link:
                    link = "https://explore.openaire.eu/"
                
                funder = metadata.get('fundingtree', {}).get('funder', {}).get('shortname', 'EU Funder')
                if isinstance(funder, dict):
                    funder = funder.get('$', 'EU Funder')
                    
                if title:
                    matched_jobs.append({
                        "title": str(title)[:100],
                        "company": str(funder),
                        "link": str(link),
                        "source": "OpenAIRE"
                    })
    except Exception as e:
        print(f"  [!] OpenAIRE Error: {e}")
    return matched_jobs

def fetch_github_repos():
    print("Fetching from GitHub (Scholarship Repos)...")
    matched_jobs = []
    url = "https://api.github.com/search/repositories?q=phd+positions+computer+science&sort=updated"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for repo in data.get('items', []):
                title = repo.get('name', '')
                desc = repo.get('description', '') or 'CS PhD Positions'
                link = repo.get('html_url', '')
                
                matched_jobs.append({
                    "title": f"Repo: {title}",
                    "company": desc[:60] + "...",
                    "link": link,
                    "source": "GitHub"
                })
                if len(matched_jobs) >= 10: break
    except Exception as e:
        print(f"  [!] GitHub Error: {e}")
    return matched_jobs

def fetch_arxiv_papers():
    print("Fetching from ArXiv (Latest CS Papers)...")
    matched_jobs = []
    url = "http://export.arxiv.org/api/query?search_query=cat:cs.AI&sortBy=submittedDate&sortOrder=descending&max_results=20"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            for entry in root.findall('atom:entry', ns):
                title = entry.find('atom:title', ns).text.strip()
                authors = [a.find('atom:name', ns).text for a in entry.findall('atom:author', ns)]
                link = entry.find('atom:id', ns).text
                
                prof_str = authors[-1] if authors else "Unknown" # Usually last author is PI
                matched_jobs.append({
                    "title": f"Paper: {title[:70]}...",
                    "company": f"PI/Author: {prof_str}",
                    "link": link,
                    "source": "ArXiv Papers"
                })
    except Exception as e:
        print(f"  [!] ArXiv Error: {e}")
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
        
        all_jobs.extend(fetch_weworkremotely_jobs())
        all_jobs.extend(fetch_bd_govt_jobs())
        all_jobs.extend(fetch_remotive_jobs())
        all_jobs.extend(fetch_professors())
        
        # New API Integrations
        all_jobs.extend(fetch_nsf_awards())
        all_jobs.extend(fetch_ukri_projects())
        all_jobs.extend(fetch_openalex_funders())
        all_jobs.extend(fetch_openaire_projects())
        all_jobs.extend(fetch_github_repos())
        all_jobs.extend(fetch_arxiv_papers())
        
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
            
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print("Running in GitHub Actions - exiting after one iteration.")
            break
            
        # 4. Wait for the next interval (Auto Trigger)
        print(f"Waiting for {CHECK_INTERVAL_MINUTES} minutes until the next scan...")
        time.sleep(CHECK_INTERVAL_MINUTES * 60)

if __name__ == "__main__":
    main()
