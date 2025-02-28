import requests
from bs4 import BeautifulSoup
import unicodedata

def scrape_ap_content(url):
    """
    Scrapes content from an AP article URL.
    Looks for text in <div class="RichTextStoryBody"> or <div class="RichTextBody">.
    Removes <span class="LinkEnhancement"> and ensures link text is separated by spaces.
    """
    response = requests.get(url)
    # Fix encoding using the detected encoding
    response.encoding = response.apparent_encoding

    if response.status_code != 200:
        print(f"Failed to retrieve AP content from {url}. Status code: {response.status_code}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    paragraphs = soup.select('div.RichTextStoryBody p, div.RichTextBody p')

    combined_text = []
    for p in paragraphs:
        # Remove <span class="LinkEnhancement">
        for span in p.find_all('span', class_='LinkEnhancement'):
            span.unwrap()

        # Add spaces around link text, remove <a> tags
        for link in p.find_all('a', class_='AnClick-LinkEnhancement'):
            link_text = link.get_text(strip=True)
            link.insert_before(" ")
            link.insert_after(" ")
            link.replace_with(link_text)

        paragraph_text = p.get_text(strip=True)
        combined_text.append(paragraph_text)

    return " ".join(combined_text)
