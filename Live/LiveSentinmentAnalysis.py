import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sqlalchemy import create_engine, Table, Column, Integer, String, Float, MetaData, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.postgresql import insert

# 1) Database configuration
DATABASE_URL = "postgresql://postgres:root@localhost:5432/my_database"

# 2) Set up SQLAlchemy engine and session
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

# 3) Define table metadata
metadata = MetaData()

# 4) Reflect the input table 'Livearticles'
livearticles = Table(
    'Livearticles',
    metadata,
    autoload_with=engine,
    schema='public'
)

# 5) Define the output table 'LiveSentimental'
live_sentimental = Table(
    'LiveSentimental',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('timestamp', String),
    Column('company', String),
    Column('newssite', String),
    Column('positive', Float),
    Column('neutral', Float),
    Column('negative', Float)
)

# 6) Create the 'LiveSentimental' table if it doesn’t exist
metadata.create_all(engine)

# 7) Load the tokenizer and model (using your local Prosus model)
model_path = r"C:\Users\Edkee\Documents\4th\1 semester\Project\ProsusA"
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForSequenceClassification.from_pretrained(model_path)

# 8) Fetch all rows from 'Livearticles'
try:
    query = select(livearticles)
    results = session.execute(query).mappings().all()
    print(f"Fetched {len(results)} rows from Livearticles.")
except SQLAlchemyError as e:
    print(f"Error fetching data from Livearticles: {e}")
    session.close()
    exit()

sentiment_results = []

# 9) Perform sentiment analysis for each row in 'Livearticles'
for row in results:
    row_id = row['id']
    timestamp = row['timestamp']  # assuming timestamp is stored as string
    company = row['company']
    newssite = row['newssite']
    content = row['fullarticle']  # full article text

    if not content:
        continue

    print(f"Analyzing row_id={row_id} for company {company}...")

    # Tokenize and run the model (truncating long texts to max_length=512 tokens)
    inputs = tokenizer(content, return_tensors="pt", truncation=True, max_length=512)
    outputs = model(**inputs)
    logits = outputs.logits

    # Calculate probabilities using softmax
    probabilities = F.softmax(logits, dim=1).detach().numpy().flatten()

    # Assume the model outputs probabilities in the order: [positive, neutral, negative]
    positive_prob = float(probabilities[0])
    neutral_prob = float(probabilities[1])
    negative_prob = float(probabilities[2])

    print(f"  Positive={positive_prob:.4f}, Neutral={neutral_prob:.4f}, Negative={negative_prob:.4f}")

    # Prepare data to insert into LiveSentimental
    sentiment_results.append({
        'id': row_id,
        'timestamp': timestamp,
        'company': company,
        'newssite': newssite,
        'positive': positive_prob,
        'neutral': neutral_prob,
        'negative': negative_prob
    })

# 10) Insert sentiment results into the LiveSentimental table using upsert logic
try:
    insert_stmt = insert(live_sentimental).values(sentiment_results)
    update_dict = {
        'timestamp': insert_stmt.excluded.timestamp,
        'company': insert_stmt.excluded.company,
        'newssite': insert_stmt.excluded.newssite,
        'positive': insert_stmt.excluded.positive,
        'neutral': insert_stmt.excluded.neutral,
        'negative': insert_stmt.excluded.negative
    }
    insert_stmt = insert_stmt.on_conflict_do_update(
        index_elements=['id'],
        set_=update_dict
    )
    session.execute(insert_stmt)
    session.commit()
    print("Sentiment data successfully saved to PostgreSQL (LiveSentimental table).")
except SQLAlchemyError as e:
    print(f"Error inserting sentiment data: {e}")
    session.rollback()

# 11) Close the session
session.close()
