import os
import time
import json
import logging
import subprocess
import concurrent.futures
from datetime import datetime, timedelta
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional

import requests
from requests.exceptions import Timeout, ConnectionError, HTTPError, SSLError, RequestException
from bs4 import BeautifulSoup

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ==========================================
# CONFIGURATION
# ==========================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

CHECK_INTERVAL_MINUTES = 30  # Auto trigger interval (in minutes)
DB_FILE = "jobs_database.json"

KEYWORDS = [
    "flutter", "dart", "machine learning", "deep learning", "computer vision", 
    "vlsi", "risc-v", "fpga", "python developer", "ml", "dl", "classification",
    "research", "funding", "grant", "fellowship", "scholarship",
    "বৃত্তি", "ফেলোশিপ", "অনুদান", "গবেষণা", "আবেদন", "প্রশিক্ষণ"
]

EXCLUDE_WORDS = [
    "senior", "staff", "principal", "lead", "manager", "director"
]

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ==========================================
# UTILITIES & SMART VALIDATION
# ==========================================

def load_db() -> Dict[str, Any]:
    """Loads the database of already found opportunities."""
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON from database file. Initializing empty DB.")
    return {}

def save_db(db: Dict[str, Any]) -> None:
    """Saves the database to keep track of active jobs."""
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=4, ensure_ascii=False)

