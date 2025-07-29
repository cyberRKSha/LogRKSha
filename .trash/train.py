# scripts/train_incremental.py
import pandas as pd
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.linear_model import SGDClassifier
import joblib
import os

# Load collected logs
df = pd.read_csv("/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/real_log.csv")

# For first run, label known normal logs as 0
# You should add anomaly samples manually too if you can
df['label'] = 0

# Initialize vectorizer & transform
vectorizer = HashingVectorizer(n_features=2**20)
X = vectorizer.transform(df['content'])
y = df['label']

# Initialize model
model = SGDClassifier(loss='log_loss', max_iter=5)

# partial_fit needs classes upfront
model.partial_fit(X, y, classes=[0,1])

# Save
joblib.dump(model, "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/model/sgd_incremental.pkl")
joblib.dump(vectorizer, "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/model/hashing_vectorizer.pkl")

print("✅ Initial model trained and saved.")
