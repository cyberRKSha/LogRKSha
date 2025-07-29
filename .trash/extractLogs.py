# # scripts/extract_logs.py
# import pandas as pd
# import argparse
# import os
# import re

# def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
# def log_success(msg): print(f"\033[92m✅ {msg}\033[0m")
# def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")

# def extract_from_csv(input_file, output_file):
#     try:
#         df = pd.read_csv(input_file)
#         # Find likely timestamp + message columns
#         possible_timestamp = [col for col in df.columns if 'time' in col.lower() or 'date' in col.lower()]
#         possible_content = [col for col in df.columns if 'content' in col.lower() or 'message' in col.lower() or 'log' in col.lower()]

#         timestamp_col = possible_timestamp[0] if possible_timestamp else None
#         content_col = possible_content[0] if possible_content else None

#         if timestamp_col and content_col:
#             clean_df = df[[timestamp_col, content_col]].rename(columns={timestamp_col: 'timestamp', content_col: 'content'})
#         else:
#             # fallback: just use first column as content
#             clean_df = pd.DataFrame({'timestamp': pd.Timestamp.now(), 'content': df.iloc[:,0].astype(str)})

#         clean_df.dropna(subset=['content'], inplace=True)
#         clean_df.to_csv(output_file, index=False)
#         log_success(f"Extracted logs saved to: {output_file}")
#     except Exception as e:
#         log_error(f"Failed to extract: {e}")

# def extract_from_txt(input_file, output_file):
#     try:
#         lines = []
#         with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
#             for line in f:
#                 line = line.strip()
#                 if line:
#                     # Extract timestamp if matches like YYYY-MM-DD or similar
#                     match = re.match(r'^(\d{4}-\d{2}-\d{2}.*?)\s+(.*)$', line)
#                     if match:
#                         timestamp, content = match.groups()
#                     else:
#                         timestamp, content = pd.Timestamp.now(), line
#                     lines.append({'timestamp': timestamp, 'content': content})

#         df = pd.DataFrame(lines)
#         df.to_csv(output_file, index=False)
#         log_success(f"Extracted logs saved to: {output_file}")
#     except Exception as e:
#         log_error(f"Failed to extract: {e}")

# def main():
#     parser = argparse.ArgumentParser(description="Extract logs from CSV or text file to clean CSV.")
#     parser.add_argument("input_file", help="Path to log file (csv or txt)")
#     args = parser.parse_args()

#     input_file = args.input_file
#     base, ext = os.path.splitext(input_file)
#     output_file = f"{base}Extracted.csv"

#     if not os.path.exists(input_file):
#         log_error("File not found.")
#         return

#     if ext.lower() == '.csv':
#         extract_from_csv(input_file, output_file)
#     else:
#         extract_from_txt(input_file, output_file)

# if __name__ == "__main__":
#     main()

# scripts/extract_logs.py
import pandas as pd
import argparse
import os
import re

def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
def log_success(msg): print(f"\033[92m✅ {msg}\033[0m")
def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")

def extract_from_csv(input_file, output_file):
    try:
        df = pd.read_csv(input_file)
        possible_timestamp = [col for col in df.columns if 'time' in col.lower() or 'date' in col.lower()]
        possible_content = [col for col in df.columns if 'content' in col.lower() or 'message' in col.lower() or 'log' in col.lower()]

        timestamp_col = possible_timestamp[0] if possible_timestamp else None
        content_col = possible_content[0] if possible_content else None

        if timestamp_col and content_col:
            clean_df = df[[timestamp_col, content_col]].rename(columns={timestamp_col: 'timestamp', content_col: 'content'})
        else:
            clean_df = pd.DataFrame({'timestamp': pd.Timestamp.now(), 'content': df.iloc[:,0].astype(str)})

        clean_df['source'] = 'file'
        clean_df = clean_df[['timestamp', 'source', 'content']]  # only 3 columns

        clean_df.dropna(subset=['content'], inplace=True)
        clean_df.to_csv(output_file, index=False)
        log_success(f"Extracted logs saved to: {output_file}")
    except Exception as e:
        log_error(f"Failed to extract: {e}")

def extract_from_txt(input_file, output_file):
    try:
        lines = []
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if line:
                    match = re.match(r'^(\d{4}-\d{2}-\d{2}.*?)\s+(.*)$', line)
                    if match:
                        timestamp, content = match.groups()
                    else:
                        timestamp, content = pd.Timestamp.now(), line
                    lines.append({'timestamp': timestamp, 'source': 'file', 'content': content})

        df = pd.DataFrame(lines)
        df.to_csv(output_file, index=False)
        log_success(f"Extracted logs saved to: {output_file}")
    except Exception as e:
        log_error(f"Failed to extract: {e}")

def main():
    parser = argparse.ArgumentParser(description="Extract logs from CSV or text file to clean CSV.")
    parser.add_argument("input_file", help="Path to log file (csv or txt)")
    args = parser.parse_args()

    input_file = args.input_file
    base, ext = os.path.splitext(input_file)
    output_file = f"{base}_extracted.csv"

    if not os.path.exists(input_file):
        log_error("File not found.")
        return

    if ext.lower() == '.csv':
        extract_from_csv(input_file, output_file)
    else:
        extract_from_txt(input_file, output_file)

if __name__ == "__main__":
    main()
