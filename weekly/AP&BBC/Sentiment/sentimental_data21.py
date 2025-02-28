import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sqlalchemy import create_engine, Table, Column, Integer, String, Float, MetaData
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# 1) Database configuration
DATABASE_URL = "postgresql://postgres:root@localhost:5432/my_database"

# 2) Set up SQLAlchemy engine and session
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

# 3) Define table metadata
metadata = MetaData()

# 4) Define the input table 'scrapedcontent'
#    Make sure the name matches exactly what's in your DB: 'scrapedcontent'
scraped_content = Table(
    'scrapedcontent',
    metadata,
    autoload_with=engine
)

# 5) Define the output table 'sentimental_data'
sentimental_data = Table(
    'sentimental_data',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('timestamp', String),
    Column('company', String),
    Column('newssite', String),
    Column('positive', Float),
    Column('neutral', Float),
    Column('negative', Float),
)

# 6) Create the 'sentimental_data' table if it doesn’t exist
metadata.create_all(engine)

# 7) Load the tokenizer and model (local directory for the Prosus model)
model_path = r"C:\Users\Edkee\Documents\4th\1 semester\Project\ProsusA"
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForSequenceClassification.from_pretrained(model_path)

try:
    # 8) Fetch data from 'scrapedcontent' table
    #    We'll assume columns: id, timestamp, company, newssite, link, fullarticle
    results = session.execute(scraped_content.select()).mappings().all()
except SQLAlchemyError as e:
    print(f"Error fetching data: {e}")
    session.close()
    exit()

sentiment_results = []

# 9) Perform sentiment analysis for each row in 'scrapedcontent'
for row in results:
    row_id = row['id']
    timestamp = row['timestamp']
    company = row['company']
    newssite = row['newssite']
    content = row['fullarticle']  # The article text

    if not content:
        continue

    print(f"Analyzing row_id={row_id}...")  # Progress message

    # Tokenize and run the model
    inputs = tokenizer(content, return_tensors="pt", truncation=True, max_length=512)
    outputs = model(**inputs)
    logits = outputs.logits

    # Calculate probabilities using softmax
    probabilities = F.softmax(logits, dim=1).detach().numpy().flatten()

    # Originally: [positive (0), neutral (1), negative (2)]
    # Based on your experiment, you want to switch neutral and negative:
    # => [positive (0), negative (1), neutral (2)]
    positive_prob = float(probabilities[0])
    negative_prob = float(probabilities[1])  # Switched
    neutral_prob  = float(probabilities[2])  # Switched

    # Print to console for confirmation
    print(f"  Positive={positive_prob:.4f}, Neutral={neutral_prob:.4f}, Negative={negative_prob:.4f}")

    # 10) Prepare data to insert into sentimental_data
    sentiment_results.append({
        'id': row_id,
        'timestamp': timestamp,
        'company': company,
        'newssite': newssite,
        'positive': positive_prob,
        'neutral': neutral_prob,
        'negative': negative_prob
    })

# 11) Insert sentiment results into 'sentimental_data' table
try:
    session.execute(sentimental_data.insert(), sentiment_results)
    session.commit()
    print("Sentiment data successfully saved to PostgreSQL (sentimental_data table).")
except SQLAlchemyError as e:
    print(f"Error inserting sentiment data: {e}")
    session.rollback()

# 12) Close the session
session.close()