def push_to_github() -> None:
    """Automatically pushes the updated database to GitHub."""
    logger.info("Pushing updated database to GitHub Pages...")
    try:
        subprocess.run(["git", "add", DB_FILE], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        result = subprocess.run(["git", "commit", "-m", "Auto-update: New opportunities from global APIs"], 
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            subprocess.run(["git", "push", "origin", "main"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info("✅ Successfully updated live dashboard on GitHub!")
        else:
            logger.info("No changes to push to GitHub.")
    except Exception as e:
        logger.error(f"⚠️ Failed to push to GitHub: {e}")

def send_telegram_alert(message: str) -> None:
    """Send alert to Telegram channel."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.info("[Telegram Alert Skipped] Token not set.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        safe_request(url, method="POST", json_data=payload)
    except Exception as e:
        logger.error(f"Telegram alert failed: {e}")

def is_good_fit(title: str) -> bool:
    """Filter out senior/managerial roles."""
    title_lower = title.lower()
    return not any(ex in title_lower for ex in EXCLUDE_WORDS)

def normalize_url(url: str) -> str:
    """Remove tracking parameters for deduplication."""
    try:
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        # Remove common tracking params
        for param in ['utm_source', 'utm_medium', 'utm_campaign', 'ref']:
            query.pop(param, None)
        new_query = urllib.parse.urlencode(query, doseq=True)
        return urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
        )
    except Exception:
        return url

def jaccard_similarity(str1: str, str2: str) -> float:
    """Calculate similarity between two strings."""
    set1 = set(str1.lower().split())
    set2 = set(str2.lower().split())
    if not set1 or not set2:
        return 0.0
    return len(set1.intersection(set2)) / len(set1.union(set2))

def is_duplicate(new_job: Dict[str, Any], db: Dict[str, Any]) -> bool:
    """Check if job already exists using exact URL or similarity."""
    new_url = normalize_url(new_job['link'])
    
    for existing_url, existing_job in db.items():
        if normalize_url(existing_url) == new_url:
            return True
        # Similarity check (if titles and companies are heavily identical)
        title_sim = jaccard_similarity(new_job['title'], existing_job['title'])
        comp_sim = jaccard_similarity(new_job['company'], existing_job['company'])
        if title_sim > 0.85 and comp_sim > 0.85:
            return True
    return False

# ==========================================
# API LAYER WRAPPER
# ==========================================

def safe_request(url: str, method: str = "GET", headers: Optional[Dict] = None, 
                 json_data: Optional[Dict] = None, timeout: int = 10, max_retries: int = 3,
                 expected_format: str = "text") -> requests.Response:
    """Reusable API wrapper with retries and structured error handling."""
    if headers is None:
        headers = {'User-Agent': 'Mozilla/5.0 (OpportunityFinder/1.0)'}
        
    for attempt in range(1, max_retries + 1):
        try:
            # Strictly enforce SSL verification
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, timeout=timeout)
            else:
                response = requests.post(url, headers=headers, json=json_data, timeout=timeout)
                
            response.raise_for_status()
            
            # JSON validation if required
            if expected_format == "json":
                response.json() # Check parsing
                
            return response
            
        except SSLError as e:
            logger.error(f"SSLError for {url}: {e}")
            # SSL Errors usually don't resolve with retries, fail fast
            break
        except Timeout as e:
            logger.warning(f"Timeout on attempt {attempt} for {url}: {e}")
        except ConnectionError as e:
            logger.warning(f"Connection error on attempt {attempt} for {url}: {e}")
        except HTTPError as e:
            logger.warning(f"HTTP error {e.response.status_code} on attempt {attempt} for {url}")
            if e.response.status_code in [401, 403, 404]:
                break # Don't retry auth or not-found errors
        except ValueError:
            logger.warning(f"Invalid JSON response on attempt {attempt} for {url}")
        except RequestException as e:
            logger.error(f"Request exception for {url}: {e}")
            break
            
        if attempt < max_retries:
            delay = 2 ** (attempt - 1)  # Exponential backoff: 1s, 2s, 4s
            time.sleep(delay)
            
    raise RequestException(f"Failed to fetch {url} after {max_retries} attempts.")

# ==========================================
# FETCH MODULES
# ==========================================

def fetch_rss_feed(url: str, source_name: str) -> List[Dict[str, Any]]:
    matched_jobs = []
    try:
        response = safe_request(url)
        root = ET.fromstring(response.content)
        for item in root.findall('.//item')[:50]:
            title = item.find('title').text or ""
            desc = item.find('description').text or ""
            link = item.find('link').text or ""
            if not is_good_fit(title):
                continue
            if any(kw in title.lower() or kw in desc.lower() for kw in KEYWORDS):
                matched_jobs.append({"title": title.strip(), "company": "Client", "link": link, "source": source_name})
    except Exception as e:
        logger.error(f"Failed to parse RSS from {source_name}: {e}")
    return matched_jobs

def fetch_weworkremotely_jobs() -> List[Dict[str, Any]]:
    logger.info("Fetching from WeWorkRemotely (RSS)...")
    return fetch_rss_feed("https://weworkremotely.com/remote-jobs.rss", "WeWorkRemotely")

def fetch_bd_govt_jobs() -> List[Dict[str, Any]]:
    logger.info("Fetching from BD Government (ICT/BCC)...")
    matched_jobs = []
    
    urls = [
        ("https://ictd.gov.bd/site/view/notices", "ICT Division BD"),
        ("http://www.bcc.gov.bd/site/view/notices", "BCC BD")
    ]
    
    for url, source_name in urls:
        try:
            response = safe_request(url)
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
                        
                        if link.startswith('/'):
                            base = "https://ictd.gov.bd" if "ictd" in url else "http://www.bcc.gov.bd"
                            link = base + link
                            
                        if any(kw in title.lower() for kw in KEYWORDS):
                            matched_jobs.append({"title": title, "company": "Govt of Bangladesh", "link": link, "source": source_name})
        except RequestException:
            # We already logged SSL and other errors inside safe_request
            pass
        except Exception as e:
            logger.error(f"Could not parse HTML from {source_name}: {e}")
            
    return matched_jobs

def fetch_professors() -> List[Dict[str, Any]]:
    logger.info("Searching for Professors/Labs via EuropePMC...")
    matched_jobs = []
    import re
    
    query = '("computer vision" OR "deep learning" OR "llm" OR "vlm" OR "vlsi" OR "machine learning")'
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={query}&format=json&resultType=core&pageSize=50&sort_date:y"
    
    try:
        response = safe_request(url, expected_format="json", timeout=15)
        data = response.json()
        for result in data.get("resultList", {}).get("result", []):
            paper_link = f"https://europepmc.org/article/MED/{result.get('pmid', '')}"
            for author in result.get("authorList", {}).get("author", []):
                if "authorAffiliationDetailsList" in author:
                    for aff in author["authorAffiliationDetailsList"]["authorAffiliation"]:
                        aff_str = aff.get("affiliation", "")
                        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', aff_str)
                        if emails:
                            email = emails[0]
                            uni_name = aff_str.split('.')[0] if '.' in aff_str else "University / Lab"
                            prof_name = f"{author.get('firstName', '')} {author.get('lastName', '')}".strip()
                            
                            if not any(j['company'] == f"Email: {email}" for j in matched_jobs):
                                matched_jobs.append({
                                    "title": f"Prof. {prof_name} ({uni_name[:40]}...)",
                                    "company": f"Email: {email}",
                                    "link": paper_link,
                                    "source": "Professors"
                                })
                            if len(matched_jobs) >= 50:
                                break
    except Exception as e:
        logger.error(f"Could not search Professors API: {e}")
    return matched_jobs

def fetch_remotive_jobs() -> List[Dict[str, Any]]:
    logger.info("Fetching from Remotive...")
    matched_jobs = []
    search_terms = ["flutter", "machine learning", "python", "deep learning", "computer vision", "ml", "dl"]
    for term in search_terms:
        try:
            response = safe_request(f"https://remotive.com/api/remote-jobs?search={term}", expected_format="json")
            for job in response.json().get('jobs', []):
                title = job['title']
                if not is_good_fit(title):
                    continue
                matched_jobs.append({"title": title, "company": job['company_name'], "link": job['url'], "source": "Remotive"})
        except Exception as e:
            logger.error(f"Remotive API error for term {term}: {e}")
    return matched_jobs

def fetch_nsf_awards() -> List[Dict[str, Any]]:
    logger.info("Fetching from NSF Awards...")
    matched_jobs = []
    url = "https://api.nsf.gov/services/v1/awards.json?keyword=computer+science"
    try:
        response = safe_request(url, expected_format="json")
        data = response.json()
        for award in data.get('response', {}).get('award', []):
            title = award.get('title', '')
            pi = f"{award.get('piFirstName', '')} {award.get('piLastName', '')}".strip()
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
            if len(matched_jobs) >= 50: break
    except Exception as e:
        logger.error(f"NSF API Error: {e}")
    return matched_jobs

def fetch_ukri_projects() -> List[Dict[str, Any]]:
    logger.info("Fetching from UKRI...")
    matched_jobs = []
    url = "https://gtr.ukri.org/gtr/api/projects?q=computer+science"
    headers = {'Accept': 'application/json'}
    try:
        response = safe_request(url, headers=headers, expected_format="json")
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
            if len(matched_jobs) >= 50: break
    except Exception as e:
        logger.error(f"UKRI API Error: {e}")
    return matched_jobs

def fetch_openalex_funders() -> List[Dict[str, Any]]:
    logger.info("Fetching from OpenAlex...")
    matched_jobs = []
    url = "https://api.openalex.org/funders?search=computer"
    try:
        response = safe_request(url, expected_format="json")
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
            if len(matched_jobs) >= 50: break
    except Exception as e:
        logger.error(f"OpenAlex API Error: {e}")
    return matched_jobs

def fetch_openaire_projects() -> List[Dict[str, Any]]:
    logger.info("Fetching from OpenAIRE...")
    matched_jobs = []
    url = "https://api.openaire.eu/search/projects?keywords=computer%20science&format=json&size=50"
    try:
        response = safe_request(url, expected_format="json")
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
        logger.error(f"OpenAIRE API Error: {e}")
    return matched_jobs

def fetch_github_repos() -> List[Dict[str, Any]]:
    logger.info("Fetching from GitHub Repos...")
    matched_jobs = []
    url = "https://api.github.com/search/repositories?q=phd+positions+computer+science&sort=updated"
    try:
        response = safe_request(url, expected_format="json")
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
            if len(matched_jobs) >= 30: break
    except Exception as e:
        logger.error(f"GitHub API Error: {e}")
    return matched_jobs

def fetch_arxiv_papers() -> List[Dict[str, Any]]:
    logger.info("Fetching from ArXiv...")
    matched_jobs = []
    url = "http://export.arxiv.org/api/query?search_query=cat:cs.AI&sortBy=submittedDate&sortOrder=descending&max_results=50"
    try:
        response = safe_request(url)
        root = ET.fromstring(response.content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        for entry in root.findall('atom:entry', ns):
            title = entry.find('atom:title', ns).text.strip()
            authors = [a.find('atom:name', ns).text for a in entry.findall('atom:author', ns)]
            link = entry.find('atom:id', ns).text
            
            prof_str = authors[-1] if authors else "Unknown"
            matched_jobs.append({
                "title": f"Paper: {title[:70]}...",
                "company": f"PI/Author: {prof_str}",
                "link": link,
                "source": "ArXiv Papers"
            })
    except Exception as e:
        logger.error(f"ArXiv API Error: {e}")
    return matched_jobs

# ==========================================
# SMART VALIDATION
# ==========================================

def check_if_closed(url: str) -> bool:
    """Visits the job URL to see if it gives a 404 or says 'closed'."""
    try:
        response = safe_request(url, max_retries=1) # Fast fail for validation
        if response.status_code == 404:
            return True
        text = response.text.lower()
        closed_phrases = [
            "this job is no longer available",
            "this position has been closed",
            "this posting is closed",
            "no longer accepting applications"
        ]
        if any(phrase in text for phrase in closed_phrases):
            return True
    except RequestException:
        pass
    except Exception:
        pass
    return False

def upgrade_db_schema(db: Dict[str, Any]) -> None:
    """Ensures old database entries have required fields for smart validation."""
    current_time = datetime.now().isoformat()
    for link, job_data in db.items():
        if "created_date" not in job_data:
            job_data["created_date"] = current_time
        if "last_checked" not in job_data:
            job_data["last_checked"] = current_time
        if "status" not in job_data:
            job_data["status"] = "active"

def validate_existing_jobs(db: Dict[str, Any]) -> None:
    """Smart checking: only check jobs that haven't been checked in 14 days."""
    logger.info("Performing smart validation on existing opportunities...")
    upgrade_db_schema(db)
    closed_jobs = []
    
    current_time = datetime.now()
    
    for link, job_data in list(db.items()):
        if job_data.get("status") != "active":
            continue
            
        last_checked_str = job_data.get("last_checked", current_time.isoformat())
        try:
            last_checked = datetime.fromisoformat(last_checked_str)
        except ValueError:
            last_checked = current_time
            
        if (current_time - last_checked).days >= 14:
            logger.info(f"Validating old entry: {link}")
            if check_if_closed(link):
                closed_jobs.append(job_data)
                del db[link]
                
                msg = f"❌ <b>Opportunity Closed:</b> {job_data['title']}\nThis job is no longer available!"
                logger.info(msg.replace("<b>", "").replace("</b>", ""))
                send_telegram_alert(msg)
            else:
                job_data["last_checked"] = current_time.isoformat()
            
    if closed_jobs:
        save_db(db)

# ==========================================
# MAIN EXECUTION
# ==========================================

def run_all_scrapers() -> List[Dict[str, Any]]:
    """Runs all APIs in parallel using ThreadPoolExecutor."""
    fetch_functions = [
        fetch_weworkremotely_jobs,
        fetch_bd_govt_jobs,
        fetch_remotive_jobs,
        fetch_professors,
        fetch_nsf_awards,
        fetch_ukri_projects,
        fetch_openalex_funders,
        fetch_openaire_projects,
        fetch_github_repos,
        fetch_arxiv_papers
    ]
    
    all_jobs = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_source = {executor.submit(func): func.__name__ for func in fetch_functions}
        for future in concurrent.futures.as_completed(future_to_source):
            source_name = future_to_source[future]
            try:
                data = future.result()
                if data:
                    all_jobs.extend(data)
                logger.info(f"✅ Extracted {len(data) if data else 0} jobs from {source_name}")
            except Exception as e:
                logger.error(f"❌ Pipeline Failed for {source_name}: {e}")
                
    return all_jobs

def main() -> None:
    logger.info(f"Auto-Trigger Started. Checking for jobs every {CHECK_INTERVAL_MINUTES} minutes.")
    
    while True:
        logger.info(f"--- Running Job Search: {datetime.now().strftime('%H:%M:%S')} ---")
        db = load_db()
        
        # 1. Smart Validate Old Jobs
        if db:
            validate_existing_jobs(db)
            
        # 2. Fetch new opportunities concurrently
        all_jobs = run_all_scrapers()
        
        # 3. Process new jobs
        new_jobs_found = 0
        current_time = datetime.now().isoformat()
        
        for job in all_jobs:
            if not is_duplicate(job, db):
                job["created_date"] = current_time
                job["last_checked"] = current_time
                job["status"] = "active"
                
                db[job['link']] = job
                new_jobs_found += 1
                
                msg = (
                    f"🚀 <b>NEW OPPORTUNITY</b>\n"
                    f"💼 <b>{job['title']}</b>\n"
                    f"🏢 <b>Client/Company:</b> {job['company']}\n"
                    f"🌐 <b>Source:</b> {job['source']}\n"
                    f"🔗 <b>Link:</b> {job['link']}\n"
                )
                logger.info(msg.replace("<b>", "").replace("</b>", ""))
                send_telegram_alert(msg)
        
        if new_jobs_found == 0:
            logger.info("No new jobs found this round.")
        else:
            save_db(db)
            logger.info(f"Found and saved {new_jobs_found} new jobs!")
            push_to_github()
            
        if os.environ.get("GITHUB_ACTIONS") == "true":
            logger.info("Running in GitHub Actions - exiting after one iteration.")
            break
            
        logger.info(f"Waiting for {CHECK_INTERVAL_MINUTES} minutes until the next scan...")
        time.sleep(CHECK_INTERVAL_MINUTES * 60)

if __name__ == "__main__":
    main()
