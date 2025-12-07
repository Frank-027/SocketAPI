# Examen_server_dashboard_web.py
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit, disconnect
from datetime import datetime
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

# ---------- Config ----------
PING_INTERVAL = 5        # sec
TIMEOUT_SECONDS = 10     # sec
students = {}            # student_name -> last_pong timestamp
status_cache = {}        # student_name -> online/offline voor logging

LOG_FILE = "student_log.txt"

# ---------- HTML Pagina's ----------
INDEX_HTML = """
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
        let online = false;

        function startExam() {
            const name = document.getElementById("name").value.trim();
            if(!name) { alert("Vul je naam in!"); return; }

            socket = io({query: {name: name}});

            socket.on('connect', () => {
                online = true;
                document.getElementById("status").innerHTML = "ONLINE";
                document.getElementById("status").className = "status online";
                console.log("Verbonden met server");
            });

            socket.on('ping_server', () => {
                socket.emit('pong_client');
            });

            socket.on('disconnect', () => {
                online = false;
                document.getElementById("status").innerHTML = "OFFLINE";
                document.getElementById("status").className = "status offline";
            });
        }
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

    <script src="//cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.1/socket.io.min.js"></script>
    <script>
        async function update() {
            const res = await fetch('/status');
            const data = await res.json();

            // sorteer online bovenaan
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

# ---------- Routes ----------
@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

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
        log_status(name, True)
        print(f"[AANGEMELD] {name} verbonden")
    else:
        disconnect()

@socketio.on('pong_client')
def handle_pong():
    for name in students.keys():
        students[name] = datetime.now()

# ---------- Ping loop ----------
def ping_loop():
    while True:
        socketio.emit('ping_server')
        now = datetime.now()
        # controleer status veranderingen
        for name, last in students.items():
            diff = (now - last).total_seconds()
            online = diff <= TIMEOUT_SECONDS
            if status_cache.get(name) != online:
                status_cache[name] = online
                log_status(name, online)
                print(f"[STATUS] {name} is nu {'ONLINE' if online else 'OFFLINE'}")
        time.sleep(PING_INTERVAL)

# ---------- Start server ----------
if __name__ == "__main__":
    threading.Thread(target=ping_loop, daemon=True).start()
    print("[STARTING] Server met dashboard wordt gestart...")
    socketio.run(app, host='0.0.0.0', port=8000, debug=True)
