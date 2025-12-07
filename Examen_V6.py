# Examen_server_dashboard_web.py (zonder report)
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
        body { font-family: Arial; background-color: #f2f2f2; }
        .container { width: 400px; margin: 80px auto; padding: 30px; background-color: #fff; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.2); text-align: center; }
        h1 { color: #333; }
        input { width: 90%; padding: 10px; margin: 10px 0; font-size: 1em; border-radius: 5px; border: 1px solid #ccc; }
        button { padding: 10px 20px; font-size: 1em; border-radius: 5px; border: none; background-color: #4CAF50; color: white; cursor: pointer; }
        button:hover { background-color: #45a049; }
        .status { font-weight: bold; font-size:1.2em; margin-top: 20px; }
        .online { color: green; }
        .offline { color: red; }
        .guideline { background-color: #e7f3fe; border-left: 6px solid #2196F3; padding: 10px; margin-top: 20px; text-align: left; }
        .warning { background-color: #ffe6e6; border-left: 6px solid #ff1a1a; padding: 10px; margin-top: 20px; text-align: left; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Examen Aanmelden</h1>
        <input type="text" id="studentNr" placeholder="Studentnummer">
        <input type="text" id="firstName" placeholder="Voornaam">
        <input type="text" id="lastName" placeholder="Naam">
        <button onclick="startExam()">Start Examen</button>

        <div class="status" id="status">Niet verbonden</div>

        <div class="guideline">
            <strong>Richtlijn:</strong> Houd deze pagina open tijdens het hele examen. <br>
            Vul correct je <strong>studentnummer, voornaam en naam</strong> in. Alleen de volgende tekens zijn toegestaan: <br>
            letters a-z/A-Z, cijfers 0-9, spaties, streepjes (-) en underscores (_).
        </div>

        <div class="warning">
            <strong>Waarschuwing:</strong> Je aanwezigheid op het examen netwerk (E109-E110) wordt gemonitord.<br>
            Inloggen op een ander netwerk wordt beschouwd als spieken.
        </div>
    </div>

    <script src="//cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.1/socket.io.min.js"></script>
    <script>
        let socket;

        function validateInput(text) {
            return /^[a-zA-Z0-9 _-]+$/.test(text);
        }

        function startExam() {
            const studentNr = document.getElementById("studentNr").value.trim();
            const firstName = document.getElementById("firstName").value.trim();
            const lastName = document.getElementById("lastName").value.trim();

            if(!studentNr || !firstName || !lastName) {
                alert("Vul alle velden correct in!");
                return;
            }

            if(!validateInput(studentNr) || !validateInput(firstName) || !validateInput(lastName)) {
                alert("Gebruik alleen toegestane tekens: letters, cijfers, spaties, - en _");
                return;
            }

            const name = studentNr + " - " + firstName + " " + lastName;
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
