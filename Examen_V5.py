# Examen_server_dashboard_web.py (volledige versie)
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit, disconnect
from datetime import datetime, timedelta
import threading, time, os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

# ---------- Config ----------
PING_INTERVAL = 1        # sec, check vaker
TIMEOUT_SECONDS = 5      # sec, sneller offline
students = {}            # student_name -> last_pong timestamp
status_cache = {}        # student_name -> online/offline voor logging
sid_map = {}             # session_id -> student_name

LOG_FILE = "student_log.txt"

# Logbestand leeg maken bij opstart
with open(LOG_FILE, "w") as f:
    f.write("")

# ---------- HTML Pagina's ----------
LOGIN_HTML = """
<!doctype html>
<html>
<head>
    <title>Examen Aanmelden</title>
    <style>
        body { font-family: Arial; text-align:center; margin-top:50px; }
        .status { font-weight:bold; font-size:1.2em; margin-top:20px; }
        .online { color: green; }
        .offline { color: red; }
    </style>
</head>
<body>
    <h1>Examen Aanmelden</h1>
    <input type="text" id="name" placeholder="Vul je naam in">
    <button onclick="startExam()">Start Examen</button>

    <div class="status" id="status">Niet verbonden</div>

    <script src="//cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.1/socket.io.min.js"></script>
    <script>
        let socket;
        function startExam() {
            const name = document.getElementById("name").value.trim();
            if(!name) { alert("Vul je naam in!"); return; }

            socket = io({query: {name: name}});

            socket.on('connect', () => {
                document.getElementById("status").innerHTML = "ONLINE";
                document.getElementById("status").className = "status online";
            });

            socket.on('ping_server', () => {
                socket.emit('pong_client'); // elke PING meteen beantwoorden
            });

            socket.on('disconnect', () => {
                document.getElementById("status").innerHTML = "OFFLINE";
                document.getElementById("status").className = "status offline";
            });
        }

        // Stuur extra PONG elke seconde voor betrouwbaarheid
        setInterval(() => {
            if(socket) socket.emit('pong_client');
        }, 1000);
    </script>
</body>
</html>
"""

DASHBOARD_HTML = """
<!doctype html>
<html>
<head>
    <title>Exam Dashboard</title>
    <style>
        body { font-family: Arial; margin: 40px; }
        table { border-collapse: collapse; width: 60%; margin: auto; }
        th, td { border: 1px solid #ccc; padding: 10px; text-align: center; }
        th { background-color: #f0f0f0; }
        .online { color: green; font-weight: bold; }
        .offline { color: red; font-weight: bold; }
    </style>
</head>
<body>
    <h1 style="text-align:center;">Studenten Live Monitor</h1>
    <table>
        <thead>
            <tr>
                <th>Naam</th>
                <th>Laatste PONG</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody id="students"></tbody>
    </table>

    <script>
        async function update() {
            const res = await fetch('/status');
            const data = await res.json();
            data.students.sort((a,b) => (b.online - a.online));

            let html = "";
            for(const s of data.students) {
                html += `<tr>
                    <td>${s.name}</td>
                    <td>${s.last_pong}</td>
                    <td class="${s.online?'online':'offline'}">${s.online?'ONLINE':'OFFLINE'}</td>
                </tr>`;
            }
            document.getElementById("students").innerHTML = html;
        }

        setInterval(update, 1000);
        update();
    </script>
</body>
</html>
"""

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

        <!-- Label onder tijdslijn -->
        <div class="label">
            {% for seg in segments %}
                {{ seg.time }} ({{ seg.status }})<br>
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

# ---------- Routes ----------
@app.route('/login')
def login():
    return render_template_string(LOGIN_HTML)

@app.route('/dashboard')
def dashboard():
    return render_template_string(DASHBOARD_HTML)

@app.route('/status')
def status():
    now = datetime.now()
    data = []
    for name, last in students.items():
        diff = (now - last).total_seconds()
        online = diff <= TIMEOUT_SECONDS
        data.append({
            "name": name,
            "last_pong": last.strftime("%H:%M:%S"),
            "online": online
        })
    return {"students": data}

@app.route('/report')
def report():
    if not os.path.exists(LOG_FILE):
        return "Geen log beschikbaar"

    # Lees log
    report_data = {}
    with open(LOG_FILE) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            timestamp_str, name, status = line.split(" - ")
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            if name not in report_data:
                report_data[name] = []
            report_data[name].append({"time": timestamp, "status": status})

    MAX_EXAM_SECONDS = 4 * 60 * 60  # 4 uur
    filtered_report = {}
    offline_segments = {}

    for name, entries in report_data.items():
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

    # laatste segment (bij online of offline ≥30s)
    if last_time:
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

    filtered_report[name] = segments
    offline_segments[name] = offline_list

    return render_template_string(REPORT_HTML, report=filtered_report, offline_segments=offline_segments)

# ---------- Helper log functie ----------
def log_status(name, online):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"{timestamp} - {name} - {'ONLINE' if online else 'OFFLINE'}\n")

# ---------- SocketIO ----------
@socketio.on('connect')
def handle_connect():
    name = request.args.get('name')
    if name:
        students[name] = datetime.now()
        status_cache[name] = True
        sid_map[request.sid] = name
        log_status(name, True)
        print(f"[AANGEMELD] {name} verbonden")
    else:
        disconnect()

@socketio.on('pong_client')
def handle_pong():
    name = sid_map.get(request.sid)
    if name:
        students[name] = datetime.now()

@socketio.on('disconnect')
def handle_disconnect():
    name = sid_map.get(request.sid)
    if name:
        students[name] = datetime.now() - timedelta(seconds=TIMEOUT_SECONDS+1)  # force offline
        status_cache[name] = False
        log_status(name, False)
        print(f"[AFGEMELD] {name} disconnected")

# ---------- Ping / timeout loop ----------
def ping_loop():
    while True:
        socketio.emit('ping_server')
        now = datetime.now()
        for name, last in list(students.items()):
            diff = (now - last).total_seconds()
            online = diff <= TIMEOUT_SECONDS
            if status_cache.get(name) != online:
                status_cache[name] = online
                log_status(name, online)
                print(f"[STATUS] {name} is nu {'ONLINE' if online else 'OFFLINE'}")
                if not online:
                    sid_to_disconnect = [sid for sid, n in sid_map.items() if n==name]
                    for sid in sid_to_disconnect:
                        socketio.server.disconnect(sid)
        time.sleep(PING_INTERVAL)

# ---------- Start server ----------
if __name__ == "__main__":
    # Logbestand leegmaken bij start
    with open(LOG_FILE, "w") as f:
        f.write("")  # leeg bestand

    threading.Thread(target=ping_loop, daemon=True).start()
    print("[STARTING] Server met dashboard wordt gestart op http://192.168.0.35:8000/login")
    socketio.run(app, host='0.0.0.0', port=8000, debug=True)
