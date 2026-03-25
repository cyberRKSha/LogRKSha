#!/usr/bin/env python3
"""
experiments/evaluate.py

Unified Evaluation Script for Research Baselines.
Computes: Accuracy, Precision, Recall, F1-Score, Confusion Matrix.

Reads predictions from:
    - results/deeplog_predictions.csv
    - results/logbert_predictions.csv
"""

import os
import pandas as pd
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report
)

# --- Configuration ---
RESULTS_DIR = "results"
DEEPLOG_RESULTS = os.path.join(RESULTS_DIR, "deeplog_predictions.csv")
LOGBERT_RESULTS = os.path.join(RESULTS_DIR, "logbert_predictions.csv")
OUTPUT_SUMMARY = os.path.join(RESULTS_DIR, "evaluation_summary.csv")


def evaluate_model(name: str, predictions_file: str):
    """
    Evaluate a model's predictions and return metrics dictionary.
    """
    if not os.path.exists(predictions_file):
        print(f"⚠️  {name}: Predictions file not found ({predictions_file})")
        return None
    
    df = pd.read_csv(predictions_file)
    
    y_true = df["true_label"].values
    y_pred = df["predicted_label"].values
    
    # Compute metrics
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    cm = confusion_matrix(y_true, y_pred)
    
    # Compute Recall@K (if anomaly_ratio or score column exists)
    recall_at_k = {}
    score_col = None
    if "anomaly_ratio" in df.columns:
        score_col = "anomaly_ratio"
    elif "score" in df.columns:
        score_col = "score"
    
    if score_col:
        # Sort by score descending (higher = more suspicious)
        df_sorted = df.sort_values(score_col, ascending=False)
        total_anomalies = y_true.sum()
        
        for k in [10, 50, 100, 500]:
            if k <= len(df_sorted):
                top_k = df_sorted.head(k)
                caught = (top_k["true_label"] == 1).sum()
                recall_at_k[f"R@{k}"] = caught / total_anomalies if total_anomalies > 0 else 0
    
    # Print results
    print(f"\n{'='*60}")
    print(f"📊 {name} Evaluation Results")
    print(f"{'='*60}")
    print(f"   Total Sessions: {len(df)}")
    print(f"   True Anomalies: {y_true.sum()}")
    print(f"   Predicted Anomalies: {y_pred.sum()}")
    print(f"\n   Metrics:")
    print(f"   ├── Accuracy:  {acc:.4f}")
    print(f"   ├── Precision: {prec:.4f}")
    print(f"   ├── Recall:    {rec:.4f}")
    print(f"   └── F1-Score:  {f1:.4f}")
    
    if recall_at_k:
        print(f"\n   Recall@K (Top-K Triage):")
        for k, v in recall_at_k.items():
            print(f"   ├── {k}: {v:.4f}")
    
    print(f"\n   Confusion Matrix:")
    print(f"                  Predicted")
    print(f"                  Normal  Anomaly")
    print(f"   Actual Normal   {cm[0][0]:6d}  {cm[0][1]:6d}")
    print(f"   Actual Anomaly  {cm[1][0]:6d}  {cm[1][1]:6d}")
    
    # FP per 1k sessions
    total_normal = (y_true == 0).sum()
    fp = cm[0][1] if len(cm) > 1 else 0
    fp_per_1k = (fp / total_normal * 1000) if total_normal > 0 else 0
    print(f"\n   FP per 1k Normal Sessions: {fp_per_1k:.2f}")
    
    return {
        "model": name,
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "f1_score": f1,
        "fp_per_1k": fp_per_1k,
        **recall_at_k,
        "true_positives": cm[1][1] if len(cm) > 1 else 0,
        "false_positives": cm[0][1] if len(cm) > 1 else 0,
        "true_negatives": cm[0][0],
        "false_negatives": cm[1][0] if len(cm) > 1 else 0
    }


def compare_models(results: list):
    """
    Print side-by-side comparison of models.
    """
    print(f"\n{'='*60}")
    print("📈 Model Comparison Summary")
    print(f"{'='*60}")
    
    # Create comparison table
    df = pd.DataFrame(results)
    
    print("\n   Model         | Acc    | Prec   | Recall | F1")
    print("   " + "-"*55)
    
    for _, row in df.iterrows():
        print(f"   {row['model']:<13} | {row['accuracy']:.4f} | {row['precision']:.4f} | {row['recall']:.4f} | {row['f1_score']:.4f}")
    
    # Save to CSV
    df.to_csv(OUTPUT_SUMMARY, index=False)
    print(f"\n   Summary saved to: {OUTPUT_SUMMARY}")
    
    # Check expected ranges
    print("\n   Expected Ranges (Paper Reported):")
    print("   ├── DeepLog: F1 = 0.93 - 0.96")
    print("   └── LogBERT: F1 = 0.95 - 0.97")
    
    return df


def main():
    print("=" * 60)
    print("Full Model Evaluation (Baselines + SIEM)")
    print("=" * 60)
    
    results = []
    
    # --- BASELINES ---
    print("\n📚 ACADEMIC BASELINES")
    
    # Evaluate DeepLog
    deeplog_metrics = evaluate_model("DeepLog", DEEPLOG_RESULTS)
    if deeplog_metrics:
        results.append(deeplog_metrics)
    
    # Evaluate LogBERT
    logbert_metrics = evaluate_model("LogBERT", LOGBERT_RESULTS)
    if logbert_metrics:
        results.append(logbert_metrics)
    
    # --- SIEM MODELS ---
    print("\n🛡️ SIEM MODELS")
    
    SIEM_MODELS = [
        ("Supervised", os.path.join(RESULTS_DIR, "hdfs_supervised.csv")),
        ("Autoencoder", os.path.join(RESULTS_DIR, "hdfs_autoencoder.csv")),
        ("Sequence", os.path.join(RESULTS_DIR, "hdfs_sequence.csv")),
        ("Hybrid", os.path.join(RESULTS_DIR, "hdfs_hybrid.csv")),
    ]
    
    for name, path in SIEM_MODELS:
        metrics = evaluate_model(name, path)
        if metrics:
            results.append(metrics)
    
    # Compare
    if results:
        compare_models(results)
    else:
        print("\n⚠️  No predictions found. Run baseline and hybrid scripts first.")
    
    print("\n" + "=" * 60)
    print("Evaluation Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
