import psycopg2
from urllib.parse import urlparse
import re

SE_URL = "postgresql://postgres:root@localhost:5432/my_database"

def parse_database_url(database_url):
    """
    Parse the database URL into connection parameters.
    """
    result = urlparse(database_url)
    return {
        "host": result.hostname,
        "port": result.port,
        "dbname": result.path.lstrip("/"),
        "user": result.username,
        "password": result.password,
    }

def main():
    # ----------------------------------------------------
    # 1. Connect to the database
    # ----------------------------------------------------
    db_info = parse_database_url(SE_URL)
    conn = psycopg2.connect(**db_info)
    conn.autocommit = True
    cur = conn.cursor()

    # ----------------------------------------------------
    # 2. Fetch all necessary data
    # ----------------------------------------------------
    # basearticles
    cur.execute("""
        SELECT id, timestamp, company, newssite, description, link
          FROM public.basearticles
    """)
    basearticles = cur.fetchall()

    # unwanted_words
    cur.execute("""
        SELECT id, company, word
          FROM filtered_words.unwanted_words
    """)
    unwanted_words = cur.fetchall()

    # combinationtable (note the quotes if needed for the case-sensitive name)
    cur.execute("""
        SELECT id, company, newssite, must_have, to_have, not_to_have
          FROM filtered_words."CombinationTable"
    """)
    combination_rows = cur.fetchall()

    # Convert the rows into lists of dictionaries for easier handling.
    unwanted_words_list = [
        {"id": row[0], "company": row[1], "word": row[2]}
        for row in unwanted_words
    ]

    combination_list = [
        {"id": row[0], "company": row[1], "newssite": row[2],
         "must_have": row[3], "to_have": row[4], "not_to_have": row[5]}
        for row in combination_rows
    ]

    # ----------------------------------------------------
    # 3. Define helper functions
    # ----------------------------------------------------
    def matches_company(filter_company, article_company):
        """
        Returns True if the filter applies to this article's company.
        'All' means always matches.
        """
        if not filter_company:
            return False
        if filter_company.lower().strip() == "all":
            return True
        return filter_company.lower().strip() == article_company.lower().strip()

    def matches_newssite(filter_newssite, article_newssite):
        """
        Returns True if the filter applies to this article's newssite.
        'All' means always matches.
        """
        if not filter_newssite:
            return False
        if filter_newssite.lower().strip() == "all":
            return True
        return filter_newssite.lower().strip() == article_newssite.lower().strip()

    def contains_word(description, word):
        """
        Uses regex to perform a whole word, case-insensitive search.
        Returns True if the exact word is found in the description.
        """
        if not word or not description:
            return False
        pattern = r'\b' + re.escape(word) + r'\b'
        return re.search(pattern, description, re.IGNORECASE) is not None

    def passes_combination_row(article_company, article_newssite, description, row):
        """
        Checks if an article passes a single combinationtable rule.
        
        - If must_have equals 'C_N', then the article's description must contain its own company.
        - Otherwise, the article must contain the text in must_have.
        - If to_have is set, it must appear in the description.
        - If not_to_have is set, it must NOT appear.
        """
        # First, ensure that this combination row applies.
        if not matches_company(row["company"], article_company):
            return False
        if not matches_newssite(row["newssite"], article_newssite):
            return False

        must_have = row["must_have"]
        to_have = row["to_have"]
        not_to_have = row["not_to_have"]

        # Check must_have condition.
        if must_have:
            if must_have.strip().lower() == "c_n":
                # 'C_N' means the article must contain its own company name.
                if not contains_word(description, article_company):
                    return False
            else:
                if not contains_word(description, must_have):
                    return False

        # Check to_have condition.
        if to_have:
            if not contains_word(description, to_have):
                return False

        # Check not_to_have condition.
        if not_to_have:
            if contains_word(description, not_to_have):
                return False

        return True

    def rescue_by_combination(article_company, article_newssite, description):
        """
        If an article is flagged for removal by an unwanted word,
        check if any matching combination rule "rescues" it.
        Returns True if at least one combination row allows it to stay.
        """
        possible_rows = [
            row for row in combination_list
            if matches_company(row["company"], article_company) and
               matches_newssite(row["newssite"], article_newssite)
        ]
        for comb_row in possible_rows:
            if passes_combination_row(article_company, article_newssite, description, comb_row):
                return True
        return False

    def final_combination_filter(article_company, article_newssite, description):
        """
        Final pass using combinationtable rules.
        If there are any combination rules matching the article,
        the article is kept if at least one of those rules is satisfied.
        If no combination rules apply, the article is kept.
        """
        relevant_rows = [
            row for row in combination_list
            if matches_company(row["company"], article_company) and
               matches_newssite(row["newssite"], article_newssite)
        ]
        if not relevant_rows:
            return True
        for comb_row in relevant_rows:
            if passes_combination_row(article_company, article_newssite, description, comb_row):
                return True
        return False

    # ----------------------------------------------------
    # 4. First pass: Apply unwanted_words filter with rescue check
    # ----------------------------------------------------
    survived_unwanted = []
    for row in basearticles:
        article_id, article_ts, article_company, article_newssite, description, link = row
        drop_due_to_unwanted = False
        for uw in unwanted_words_list:
            if matches_company(uw["company"], article_company):
                if contains_word(description, uw["word"]):
                    # If an unwanted word is found, check for rescue via combinationtable.
                    if not rescue_by_combination(article_company, article_newssite, description):
                        drop_due_to_unwanted = True
                        break
        if not drop_due_to_unwanted:
            survived_unwanted.append(row)

    # ----------------------------------------------------
    # 5. Second pass: Apply final combinationtable filter
    # ----------------------------------------------------
    final_kept = []
    for row in survived_unwanted:
        article_id, article_ts, article_company, article_newssite, description, link = row
        if final_combination_filter(article_company, article_newssite, description):
            final_kept.append(row)

    # ----------------------------------------------------
    # 6. Write the final kept articles to the filtered table.
    # ----------------------------------------------------
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS public.basearticles_filtered (
        id          BIGINT PRIMARY KEY,
        timestamp   BIGINT,
        company     VARCHAR,
        newssite    VARCHAR,
        description TEXT,
        link        TEXT
    )
    """
    cur.execute(create_table_sql)
    cur.execute("TRUNCATE public.basearticles_filtered")

    insert_sql = """
    INSERT INTO public.basearticles_filtered
        (id, timestamp, company, newssite, description, link)
    VALUES (%s, %s, %s, %s, %s, %s)
    """

    for article in final_kept:
        cur.execute(insert_sql, article)

    cur.close()
    conn.close()

    print(f"Filtering complete. Final kept articles: {len(final_kept)}.")

if __name__ == "__main__":
    main()
