"""
Ticket category classifier: TF-IDF + Logistic Regression.

Interview points:
- Why TF-IDF + LogReg as baseline? Fast, interpretable, trains in seconds,
  and gives a benchmark to compare a transformer against.
- Upgrade path: fine-tune DistilBERT and compare F1 scores. Being able to
  say "baseline F1 was X, transformer improved it to Y at Z ms latency
  cost" is a strong interview answer.
- Sentiment here is a simple keyword approach; upgrade to a pretrained
  transformer sentiment model later (see comments at bottom).
"""

import os
import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

MODEL_PATH = os.path.join(os.path.dirname(__file__), "classifier.joblib")

NEGATIVE_WORDS = {"crash", "crashes", "error", "failed", "broken", "slow",
                  "not", "cannot", "expired", "locked", "duplicate", "wrong",
                  "hurts", "invalid"}
POSITIVE_WORDS = {"great", "love", "thanks", "good", "please", "works"}


def train(csv_path):
    """Train on a CSV with columns: subject, body, category."""
    df = pd.read_csv(csv_path)
    texts = (df["subject"] + " " + df["body"]).tolist()
    labels = df["category"].tolist()

    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )

    model = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), stop_words="english")),
        ("clf", LogisticRegression(max_iter=1000)),
    ])
    model.fit(X_train, y_train)

    print(classification_report(y_test, model.predict(X_test)))
    joblib.dump(model, MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")
    return model


def load_model():
    return joblib.load(MODEL_PATH)


def predict_category(model, subject, body):
    text = subject + " " + body
    return model.predict([text])[0]


def predict_sentiment(subject, body):
    """
    Very simple keyword sentiment. Honest interview line:
    "I started with a keyword baseline, then swapped in a pretrained
    DistilBERT sentiment model from HuggingFace for better accuracy."

    Upgrade (2 lines with transformers library):
        from transformers import pipeline
        sentiment = pipeline("sentiment-analysis")   # distilbert based
    """
    words = set((subject + " " + body).lower().split())
    neg = len(words & NEGATIVE_WORDS)
    pos = len(words & POSITIVE_WORDS)
    if neg > pos:
        return "negative"
    if pos > neg:
        return "positive"
    return "neutral"


if __name__ == "__main__":
    train(os.path.join(os.path.dirname(__file__), "..", "..", "data",
                       "sample_tickets.csv"))
