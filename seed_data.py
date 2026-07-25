"""Load sample tickets into MySQL with ML predictions. Run once after setup."""
import pandas as pd
from app import db
from app.ml.classifier import load_model, predict_category, predict_sentiment

model = load_model()
df = pd.read_csv("data/sample_tickets.csv")
for _, row in df.iterrows():
    cat = predict_category(model, row["subject"], row["body"])
    sent = predict_sentiment(row["subject"], row["body"])
    db.insert_ticket(row["subject"], row["body"], cat, sent)
print(f"Inserted {len(df)} tickets")
