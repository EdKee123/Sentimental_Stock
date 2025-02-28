import psycopg2
from psycopg2.extras import DictCursor
from urllib.parse import urlparse
from bbc_indi_website20 import scrape_bbc_content
from ap_indi_website20 import scrape_ap_content

# Database configuration
DATABASE_URL = "postgresql://postgres:root@localhost:5432/my_database"

def parse_database_url(db_url):
    """
    Parses a postgres:// URL and returns a dict suitable for psycopg2.connect.
    """
    result = urlparse(db_url)
    return {
        "host": result.hostname,
        "port": result.port or 5432,
        "dbname": result.path.lstrip("/"),
        "user": result.username,
        "password": result.password,
    }

def main():
    # 1) Parse the database URL into connection parameters
    db_config = parse_database_url(DATABASE_URL)

    # 2) Connect to Postgres
    conn = psycopg2.connect(**db_config)
    conn.autocommit = True

    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            # 3) Create the new scrapedcontent table if it doesn't exist
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS public.scrapedcontent (
                id           INT PRIMARY KEY,
                timestamp    BIGINT,
                company      TEXT,
                newssite     TEXT,
                link         TEXT,
                fullarticle  TEXT
            );
            """
            cur.execute(create_table_sql)
            print("Ensured table 'scrapedcontent' exists.")

            # 4) Select articles from basearticles
            select_sql = """
                SELECT id, timestamp, company, newssite, link
                FROM public.basearticles
                ORDER BY id;
            """
            cur.execute(select_sql)
            rows = cur.fetchall()

            for row in rows:
                article_id = row['id']
                timestamp = row['timestamp']
                company = row['company']
                news_site = row['newssite'].lower()  # e.g. "BBC" or "AP"
                link = row['link']

                print(f"\n--- Scraping ID={article_id}, Company={company}, Site={news_site}, Link={link}")

                # 5) Call the appropriate scraper
                if "bbc" in news_site:
                    content = scrape_bbc_content(link)
                elif "ap" in news_site:
                    content = scrape_ap_content(link)
                else:
                    print(f"Unknown site: {news_site}, skipping this row.")
                    continue

                if not content:
                    print("No content scraped, skipping insert.")
                    continue

                # 6) Insert into scrapedcontent table
                insert_sql = """
                    INSERT INTO public.scrapedcontent (id, timestamp, company, newssite, link, fullarticle)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING;
                """
                cur.execute(insert_sql, (article_id, timestamp, company, news_site, link, content))
                print("Scraped content successfully inserted.")

    finally:
        conn.close()

if __name__ == "__main__":
    main()
