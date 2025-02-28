# ap_scraper20.py
import requests
from bs4 import BeautifulSoup
import time

def scrape_page_ap(url):
    r = requests.get(url)
    if r.status_code != 200:
        print(f"Failed to retrieve AP page. Status code: {r.status_code}")
        return [], None

    soup = BeautifulSoup(r.text, 'html.parser')
    divs = soup.find_all('div', class_='PagePromo-description')
    unwanted_description = (
        "The Associated Press is an independent global news organization "
        "dedicated to factual reporting. Founded in 1846, AP today remains "
        "the most trusted source of fast, accurate, unbiased news in all formats "
        "and the essential provider of the technology and services vital to the news business. "
        "More than half the world’s population sees AP journalism every day."
    )

    page_data = []
    for div in divs:
        text = div.get_text(strip=True)
        if text == unwanted_description:
            continue

        desc = text
        link_urls = []
        links = div.find_all('a', class_='Link')
        unique_links = set()
        for l in links:
            href = l.get('href')
            if href not in unique_links:
                link_urls.append(href)
                unique_links.add(href)

        # Find timestamp
        date_div = div.find_next('div', class_='PagePromo-date')
        ts = None
        if date_div:
            timestamp_tag = date_div.find('bsp-timestamp')
            if timestamp_tag:
                ts = timestamp_tag.get('data-timestamp')

        page_data.append({
            "Timestamp": ts,
            "Description": desc,
            "Link": ', '.join(link_urls)
        })

    # Next page
    next_page = None
    next_button = soup.find('div', class_='Pagination-nextPage')
    if next_button:
        next_link = next_button.find('a')
        if next_link:
            next_page = next_link.get('href')

    return page_data, next_page

def scrape_ap_in_memory(start_url, max_pages, unwanted_words):
    all_articles = []
    current_url = start_url
    page_count = 0

    while current_url and page_count < max_pages:
        print(f"Scraping AP page {page_count+1}...")
        page_data, next_page = scrape_page_ap(current_url)
        filtered = []
        for art in page_data:
            desc_lower = art["Description"].lower()
            if not any(w.lower() in desc_lower for w in unwanted_words):
                filtered.append(art)
        all_articles.extend(filtered)

        current_url = next_page
        page_count += 1
        time.sleep(1)
    return all_articles
