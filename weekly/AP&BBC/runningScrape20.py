# runningScape20.py
import psycopg2
from bbcscraper20 import scrape_bbc_search_in_memory
from ap_scraper20 import scrape_ap_in_memory
from helperFunction20 import get_unwanted_words_for_company, store_articles_in_db
from urllib.parse import urlparse
from sqlalchemy import create_engine, text

# Parse the DATABASE_URL
DATABASE_URL = "postgresql://postgres:root@localhost:5432/my_database"

def parse_database_url(database_url):
    result = urlparse(database_url)
    return {
        "host": result.hostname,
        "port": result.port,
        "dbname": result.path.lstrip("/"),
        "user": result.username,
        "password": result.password,
    }

def get_companies_from_db():
    """
    Queries the database to get distinct companies from stock_market.monthlyStock.
    Returns a list of company names.
    """
    engine = create_engine(DATABASE_URL)
    query = 'SELECT DISTINCT "Company" FROM stock_market."monthlyStock";'
    companies = []
    with engine.connect() as conn:
        result = conn.execute(text(query))
        # Each row is a tuple; get the first element (Company name)
        companies = [row[0] for row in result]
    return companies

def main():
    # Parse the database configuration for psycopg2 (used in helper functions)
    db_config = parse_database_url(DATABASE_URL)

    # Get list of companies from the DB query
    companies = get_companies_from_db()
    if not companies:
        print("No companies found in the database. Exiting.")
        return

    # Loop through each company and scrape data
    for company in companies:
        print(f"\n--- Scraping for {company} ---")
        unwanted_words = get_unwanted_words_for_company(db_config, company)
        print(f"Unwanted words: {unwanted_words}")

        # Scrape BBC articles
        print("Scraping BBC...")
        bbc_articles = scrape_bbc_search_in_memory(query=company, max_pages=5, unwanted_words=unwanted_words)
        store_articles_in_db(db_config, bbc_articles, company, "BBC")

        # Scrape AP articles
        print("Scraping AP...")
        ap_start_url = f"https://apnews.com/search?q={company}+company&f2=00000188-f942-d221-a78c-f9570e360000&s=0"
        ap_articles = scrape_ap_in_memory(ap_start_url, max_pages=3, unwanted_words=unwanted_words)
        store_articles_in_db(db_config, ap_articles, company, "AP")

    print("All done!")

if __name__ == "__main__":
    main()
