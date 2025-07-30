from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import os

# Define the app and the static folder path
app = Flask(__name__, static_folder='static', static_url_path='/static')

PENDING_FILE = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/review.csv"
REAL_FILE = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/real_log.csv"

# This function will be used to clean labels in both display and saving logic
def map_labels_to_numeric(df):
    """Converts string labels ('anomaly', 'normal') to numeric (1, 0)"""
    def map_val(label):
        if isinstance(label, str):
            if 'anomaly' in label.lower(): return 1
            if 'normal' in label.lower(): return 0
        if pd.to_numeric(label, errors='coerce') in [0, 1]:
            return int(label)
        return 0 # Default for any other case
    
    # Apply the mapping function safely
    if 'label' in df.columns:
        df['label'] = df['label'].apply(map_val)
    return df

@app.route('/')
def index():
    sort_by = request.args.get('sort_by')
    entries = []
    
    if os.path.exists(PENDING_FILE) and os.path.getsize(PENDING_FILE) > 0:
        try:
            df = pd.read_csv(PENDING_FILE)
            df.dropna(subset=['content'], inplace=True)

            # Use the helper function to clean labels for display
            df = map_labels_to_numeric(df)

            if sort_by == '1':
                df = df.sort_values(by='label', ascending=False)
            elif sort_by == '0':
                df = df.sort_values(by='label', ascending=True)

            df['index'] = df.index
            entries = df.to_dict('records')

        except Exception as e:
            print(f"Error in index function: {e}")

    return render_template('review.html', entries=entries, sort_by=sort_by)

@app.route('/update', methods=['POST'])
def update():
    if not os.path.exists(PENDING_FILE) or os.path.getsize(PENDING_FILE) == 0:
        return redirect(url_for('index'))

    try:
        df_pending = pd.read_csv(PENDING_FILE)
        if df_pending.empty:
            return redirect(url_for('index'))

        df_pending = map_labels_to_numeric(df_pending)

        updated_labels = request.form
        for key, new_label in updated_labels.items():
            if key.startswith('label_'):
                idx = int(key.split('_')[1])
                df_pending.loc[idx, 'label'] = int(new_label)
        # === END: CRITICAL FIX ===

        # Append the fully numeric DataFrame to the real log file.
        header = not os.path.exists(REAL_FILE)
        df_pending.to_csv(REAL_FILE, mode='a', header=header, index=False)

        # Clear the review file
        with open(PENDING_FILE, mode='w', newline='', encoding='utf-8') as f:
            f.write('timestamp,source,content,label\n')

    except Exception as e:
        print(f"Error in update function: {e}")

    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(debug=True, port=5000)