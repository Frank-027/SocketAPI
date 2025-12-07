# Examen_report.py
from flask import Flask, render_template_string
from datetime import datetime, timedelta
import os

app = Flask(__name__)

LOG_FILE = "student_log.txt"

REPORT_HTML = """
<!doctype html>
<html>
<head>
    <title>Exam Report</title>
    <style>
        body { font-family: Arial; margin: 40px; }
        h2 { text-align: center; }
        .student { margin-bottom: 50px; }
        .timeline { display: flex; height: 30px; border: 1px solid #ccc; width: 80%; margin: auto; }
        .segment { height: 100%; }
        .online { background-color: green; }
        .offline { background-color: red; }
        .label { text-align: center; font-size: 0.9em; margin-top: 5px; }
        table { border-collapse: collapse; width: 60%; margin: 10px auto; }
        th, td { border: 1px solid #ccc; padding: 5px; text-align: center; }
        th { background-color: #f0f0f0; }
    </style>
</head>
<body>
    <h1>Student Online/Offline Report</h1>
    {% for student, segments in report.items() %}
    <div class="student">
        <h2>{{ student }}</h2>

        <!-- Tijdslijn -->
        <div class="timeline">
            {% for seg in segments %}
                <div class="segment {{ seg.status }}" style="flex: {{ seg.duration_ratio }};" title="{{ seg.time }} - {{ seg.status }}"></div>
            {% endfor %}
        </div>

        <!-- Offline tabel -->
        <table>
            <thead>
                <tr><th>Offline start</th><th>Offline einde</th><th>Duur (sec)</th></tr>
            </thead>
            <tbody>
            {% for offline in offline_segments[student] %}
                <tr>
                    <td>{{ offline.start }}</td>
                    <td>{{ offline.end }}</td>
                    <td>{{ offline.duration }}</td>
                </tr>
            {% endfor %}
            </tbody>
        </table>
    </div>
    {% endfor %}
</body>
</html>
"""

@app.route('/report')
def report():
    if not os.path.exists(LOG_FILE):
        return "Geen log beschikbaar"

    # Lees log
    report_data = {}
    with open(LOG_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(" - ")
            if len(parts) != 4:
                continue
            timestamp_str, studentNr, name, status = parts
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            key = f"{studentNr} - {name}"
            if key not in report_data:
                report_data[key] = []
            report_data[key].append({"time": timestamp, "status": status})

    MAX_EXAM_SECONDS = 4 * 60 * 60  # 4 uur
    filtered_report = {}
    offline_segments = {}

    # Sorteer op studentNr
    sorted_keys = sorted(report_data.keys(), key=lambda x: int(x.split(" - ")[0]))

    for key in sorted_keys:
        entries = report_data[key]
        segments = []
        offline_list = []

        last_time = None
        last_status = None

        for entry in entries:
            if last_time:
                duration = (entry['time'] - last_time).total_seconds()

                # Alleen offline segmenten toevoegen als duur >= 30 sec
                if last_status == 'OFFLINE' and duration >= 30:
                    segments.append({
                        "status": 'offline',
                        "time": last_time.strftime("%H:%M:%S"),
                        "duration_ratio": duration / MAX_EXAM_SECONDS
                    })
                    offline_list.append({
                        "start": last_time.strftime("%H:%M:%S"),
                        "end": entry['time'].strftime("%H:%M:%S"),
                        "duration": int(duration)
                    })
                elif last_status == 'ONLINE':
                    segments.append({
                        "status": 'online',
                        "time": last_time.strftime("%H:%M:%S"),
                        "duration_ratio": duration / MAX_EXAM_SECONDS
                    })

            last_time = entry['time']
            last_status = entry['status']

        # Laatste segment (afhankelijk van status)
        if last_time:
            # Bereken resterende tijd tot max examen
            duration = MAX_EXAM_SECONDS - (entries[0]['time'] - last_time).total_seconds()
            if last_status == 'OFFLINE' and duration >= 30:
                segments.append({
                    "status": 'offline',
                    "time": last_time.strftime("%H:%M:%S"),
                    "duration_ratio": duration / MAX_EXAM_SECONDS
                })
                offline_list.append({
                    "start": last_time.strftime("%H:%M:%S"),
                    "end": (last_time + timedelta(seconds=duration)).strftime("%H:%M:%S"),
                    "duration": int(duration)
                })
            elif last_status == 'ONLINE':
                segments.append({
                    "status": 'online',
                    "time": last_time.strftime("%H:%M:%S"),
                    "duration_ratio": duration / MAX_EXAM_SECONDS
                })

        filtered_report[key] = segments
        offline_segments[key] = offline_list

    return render_template_string(REPORT_HTML, report=filtered_report, offline_segments=offline_segments)

if __name__ == "__main__":
    print("[STARTING] Examen report server op http://0.0.0.0:8001")
    app.run(host='0.0.0.0', port=8001, debug=True)

