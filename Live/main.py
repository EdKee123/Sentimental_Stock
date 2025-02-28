from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import subprocess
import os

from typing import List, Dict

DATABASE_URL = "postgresql://postgres:root@localhost:5432/my_database"

app = FastAPI()

# Allow CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SCRIPTS_DIR = r"C:\Users\Edkee\Documents\4th\Project\Sentimental_Stock\Live"


def truncate_tables():
    """
    Truncate the three tables so they only contain fresh data.
    """
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute('TRUNCATE TABLE public."LiveSentimental" RESTART IDENTITY CASCADE;')
            cur.execute('TRUNCATE TABLE public."Livearticles" RESTART IDENTITY CASCADE;')
            cur.execute('TRUNCATE TABLE public.live_data RESTART IDENTITY CASCADE;')
        conn.commit()

def run_pipeline_scripts():
    """
    Runs the 5 scripts in the specified order.
    """
    scripts_order = [
        "LiveUpdateStock.py",
        "LiveYahooScrape.py",
        "LiveYahooArticle.py",
        "LiveSentinmentAnalysis.py",
        "LiveMachineLearningPrediction.py"
    ]
    for script_name in scripts_order:
        script_path = os.path.join(SCRIPTS_DIR, script_name)
        print(f"Running script: {script_path} ...")
        subprocess.run(["python", script_path], check=True)
        print(f"Finished: {script_name}")

def fetch_final_predictions() -> List[Dict]:
    results = []
    query = """
    SELECT company, newssite, predicted_label, prob_down, prob_same, prob_up
    FROM public."LiveSentimental"
    WHERE predicted_label IS NOT NULL;
    """
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            for r in rows:
                results.append({
                    "company": r[0],
                    "newssite": r[1],
                    "prediction": r[2],
                    "prob_down": float(r[3]),
                    "prob_same": float(r[4]),
                    "prob_up": float(r[5])
                })
    return results

@app.post("/runAll")
def run_all_pipeline():
    """
    Truncate tables, run pipeline scripts, fetch predictions, return them in JSON.
    """
    try:
        # 1) Truncate
        truncate_tables()
        # 2) Run the pipeline
        run_pipeline_scripts()
        # 3) Fetch final predictions
        predictions = fetch_final_predictions()
        return {"status": "ok", "predictions": predictions}
    except Exception as e:
        return {"status": "error", "message": str(e)}

###############################################################
# The rest are your existing endpoints for the front-end
###############################################################

def get_companies():
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT DISTINCT "company" FROM public.sentimental_data ORDER BY "company" ASC;')
            rows = cur.fetchall()
            companies = [row[0] for row in rows]
    return companies

@app.get("/companies")
def companies():
    return {"companies": get_companies()}

@app.get("/stockdata")
def get_stockdata(company: str = Query(..., description="Name of the company")):
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Fetch stock data
            query_data = '''
                SELECT "Timestamp", "Adj_Close" 
                FROM stock_market."monthlyStock"
                WHERE "Company" = %s
                ORDER BY "Timestamp" ASC;
            '''
            cur.execute(query_data, (company,))
            rows = cur.fetchall()

            # Fetch max/min for chart
            query_range = '''
                SELECT MAX("Adj_Close"), MIN("Adj_Close") 
                FROM stock_market."monthlyStock"
                WHERE "Company" = %s;
            '''
            cur.execute(query_range, (company,))
            max_val, min_val = cur.fetchone()
            min_adjusted = min_val - 5 if min_val is not None else None
            max_adjusted = max_val + 5 if max_val is not None else None

            # x-axis max
            query_x_max = '''
                SELECT MAX("Timestamp")
                FROM stock_market."monthlyStock"
                WHERE "Company" = %s;
            '''
            cur.execute(query_x_max, (company,))
            x_max = cur.fetchone()[0]

    return {
        "data": [{"timestamp": row[0], "adj_close": row[1]} for row in rows],
        "range": {"min": min_adjusted, "max": max_adjusted},
        "x_max": x_max
    }

@app.get("/sentimentdata")
def get_sentimentdata(company: str = Query(..., description="Name of the company")):
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            query = '''
                SELECT "timestamp", "positive", "neutral", "negative", "newssite"
                FROM public.sentimental_data
                WHERE "company" = %s
                ORDER BY "timestamp" ASC;
            '''
            cur.execute(query, (company,))
            rows = cur.fetchall()

    sentiment_data = []
    for row in rows:
        timestamp, positive, neutral, negative, newssite = row
        max_val = max(positive, neutral, negative)
        min_val = min(positive, neutral, negative)
        if positive == max_val:
            score = positive - neutral - negative
        elif negative == max_val:
            score = -(negative - neutral - positive)
        elif neutral == max_val and negative == min_val:
            score = positive - negative
        elif neutral == max_val and positive == min_val:
            score = -(negative - positive)
        else:
            score = 0
        sentiment_data.append({
            "timestamp": timestamp,
            "score": score,
            "newssite": newssite,
            "breakdown": {
                "positive": positive,
                "neutral": neutral,
                "negative": negative
            }
        })

    return {"data": sentiment_data}
