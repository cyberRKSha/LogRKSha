from flask import Flask, render_template, request, redirect
import csv
import os

app = Flask(__name__)

PENDING_FILE = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/review.csv"
REAL_FILE = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/real_log.csv"

@app.route('/')
def index():
    entries = []
    if os.path.exists(PENDING_FILE):
        with open(PENDING_FILE, newline='', encoding='utf-8') as f:
            reader = list(csv.reader(f))
            header, data = reader[0], reader[1:]
            entries = [dict(timestamp=row[0], source=row[1], content=row[2], label=row[3], index=idx)
                       for idx, row in enumerate(data)]
    return render_template('review.html', entries=entries)

@app.route('/update', methods=['POST'])
def update():
    updated_labels = request.form
    with open(PENDING_FILE, newline='', encoding='utf-8') as f:
        reader = list(csv.reader(f))
        header, data = reader[0], reader[1:]

    reviewed = []
    for idx, row in enumerate(data):
        new_label = updated_labels.get(f'label_{idx}')
        if new_label in ['0', '1']:
            row[3] = new_label
        reviewed.append(row)

    # Append reviewed to real_log.csv
    write_mode = 'a' if os.path.exists(REAL_FILE) else 'w'
    with open(REAL_FILE, mode=write_mode, newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if write_mode == 'w':
            writer.writerow(header)
        writer.writerows(reviewed)

    # Clear pending review.csv (keep header)
    with open(PENDING_FILE, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)

    return redirect('/')

if __name__ == "__main__":
    app.run(debug=True, port=5000)
