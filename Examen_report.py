# exam_report_web.py
from flask import Flask, render_template_string
from datetime import datetime, timedelta
import os

LOG_FILE = "student_log.txt"
MAX_OFFLINE_SECONDS = 30
EXAM_DURATION_HOURS = 4

app = Flask(__name__)

@app.route('/report')
def report():
    if not os.path.exists(LOG_FILE):
        return "<h1>Geen logbestand gevonden!</h1>"

    # Lees logbestand
    with open(LOG_FILE, "r") as f:
        lines = f.readlines()

    # Groepeer per student
    students_entries = {}
    for line in lines:
        parts = line.strip().split(" - ")
        if len(parts) != 3:
            continue
        ts_str, name, status = parts
        ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        if name not in students_entries:
            students_entries[name] = []
        students_entries[name].append({"time": ts, "status": status})

    # Verwerk entries
    report_data = {}
    offline_summary = {}
    exam_start = min(min(e["time"] for e in entries) for entries in students_entries.values())
    exam_end = exam_start + timedelta(hours=EXAM_DURATION_HOURS)
    total_seconds = EXAM_DURATION_HOURS * 3600

    for name, entries in students_entries.items():
        merged = []
        last_entry = None
        offline_summary[name] = []
        for e in entries:
            if not last_entry:
                last_entry = {"time": e["time"], "status": e["status"]}
            else:
                if e["status"] == last_entry["status"]:
                    last_entry["time_end"] = e["time"]
                else:
                    if last_entry["status"] == "OFFLINE":
                        duration = (last_entry.get("time_end", last_entry["time"]) - last_entry["time"]).total_seconds()
                        if duration >= MAX_OFFLINE_SECONDS:
                            merged.append(last_entry)
                            offline_summary[name].append(last_entry)
                    else:
                        merged.append(last_entry)
                    last_entry = {"time": e["time"], "status": e["status"]}
        if last_entry:
            if last_entry["status"] == "OFFLINE":
                duration = (last_entry.get("time_end", last_entry["time"]) - last_entry["time"]).total_seconds()
                if duration >= MAX_OFFLINE_SECONDS:
                    merged.append(last_entry)
                    offline_summary[name].append(last_entry)
            else:
                merged.append(last_entry)
        report_data[name] = merged

    # HTML genereren
    html = """
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <title>Exam Report</title>
    <style>
    body { font-family: Arial; margin: 40px; }
    h2 { margin-top: 50px; }
    .timeline { display: flex; height: 20px; margin-bottom: 5px; border: 1px solid #ccc; }
    .online { background-color: green; }
    .offline { background-color: red; }
    .offline-table { margin-bottom: 40px; }
    table { border-collapse: collapse; width: 60%; }
    th, td { border: 1px solid #ccc; padding: 5px; text-align: center; }
    th { background-color: #f0f0f0; }
    </style>
    </head>
    <body>
    <h1>Exam Report</h1>
    """

    for name, events in report_data.items():
        html += f"<h2>{name}</h2>\n"
        html += '<div class="timeline">'
        for e in events:
            start_sec = max(0, (e["time"] - exam_start).total_seconds())
            end_sec = min(total_seconds, (e.get("time_end", e["time"]) - exam_start).total_seconds())
            width_percent = (end_sec - start_sec) / total_seconds * 100
            cls = "online" if e["status"]=="ONLINE" else "offline"
            html += f'<div class="{cls}" style="width:{width_percent}%"></div>'
        html += "</div>"

        # Tabel offline periodes ≥30 sec
        html += '<div class="offline-table">'
        html += "<table><tr><th>Offline start</th><th>Offline einde</th></tr>"
        for e in offline_summary[name]:
            start = e["time"].strftime("%H:%M:%S")
            end = e.get("time_end", e["time"]).strftime("%H:%M:%S")
            html += f"<tr><td>{start}</td><td>{end}</td></tr>"
        html += "</table></div>"

    html += "</body></html>"

    return html

if __name__ == "__main__":
    print("Server gestart op http://0.0.0.0:8001/report")
    app.run(host='0.0.0.0', port=8001, debug=True)
