#!/usr/bin/env python
"""
Master script to run the full workflow:
1. Scrape articles (BBC & AP) and store them in the 'basearticles' table.
2. Filter articles and write the final set to the 'basearticles_filtered' table.
3. Scrape the full content from each article and store it in 'scrapedcontent'.
4. Run sentiment analysis on the scraped content and store results in 'sentimental_data'.
"""

import time

# Import each module. Adjust the module names if your files are named differently.
import runningScape20
import BaseArticleFilter      # This is the file containing the filtering code.
import content_scraper  # This is the file that scrapes full article content.
import sentiment_analysis  # This file performs sentiment analysis.

def main():
    print("Step 1: Scraping initial articles (populating basearticles)...")
    runningScape20.main()
    print("Step 1 complete.\n")
    
    # Optional pause between steps.
    time.sleep(2)
    
    print("Step 2: Filtering articles (writing to basearticles_filtered)...")
    filtering.main()
    print("Step 2 complete.\n")
    
    time.sleep(2)
    
    print("Step 3: Scraping full article content (populating scrapedcontent)...")
    content_scraper.main()
    print("Step 3 complete.\n")
    
    time.sleep(2)
    
    print("Step 4: Performing sentiment analysis (writing to sentimental_data)...")
    sentiment_analysis.main()
    print("Step 4 complete.\n")
    
    print("All steps complete! Full workflow executed.")

if __name__ == "__main__":
    main()
