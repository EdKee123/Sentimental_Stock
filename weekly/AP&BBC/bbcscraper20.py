# bbcscraper20.py
import requests
import time
import datetime
from bs4 import BeautifulSoup
import subprocess

# ----- Constants for IP Changing -----
IP_CHANGE_FREQUENCY = 3  # Change IP every 3 BBC page scrapes (adjust as needed)
ip_script_path = r"C:\Users\Edkee\Documents\4th\Project\Sentimental_Stock\IPchange\IPRegChange.py"


def get_last_1800_utc():
    now = datetime.datetime.utcnow()
    if now.hour >= 18:
        return now.replace(hour=18, minute=0, second=0, microsecond=0)
    else:
        yday = now - datetime.timedelta(days=1)
        return yday.replace(hour=18, minute=0, second=0, microsecond=0)

def convert_bbc_date_string(date_string):
    date_string = date_string.lower().strip()
    now = datetime.datetime.utcnow()
    if "hrs ago" in date_string:
        dt = get_last_1800_utc()
    elif "days ago" in date_string:
        parts = date_string.split()
        try:
            days_ago = int(parts[0])
        except:
            days_ago = 1
        raw_dt = now - datetime.timedelta(days=days_ago)
        dt = raw_dt.replace(hour=18, minute=0, second=0, microsecond=0)
    else:
        try:
            dt_parsed = datetime.datetime.strptime(date_string, '%d %b %Y')
            dt = dt_parsed.replace(hour=18, minute=0, second=0, microsecond=0)
        except ValueError:
            dt = get_last_1800_utc()
    return int(dt.timestamp())

def scrape_page_bbc(page_url):
    print(f"Fetching BBC page: {page_url}")
    r = requests.get(page_url)
    if r.status_code != 200:
        print(f"Failed to retrieve. Status code: {r.status_code}")
        return []

    soup = BeautifulSoup(r.content, 'html.parser')
    article_divs = soup.find_all('div', {'data-testid': 'anchor-inner-wrapper'})

    data = []
    for div in article_divs:
        link_tag = div.find('a')
        if not link_tag:
            continue
        link_href = link_tag.get('href', '')
        if not link_href.startswith("/news/articles/"):
            continue
        full_link = "https://www.bbc.com" + link_href

        headline_tag = div.find('h2', {'data-testid': 'card-headline'})
        headline_text = headline_tag.get_text(strip=True) if headline_tag else ""

        date_tag = div.find('span', {'data-testid': 'card-metadata-lastupdated'})
        if date_tag:
            date_text = date_tag.get_text(strip=True)
            epoch_ts = convert_bbc_date_string(date_text)
        else:
            epoch_ts = None

        data.append({
            "Timestamp": epoch_ts,
            "Description": headline_text,
            "Link": full_link
        })
    return data

def scrape_bbc_search_in_memory(query, max_pages, unwanted_words):
    """
    Returns a list of articles (dicts) for the given query, ignoring unwanted words in the headline.
    Also changes the IP address every IP_CHANGE_FREQUENCY pages.
    """
    all_articles = []
    for page_num in range(max_pages):
        url = f"https://www.bbc.com/search?q={query}&page={page_num}"
        page_articles = scrape_page_bbc(url)
        filtered = []
        for art in page_articles:
            desc = art["Description"].lower()
            if not any(w.lower() in desc for w in unwanted_words):
                filtered.append(art)
        all_articles.extend(filtered)
        
        # Change IP after every IP_CHANGE_FREQUENCY pages
        if (page_num + 1) % IP_CHANGE_FREQUENCY == 0:
            print("Changing IP address...")
            subprocess.run(["python", ip_script_path])
        
        time.sleep(1)
    return all_articles
