import time
import psycopg2
from psycopg2.extras import execute_values

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementClickInterceptedException
)
from webdriver_manager.chrome import ChromeDriverManager

def main():
    # --------------------------------------------------------------
    # 1. Connect to PostgreSQL
    # --------------------------------------------------------------
    db_host = "localhost"
    db_name = "my_database"
    db_user = "postgres"
    db_pass = "root"
    db_port = 5432  # Adjust as needed

    try:
        conn = psycopg2.connect(
            host=db_host,
            dbname=db_name,
            user=db_user,
            password=db_pass,
            port=db_port
        )
        print("Connected to PostgreSQL successfully.")
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return

    # Create table live_data if not exists
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS public.live_data (
        id SERIAL PRIMARY KEY,
        description TEXT,
        url TEXT
    );
    """
    try:
        with conn.cursor() as cur:
            cur.execute(create_table_sql)
            conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error creating table live_data: {e}")
        conn.close()
        return

    # --------------------------------------------------------------
    # 2. Launch Headless Chrome
    # --------------------------------------------------------------
    chrome_options = Options()
    chrome_options.add_argument("--headless")  
    chrome_options.add_argument("--start-maximized")

    try:
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        print("WebDriver initialized in headless mode.")
    except Exception as e:
        print(f"Error initializing WebDriver: {e}")
        conn.close()
        return

    # --------------------------------------------------------------
    # 3. Go to Yahoo Finance Latest News
    # --------------------------------------------------------------
    url = "https://finance.yahoo.com/topic/latest-news/"
    driver.get(url)
    time.sleep(3)

    # --------------------------------------------------------------
    # 4. Accept Cookies if Found
    # --------------------------------------------------------------
    try:
        accept_btn = driver.find_element(
            By.XPATH,
            "//button[contains(@class, 'accept-all') and @name='agree']"
        )
        accept_btn.click()
        print("Clicked 'Accept All' cookies button.")
        time.sleep(2)
    except NoSuchElementException:
        print("No 'Accept All' cookies button found.")
    except ElementClickInterceptedException:
        print("Couldn't click 'Accept All' cookies. Possibly already accepted.")
    except Exception as e:
        print(f"Unexpected cookie error: {e}")

    # --------------------------------------------------------------
    # 5. Scroll to Load More (Optional, up to some attempts)
    # --------------------------------------------------------------
    max_scroll_attempts = 3
    scroll_count = 0
    last_height = driver.execute_script("return document.body.scrollHeight")

    while scroll_count < max_scroll_attempts:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)  # wait for load
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            scroll_count += 1
        else:
            scroll_count = 0
            last_height = new_height

    # --------------------------------------------------------------
    # 6. Scrape All <div class="content yf-82qtw3">
    #    Each article is typically in one of these content blocks
    #    We'll combine any <h3> and <p> of class clamp yf-82qtw3
    # --------------------------------------------------------------
    all_articles = []
    content_blocks = driver.find_elements(By.CSS_SELECTOR, "div.content.yf-82qtw3")

    for block in content_blocks:
        try:
            # Grab the link (URL) from the first <a> inside this block
            a_el = block.find_element(By.TAG_NAME, "a")
            article_url = a_el.get_attribute("href")

            # Grab all textual parts: <h3 class="clamp yf-82qtw3"> + <p class="clamp yf-82qtw3">
            text_parts = block.find_elements(
                By.CSS_SELECTOR, "h3.clamp.yf-82qtw3, p.clamp.yf-82qtw3"
            )
            # Combine them
            combined_text = " ".join(tp.text.strip() for tp in text_parts if tp.text.strip())

            if combined_text:
                all_articles.append((combined_text, article_url))
        except NoSuchElementException:
            # Possibly some unexpected structure, skip
            continue
        except Exception as e:
            print(f"Error extracting from a content block: {e}")
            continue

    driver.quit()
    print(f"Total articles scraped: {len(all_articles)}")

    # --------------------------------------------------------------
    # 7. Insert into live_data
    # --------------------------------------------------------------
    if not all_articles:
        print("No articles to insert.")
        conn.close()
        return

    insert_sql = """
    INSERT INTO public.live_data (description, url)
    VALUES %s
    """
    try:
        with conn.cursor() as cur:
            execute_values(cur, insert_sql, all_articles)
            conn.commit()
        print(f"Inserted {len(all_articles)} articles into live_data.")
    except Exception as e:
        conn.rollback()
        print(f"Failed to insert articles: {e}")

    # --------------------------------------------------------------
    # 8. Cleanup
    # --------------------------------------------------------------
    conn.close()
    print("Done. Connection closed.")

if __name__ == "__main__":
    main()
