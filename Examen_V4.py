# Examen_server_dashboard_web.py (complete versie)
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit, disconnect
from datetime import datetime
import threading
import time
from collections import defaultdict

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

        // Stuur extra PONG elke seconde, voor betrouwbaarheid
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
    <title>Student Log Report</title>
    <style>
        body { font-family: Arial; margin: 20px; }
        h2 { margin-top: 40px; }
        .timeline { display: flex; margin-bottom: 20px; }
        .segment { width: 20px; height: 20px; margin-right: 1px; }
        .online { background-color: green; }
        .offline { background-color: red; }
        .legend { margin-bottom: 20px; }
        .legend span { display: inline-block; width: 20px; height: 20px; margin-right: 5px; vertical-align: middle; }
    </style>
</head>
<body>
    <h1>Student Log Timeline</h1>
    <div class="legend">
        <span class="online"></span> ONLINE
        <span class="offline" style="margin-left:20px;"></span> OFFLINE
    </div>
    {% for student, entries in report.items() %}
        <h2>{{ student }}</h2>
        <div class="timeline">
            {% for entry in entries %}
                <div class="segment {{ 'online' if entry.status=='ONLINE' else 'offline' }}" title="{{ entry.time }} - {{ entry.status }}"></div>
            {% endfor %}
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
    
    report_data = {}
    with open(LOG_FILE) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            timestamp, name, status = line.split(" - ")
            if name not in report_data:
                report_data[name] = []
            report_data[name].append({"time": timestamp, "status": status})
    
    return render_template_string(REPORT_HTML, report=report_data)

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
        diff = TIMEOUT_SECONDS + 1
        students[name] = datetime.now() - timedelta(seconds=diff)  # force offline
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
        time.sleep(PING_INTERVAL)

# ---------- Start server ----------
if __name__ == "__main__":
    # Logbestand leegmaken bij start
    with open(LOG_FILE, "w") as f:
        f.write("")  # leeg bestand

    threading.Thread(target=ping_loop, daemon=True).start()
    print("[STARTING] Server met dashboard, login en report wordt gestart...")
    socketio.run(app, host='0.0.0.0', port=8000, debug=True)
