# from flask import Flask, render_template, request, redirect, url_for
# import pandas as pd
# import os

# # Define the app and the static folder path
# app = Flask(__name__, static_folder='static', static_url_path='/static')

# PENDING_FILE = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/review.csv"
# REAL_FILE = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/real_log.csv"

# # This function will be used to clean labels in both display and saving logic
# def map_labels_to_numeric(df):
#     """Converts string labels ('anomaly', 'normal') to numeric (1, 0)"""
#     def map_val(label):
#         if isinstance(label, str):
#             if 'anomaly' in label.lower(): return 1
#             if 'normal' in label.lower(): return 0
#         if pd.to_numeric(label, errors='coerce') in [0, 1]:
#             return int(label)
#         return 0 # Default for any other case
    
#     # Apply the mapping function safely
#     if 'label' in df.columns:
#         df['label'] = df['label'].apply(map_val)
#     return df

# @app.route('/')
# def index():
#     sort_by = request.args.get('sort_by')
#     entries = []
    
#     if os.path.exists(PENDING_FILE) and os.path.getsize(PENDING_FILE) > 0:
#         try:
#             df = pd.read_csv(PENDING_FILE)
#             df.dropna(subset=['content'], inplace=True)

#             # Use the helper function to clean labels for display
#             df = map_labels_to_numeric(df)

#             if sort_by == '1':
#                 df = df.sort_values(by='label', ascending=False)
#             elif sort_by == '0':
#                 df = df.sort_values(by='label', ascending=True)

#             df['index'] = df.index
#             entries = df.to_dict('records')

#         except Exception as e:
#             print(f"Error in index function: {e}")

#     return render_template('review.html', entries=entries, sort_by=sort_by)

# @app.route('/update', methods=['POST'])
# def update():
#     if not os.path.exists(PENDING_FILE) or os.path.getsize(PENDING_FILE) == 0:
#         return redirect(url_for('index'))

#     try:
#         df_pending = pd.read_csv(PENDING_FILE)
#         if df_pending.empty:
#             return redirect(url_for('index'))

#         df_pending = map_labels_to_numeric(df_pending)

#         updated_labels = request.form
#         for key, new_label in updated_labels.items():
#             if key.startswith('label_'):
#                 idx = int(key.split('_')[1])
#                 df_pending.loc[idx, 'label'] = int(new_label)
#         # === END: CRITICAL FIX ===

#         # Append the fully numeric DataFrame to the real log file.
#         header = not os.path.exists(REAL_FILE)
#         df_pending.to_csv(REAL_FILE, mode='a', header=header, index=False)

#         # Clear the review file
#         with open(PENDING_FILE, mode='w', newline='', encoding='utf-8') as f:
#             f.write('timestamp,source,content,label\n')

#     except Exception as e:
#         print(f"Error in update function: {e}")

#     return redirect(url_for('index'))

# if __name__ == "__main__":
#     app.run(debug=True, port=5000)














# review.py
from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os

# --- Configuration ---
DATABASE_FILE = "log_database.db"
# The static folder path is configured directly in the Flask app constructor
app = Flask(__name__, static_folder='static', static_url_path='/static')


def get_db_connection():
    """Establishes a connection to the database."""
    conn = sqlite3.connect(DATABASE_FILE)
    # This allows accessing columns by name (like a dictionary)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    """
    Displays logs that are pending review.
    """
    sort_by = request.args.get('sort_by')
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM logs WHERE is_reviewed = 0"
    if sort_by == '1': # Sort by anomaly
        query += " ORDER BY final_label DESC, timestamp DESC"
    elif sort_by == '0': # Sort by normal
        query += " ORDER BY final_label ASC, timestamp DESC"
    else:
        query += " ORDER BY timestamp DESC"

    cursor.execute(query)
    entries = cursor.fetchall()
    conn.close()

    return render_template('review.html', entries=entries, sort_by=sort_by)

@app.route('/update', methods=['POST'])
def update():
    """
    Updates logs based on user review and marks them as reviewed.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Loop through the submitted form data which contains the corrected labels
    for key, new_label in request.form.items():
        if key.startswith('label_'):
            # Extract the unique log ID from the form field name
            log_id = int(key.split('_')[1])

            # Update the database: set the final label and mark as reviewed (is_reviewed = 1)
            cursor.execute("""
                UPDATE logs
                SET final_label = ?, is_reviewed = 1
                WHERE id = ?
            """, (int(new_label), log_id))

    conn.commit()
    conn.close()
    print(f"✅ Successfully reviewed and updated logs in the database.")
    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(debug=True, port=5000)