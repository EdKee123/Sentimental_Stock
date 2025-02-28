import psycopg2
import pandas as pd
import numpy as np
import datetime
from datetime import timedelta, timezone
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

##################################################
# 1. Database connection and data retrieval
##################################################
DATABASE_URL = "postgresql://postgres:root@localhost:5432/my_database"

SQL_LIVE_SENTIMENT = """
SELECT
    id,
    "timestamp",
    company,
    newssite,
    positive,
    neutral,
    negative
FROM public."LiveSentimental"
ORDER BY id ASC;
"""

SQL_STOCK = """
SELECT *
FROM stock_market."monthlyStock";
"""

def get_data_from_db():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        df_live_sentiment = pd.read_sql(SQL_LIVE_SENTIMENT, conn)
        df_stock = pd.read_sql(SQL_STOCK, conn)
    finally:
        conn.close()
    return df_live_sentiment, df_stock

df_sentiment, df_stock = get_data_from_db()

##################################################
# 2. Basic data cleaning and type adjustments
##################################################
df_sentiment['article_datetime'] = pd.to_datetime(df_sentiment['timestamp'], unit='s', utc=True)
df_stock['stock_datetime'] = pd.to_datetime(df_stock['Timestamp'], unit='s', utc=True)

df_sentiment.dropna(subset=['company','positive','negative','neutral','article_datetime'], inplace=True)
df_stock.dropna(subset=['Company','Close','stock_datetime'], inplace=True)

##################################################
# 2a. Weekend Handling for article times
##################################################
def shift_to_friday_if_weekend(dt: pd.Timestamp) -> pd.Timestamp:
    if dt.weekday() == 5:
        return dt - pd.Timedelta(days=1)
    elif dt.weekday() == 6:
        return dt - pd.Timedelta(days=2)
    else:
        return dt

df_sentiment['article_datetime'] = df_sentiment['article_datetime'].apply(shift_to_friday_if_weekend)

##################################################
# 3. Feature Engineering & Labeling
##################################################
def get_avg_price_in_window(stock_data, center_time, window, baseline=False):
    if baseline:
        start_time = center_time - window
        end_time = center_time
    else:
        start_time = center_time - window
        end_time = center_time + window

    mask = (stock_data['stock_datetime'] >= start_time) & (stock_data['stock_datetime'] <= end_time)
    window_data = stock_data.loc[mask, 'Close']
    if len(window_data) == 0:
        return np.nan

    mean_ = window_data.mean()
    std_ = window_data.std()
    cutoff = 3 * std_
    window_data = window_data[(window_data >= mean_ - cutoff) & (window_data <= mean_ + cutoff)]
    if len(window_data) == 0:
        return np.nan
    return window_data.mean()

STRONG_SENT_THRESHOLD = 0.75
BASELINE_WINDOW = pd.Timedelta(days=7)
EVENT_HALF_WINDOW = pd.Timedelta(hours=36)

df_sentiment.sort_values(by=['company','article_datetime'], inplace=True)
df_stock.sort_values(by=['Company','stock_datetime'], inplace=True)

stock_groups = dict(tuple(df_stock.groupby('Company')))

feature_rows = []
for company, df_company_sent in df_sentiment.groupby('company'):
    if company not in stock_groups:
        continue
    stock_data_for_company = stock_groups[company]
    for idx, row in df_company_sent.iterrows():
        article_time = row['article_datetime']
        baseline_avg = get_avg_price_in_window(stock_data_for_company, article_time, BASELINE_WINDOW, baseline=True)
        event_avg = get_avg_price_in_window(stock_data_for_company, article_time, EVENT_HALF_WINDOW, baseline=False)
        if pd.isna(baseline_avg) or pd.isna(event_avg):
            continue
        change_ratio = (event_avg - baseline_avg) / baseline_avg
        if change_ratio > 0.01:
            label = 'Up'
        elif change_ratio < -0.01:
            label = 'Down'
        else:
            label = 'Same'
        strong_pos = 1 if row['positive'] > STRONG_SENT_THRESHOLD else 0
        strong_neg = 1 if row['negative'] > STRONG_SENT_THRESHOLD else 0
        start_window = article_time - EVENT_HALF_WINDOW
        end_window = article_time + EVENT_HALF_WINDOW
        mask_72h = (df_company_sent['article_datetime'] >= start_window) & (df_company_sent['article_datetime'] <= end_window)
        time_window_articles = df_company_sent.loc[mask_72h]
        sp_count = (time_window_articles['positive'] > STRONG_SENT_THRESHOLD).sum()
        sn_count = (time_window_articles['negative'] > STRONG_SENT_THRESHOLD).sum()
        feature_rows.append({
            'company': company,
            'article_time': article_time,
            'newssite': row['newssite'],
            'positive': row['positive'],
            'neutral': row['neutral'],
            'negative': row['negative'],
            'strong_positive': strong_pos,
            'strong_negative': strong_neg,
            'strong_positive_count_72h': sp_count,
            'strong_negative_count_72h': sn_count,
            'baseline_avg_price': baseline_avg,
            'event_avg_price': event_avg,
            'change_ratio': change_ratio,
            'label': label
        })

