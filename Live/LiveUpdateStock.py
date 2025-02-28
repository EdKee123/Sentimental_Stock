import yfinance as yf
import pandas as pd
import csv
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError  # For DB error handling

# ------------------------------------------------------------------------------
# 1) DATABASE CONNECTION & RETRIEVAL OF COMPANIES
# ------------------------------------------------------------------------------
DATABASE_URL = "postgresql://postgres:root@localhost:5432/my_database"
engine = create_engine(DATABASE_URL)

# Retrieve distinct companies and their stock tickers from the database
query = 'SELECT DISTINCT "Company", "StockTicker" FROM stock_market."monthlyStock";'
with engine.connect() as conn:
    result = conn.execute(text(query)).fetchall()

companies = {row[0]: row[1] for row in result}

if not companies:
    print("No companies found from the database query.")
    # Optionally, exit or define a fallback dictionary
    # exit(1)

# ------------------------------------------------------------------------------
# 2) DEFINE TIME CHUNK: FROM MAXIMUM TIMESTAMP IN THE DB TO NOW
# ------------------------------------------------------------------------------
# Query the maximum timestamp (epoch seconds) from the table
with engine.connect() as conn:
    max_ts_result = conn.execute(text('SELECT MAX("Timestamp") FROM stock_market."monthlyStock";')).fetchone()

max_ts = max_ts_result[0]
if max_ts is None:
    # If no data exists in the table, fall back to a default start datetime.
    start_dt = datetime(2025, 2, 17, 9, 30)
else:
    # Convert the max timestamp (epoch seconds) to a datetime object.
    start_dt = datetime.fromtimestamp(max_ts)

end_dt = datetime.now()  # Use current time as the end of the time chunk
time_chunks = [(start_dt, end_dt)]
print(f"Time chunk set from {start_dt} to {end_dt}")

# ------------------------------------------------------------------------------
# 3) LOOP OVER COMPANIES & TIME CHUNKS TO DOWNLOAD, PROCESS, & SAVE DATA
# ------------------------------------------------------------------------------
for company_name, ticker in companies.items():
    print(f"Processing {company_name} ({ticker})...")
    all_chunks = []

    for (chunk_start, chunk_end) in time_chunks:
        print(f"  - Downloading data from {chunk_start} to {chunk_end}")
        ticker_obj = yf.Ticker(ticker)
        data = ticker_obj.history(start=chunk_start, end=chunk_end, interval="1m")

        # Flatten MultiIndex columns if necessary
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)

        if data.empty:
            print(f"    [WARNING] No data for {company_name} ({ticker}) in {chunk_start} – {chunk_end}")
            continue

        # Convert known numeric columns to proper numeric types.
        numeric_cols = ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
        for col in numeric_cols:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')

        all_chunks.append(data)

    if not all_chunks:
        print(f"[INFO] No data found for {company_name} ({ticker}) in any defined time chunk.")
        continue

    # Combine all downloaded chunks and sort by time.
    final_df = pd.concat(all_chunks).sort_index()

    # ------------------------------------------------------------------------------
    # 4) PROCESS THE DATAFRAME: Prepare for CSV/DB Storage
    # ------------------------------------------------------------------------------
    # Reset index so that the Datetime becomes a normal column.
    final_df.reset_index(inplace=True)
    if 'index' in final_df.columns:
        final_df.rename(columns={'index': 'Datetime'}, inplace=True)

    # Rename "Adj Close" to "Adj_Close" and fill null values with the "Close" value.
    if 'Adj Close' in final_df.columns:
        final_df.rename(columns={'Adj Close': 'Adj_Close'}, inplace=True)
    if 'Adj_Close' in final_df.columns:
        final_df['Adj_Close'] = final_df['Adj_Close'].fillna(final_df['Close'])

    # Create a "Timestamp" column from the Datetime (in epoch seconds).
    final_df['Timestamp'] = final_df['Datetime'].astype('int64') // 10**9

    # Add metadata columns for Company and StockTicker.
    final_df['Company'] = company_name
    final_df['StockTicker'] = ticker

    # Create a unique "StockHoldID" by combining StockTicker and Timestamp.
    final_df['StockHoldID'] = final_df['StockTicker'] + '_' + final_df['Timestamp'].astype(str)

    # Reorder columns as desired.
    desired_order = [
        'StockHoldID',
        'Timestamp',
        'Adj_Close',
        'Close',
        'High',
        'Low',
        'Open',
        'Volume',
        'Company',
        'StockTicker'
    ]
    existing_cols = [col for col in desired_order if col in final_df.columns]
    final_df = final_df[existing_cols]

    # ------------------------------------------------------------------------------
    # 5) (OPTIONAL) SAVE THE FINAL DATAFRAME TO A CSV FILE
    # ------------------------------------------------------------------------------
    # csv_path = f"C:\\Users\\Edkee\\Documents\\4th\\Project\\research\\stockmarket\\models\\{ticker}_data.csv"
    # final_df.to_csv(csv_path, index=False, float_format='%.6f', quoting=csv.QUOTE_NONE, escapechar=' ')
    # print(f"[CSV] Data for {company_name} ({ticker}) saved to: {csv_path}")

    # ------------------------------------------------------------------------------
    # 6) INSERT DATA INTO THE POSTGRESQL DATABASE
    # ------------------------------------------------------------------------------
    try:
        with engine.connect() as conn:
            final_df.to_sql(
                'monthlyStock',
                con=conn,
                schema='stock_market',
                if_exists='append',
                index=False
            )
        print(f"[DB] Data for {company_name} ({ticker}) appended to stock_market.monthlyStock")
    except SQLAlchemyError as e:
        print(f"[DB ERROR] Could not insert data for {company_name} ({ticker}): {e}")
