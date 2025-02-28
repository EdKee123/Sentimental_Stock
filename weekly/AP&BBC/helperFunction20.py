# helperFunction20.py
import psycopg2

def get_unwanted_words_for_company(db_config, company):
    """
    Fetch all unwanted words for the given company from filtered_words.unwanted_words.
    Returns a list of strings (the words).
    """
    conn = psycopg2.connect(**db_config)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT word
                FROM filtered_words.unwanted_words
                WHERE company_name = %s
            """, (company,))
            rows = cur.fetchall()
            # rows is like [( 'brazil', ), ('river', ), ...]
            unwanted = [r[0] for r in rows]
        return unwanted
    finally:
        conn.close()

def store_articles_in_db(db_config, articles, company, news_site):
    """
    Inserts articles into public.basearticles if an article with the same company and link doesn't already exist.
    Each article is a dict with keys: Timestamp, Description (or Headline), Link.
    """
    conn = psycopg2.connect(**db_config)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            # SQL to check for an existing article for the same company and link.
            select_sql = """
                SELECT 1 FROM basearticles WHERE company = %s AND link = %s
            """
            # SQL to insert the article.
            insert_sql = """
                INSERT INTO basearticles (timestamp, company, newssite, description, link)
                VALUES (%s, %s, %s, %s, %s)
            """
            for art in articles:
                ts = art.get("Timestamp")    # might be None
                desc = art.get("Description") or art.get("Headline") or ""
                link = art.get("Link") or art.get("Links") or ""
                
                # Check for duplicate: same company and link
                cur.execute(select_sql, (company, link))
                exists = cur.fetchone()
                if not exists:
                    cur.execute(insert_sql, (ts, company, news_site, desc, link))
    finally:
        conn.close()