df_features = pd.DataFrame(feature_rows)
if df_features.empty:
    print("No feature rows were generated. Exiting.")
    exit()
else:
    df_features.dropna(subset=['label','positive','negative','neutral'], inplace=True)

label_map = {'Down': 0, 'Same': 1, 'Up': 2}
df_features['label_encoded'] = df_features['label'].map(label_map)

##################################################
# 4. Model Training
##################################################
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier

feature_cols = [
    'positive',
    'neutral',
    'negative',
    'strong_positive',
    'strong_negative',
    'strong_positive_count_72h',
    'strong_negative_count_72h'
]
X = df_features[feature_cols].values
y = df_features['label_encoded'].values

all_indices = np.arange(len(X))
X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
    X, y, all_indices, test_size=0.2, random_state=42, stratify=y
)

model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)
y_pred = model.predict(X_test)

##################################################
# 5. Evaluate & Print Predictions
##################################################
from sklearn.metrics import classification_report, accuracy_score

print("Overall Accuracy:", accuracy_score(y_test, y_pred))
print("Classification Report:")
print(classification_report(y_test, y_pred, labels=[0,1,2], target_names=['Down','Same','Up'], zero_division=0))

df_test = df_features.iloc[idx_test].copy()
df_test['y_true'] = y_test
df_test['y_pred'] = y_pred

y_pred_probs = model.predict_proba(X_test)
if y_pred_probs.shape[1] < 3:
    new_probs = np.zeros((y_pred_probs.shape[0], 3))
    for c_idx, c_label in enumerate(model.classes_):
        new_probs[:, int(c_label)] = y_pred_probs[:, c_idx]
    y_pred_probs = new_probs

inv_label_map = {0: 'Down', 1: 'Same', 2: 'Up'}

print("\n--- Detailed Predictions on the Test Set ---")
for i, row_index in enumerate(idx_test):
    row_data = df_test.loc[row_index]
    company_name = row_data['company']
    newssite = row_data['newssite']
    prob_down = y_pred_probs[i, 0]
    prob_same = y_pred_probs[i, 1]
    prob_up   = y_pred_probs[i, 2]
    print("-----------------------------------")
    print(f"Company Name: {company_name}")
    print(f"Newssite    : {newssite}")
    print("Probability:")
    print(f"  Rising  : {prob_up:.3f}")
    print(f"  Staying : {prob_same:.3f}")
    print(f"  Falling : {prob_down:.3f}")

##################################################
# 6. Insert Final Predictions into FinalPredictions Table
##################################################
def insert_final_predictions():
    insert_data = []
    for i, row_index in enumerate(idx_test):
        row_data = df_test.loc[row_index]
        company_name = row_data['company']
        newssite = row_data['newssite']
        p_down = float(y_pred_probs[i, 0])
        p_same = float(y_pred_probs[i, 1])
        p_up   = float(y_pred_probs[i, 2])
        pred_label = inv_label_map[np.argmax([p_down, p_same, p_up])]
        insert_data.append((company_name, newssite, pred_label, p_down, p_same, p_up))
    
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            insert_sql = """
            INSERT INTO public."FinalPredictions" (company, newssite, predicted_label, prob_down, prob_same, prob_up)
            VALUES (%s, %s, %s, %s, %s, %s);
            """
            cur.executemany(insert_sql, insert_data)
        conn.commit()
        print("Final predictions inserted into public.FinalPredictions.")
    except Exception as e:
        conn.rollback()
        print("Error inserting final predictions:", e)
    finally:
        conn.close()

insert_final_predictions()

print("\nDone with LiveMachineLearningPrediction.py.")
