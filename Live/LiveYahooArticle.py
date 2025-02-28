import sys
import time
import requests
import psycopg2
from psycopg2.extras import execute_values
from bs4 import BeautifulSoup
from datetime import datetime
import subprocess
import re
from urllib.parse import urlparse

def get_db_connection():
    """
    Returns a new PostgreSQL connection.
    Modify credentials for your environment.
    """
    db_host = "localhost"
    db_name = "my_database"
    db_user = "postgres"
    db_pass = "root"
    db_port = 5432
    return psycopg2.connect(
        host=db_host,
        dbname=db_name,
        user=db_user,
        password=db_pass,
        port=db_port
    )

def run_ip_reg_change(ip_script_path: str):
    """
    Executes the IPRegChange.py script to rotate IP.
    """
    try:
        print(f"[IP] Running IPRegChange script: {ip_script_path}")
        subprocess.run(['python', ip_script_path], check=True)
        print("[IP] IPRegChange executed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"[IP] IPRegChange failed with return code {e.returncode}.")
    except FileNotFoundError:
        print(f"[IP] IPRegChange script not found at: {ip_script_path}")
    except Exception as e:
        print(f"[IP] Unexpected error during IPRegChange: {e}")

def create_livearticles_table(conn):
    """
    Creates the Livearticles table if it does not exist.
    Columns: id SERIAL PRIMARY KEY, timestamp INT, company TEXT, newssite TEXT, link TEXT, fullarticle TEXT
    """
    create_sql = """
    CREATE TABLE IF NOT EXISTS public."Livearticles" (
      id SERIAL PRIMARY KEY,
      "timestamp" INT,
      company TEXT,
      newssite TEXT,
      link TEXT,
      fullarticle TEXT
    );
    """
    try:
        with conn.cursor() as cur:
            cur.execute(create_sql)
        conn.commit()
        print("[DB] Ensured table 'Livearticles' exists.")
    except Exception as e:
        conn.rollback()
        print(f"[DB] Error creating 'Livearticles' table: {e}")

def get_companies_and_tickers(conn):
    """
    Fetch distinct (Company, StockTicker) pairs from stock_market."monthlyStock".
    Returns a list of tuples: [(company, ticker), ...]
    """
    results = []
    sql = """
        SELECT DISTINCT "Company", "StockTicker"
        FROM stock_market."monthlyStock"
        WHERE "Company" IS NOT NULL
          AND "StockTicker" IS NOT NULL
          AND "Company" <> ''
          AND "StockTicker" <> '';
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            for row in rows:
                company = row[0].strip()
                ticker = row[1].strip()
                results.append((company, ticker))
    except Exception as e:
        print(f"[DB] Error fetching companies and tickers: {e}")
    return results

def get_live_data_rows(conn):
    """
    Fetches rows from public.live_data: (id, description, url).
    Returns a list of tuples.
    """
    results = []
    sql = """
        SELECT id, description, url
        FROM public.live_data
        WHERE url IS NOT NULL AND url <> ''
        ORDER BY id ASC;
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            results = cur.fetchall()
    except Exception as e:
        print(f"[DB] Error fetching rows from live_data: {e}")
    return results

def find_all_matches(description, company_ticker_list):
    """
    Given a description and a list of (company, ticker) pairs,
    returns a list of matches where either:
      - The ticker appears as a whole word.
      - The company name appears as a whole word, allowing an optional trailing "'s".
    
    For example, for company "ARM", "ARM" or "ARM's" will match,
    but "disarm" will not.
    """
    matches = []
    for (company, ticker) in company_ticker_list:
        ticker_pattern = r'\b' + re.escape(ticker) + r'\b'
        company_pattern = r'\b' + re.escape(company) + r"(?:'s)?\b"
        if re.search(ticker_pattern, description, flags=re.IGNORECASE) or re.search(company_pattern, description, flags=re.IGNORECASE):
            matches.append((company, ticker))
    return matches

def scrape_article_details(url: str) -> tuple:
    """
    Scrapes the article page at the given URL using requests + BeautifulSoup.
    Returns a tuple (full_text, newssite) where:
      - full_text: The concatenated text from all <p> tags.
      - newssite: Extracted from the first <a class="subtle-link fin-size-small yf-1xqzjha"> tag's title attribute,
                  or if not found, the URL's domain.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0.0.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"[SCRAPE] Error fetching {url}: {e}")
        return ("", urlparse(url).netloc or "Unknown")
    
    soup = BeautifulSoup(resp.text, "html.parser")
    paragraphs = soup.find_all("p")
    full_text = " ".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
    
    # Look for the specific anchor tag to get newssite from its title attribute.
    anchor = soup.find("a", class_="subtle-link fin-size-small yf-1xqzjha")
    if anchor and anchor.has_attr("title"):
        newssite = anchor.get("title").strip()
    else:
        newssite = urlparse(url).netloc or "Unknown"
    
    return (full_text, newssite)

def insert_into_livearticles(conn, timestamp_val, company, newssite, link, article_text):
    """
    Inserts a row into Livearticles with the provided values.
    """
    insert_sql = """
        INSERT INTO public."Livearticles"("timestamp", company, newssite, link, fullarticle)
        VALUES (%s, %s, %s, %s, %s)
    """
    try:
        with conn.cursor() as cur:
            cur.execute(insert_sql, (timestamp_val, company, newssite, link, article_text))
        conn.commit()
        print(f"[DB] Inserted article for {company} from {link}")
    except Exception as e:
        conn.rollback()
        print(f"[DB] Failed to insert article for {link}: {e}")

def main():
    # 1. Connect to DB
    try:
        conn = get_db_connection()
        print("[DB] Connected to PostgreSQL.")
    except Exception as e:
        print(f"[DB] Cannot connect to PostgreSQL: {e}")
        sys.exit(1)

    # 2. Ensure Livearticles table exists
    create_livearticles_table(conn)

    # 3. Get (Company, StockTicker) pairs
    company_ticker_list = get_companies_and_tickers(conn)
    print(f"[DB] Fetched {len(company_ticker_list)} company/ticker pairs.")

    # 4. Get rows from live_data
    live_rows = get_live_data_rows(conn)
    total_rows = len(live_rows)
    print(f"[DB] Fetched {total_rows} rows from live_data.")

    if total_rows == 0:
        conn.close()
        print("[DB] No data to process. Exiting.")
        return

    # 5. Run initial IP rotation
    ip_script_path = r"C:\Users\Edkee\Documents\4th\Project\Sentimental_Stock\IPchange\IPRegChange.py"
    
    run_ip_reg_change(ip_script_path)

    # If more than 20 articles to check, do a second IP rotation after processing 20 rows.
    do_second_ip_change = (total_rows > 20)

    processed_count = 0
    for idx, (row_id, description, url) in enumerate(live_rows, start=1):
        # Rotate IP after processing 20 rows if applicable.
        if do_second_ip_change and idx == 21:
            print("[IP] Processed 20 articles. Running second IP rotation.")
            run_ip_reg_change(ip_script_path)

        # Use the improved matching function.
        matches = find_all_matches(description, company_ticker_list)
        if matches:
            # Scrape the full article details once per URL.
            article_text, newssite = scrape_article_details(url)
            current_epoch = int(datetime.utcnow().timestamp())
            # Insert a row for each matching (company, ticker) pair.
            for (company, ticker) in matches:
                insert_into_livearticles(conn, current_epoch, company, newssite, url, article_text)
        processed_count += 1

    conn.close()
    print(f"[DB] Done. Processed {processed_count} rows from live_data. Connection closed.")

if __name__ == "__main__":
    main()
