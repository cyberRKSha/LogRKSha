import csv
import os

# === Config paths ===
PENDING_FILE = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/review.csv"
REAL_FILE = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/real_log.csv"

# === Load rows from CSV ===
def load_csv(filepath):
    with open(filepath, mode='r', encoding='utf-8') as f:
        reader = list(csv.reader(f))
    return reader

# === Save rows to CSV (overwrite) ===
def save_csv(filepath, rows):
    with open(filepath, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(rows)

# === Review new entries interactively ===
def review_entries(entries):
    """
    entries: list of rows including header
    """
    header, data = entries[0], entries[1:]
    print(f"📝 Found {len(data)} new log entries to review.\n")

    reviewed = []
    for idx, row in enumerate(data, start=1):
        timestamp, source, content, label = row
        print(f"\n[{idx}] Timestamp: {timestamp}")
        print(f"Source: {source}")
        print(f"Content: {content}")
        print(f"Current label: {label} (1=anomaly, 0=normal)")

        new_label = input("Enter new label (1/0) or press Enter to keep: ").strip()
        if new_label in ['0', '1']:
            print(f"✔ Updated label to {new_label}")
            label = new_label
        else:
            print("✅ Kept original label")

        reviewed.append([timestamp, source, content, label])

    return [header] + reviewed

# === Append reviewed rows to real_log.csv ===
def append_to_real_log(new_entries):
    """
    new_entries: list of rows including header
    """
    if not os.path.exists(REAL_FILE):
        # Create new file with header + data
        save_csv(REAL_FILE, new_entries)
        print("📦 real_log.csv created.")
    else:
        # Append data only (skip header)
        with open(REAL_FILE, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for row in new_entries[1:]:
                writer.writerow(row)
        print("📦 Added reviewed entries to existing real_log.csv.")

# === Main ===
if __name__ == "__main__":
    # Check if review.csv exists
    if not os.path.exists(PENDING_FILE):
        print("❗ review.csv not found. Nothing to merge.")
        exit(1)

    # Load entries from review.csv
    entries = load_csv(PENDING_FILE)

    if len(entries) <= 1:
        print("✅ No new entries to review. review.csv is empty.")
        exit(0)

    # Review interactively
    reviewed_entries = review_entries(entries)

    # Append to real_log.csv
    append_to_real_log(reviewed_entries)

    # Clear review.csv but keep header
    save_csv(PENDING_FILE, [entries[0]])
    print("🧹 Cleared review.csv after merge. Done!")
