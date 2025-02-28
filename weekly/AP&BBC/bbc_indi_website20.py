import requests
from bs4 import BeautifulSoup
import unicodedata

def clean_text(text):
    """
    Removes extraneous whitespace and normalizes unicode characters (e.g. â€” -> —).
    """
    text = unicodedata.normalize("NFKC", text)
    return " ".join(text.split())

def scrape_bbc_content(url):
    """
    Scrapes content from a BBC article URL.
    Looks for text in <div data-component="text-block"> and combines <p> tags.
    """
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to retrieve BBC content from {url}. Status code: {response.status_code}")
        return None

    soup = BeautifulSoup(response.content, 'html.parser')
    paragraphs = soup.select('div[data-component="text-block"] p')
    combined_text = ' '.join(clean_text(p.get_text(strip=True)) for p in paragraphs)
    return combined_text
