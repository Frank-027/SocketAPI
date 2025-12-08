from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, disconnect
from datetime import datetime, timedelta
import threading, time
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = "secret"

# async_mode="threading" → werkt met Python client
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

TIMEOUT_SECONDS = 12
PING_INTERVAL = 1
LOG_FILE = "student_log.txt"

students = {}       # name -> last pong time
sid_map = {}        # sid -> name
status_cache = {}   # name -> last known online status

# Logbestand leegmaken bij start
with open(LOG_FILE, "w") as f:
    f.write("")

# ---------- DASHBOARD HTML ----------
DASHBOARD_HTML = """
<!doctype html>
<html>
<head>
<title>Exam Dashboard</title>
<style>
 body { font-family:Arial; margin:40px; }
 table { width:60%; border-collapse:collapse; margin:auto; }
 th,td { border:1px solid #ccc; padding:10px; text-align:center; }
 th { background-color:#f0f0f0; }
 .online { color:green; font-weight:bold; }
 .offline { color:red; font-weight:bold; }
</style>
</head>
<body>
<h1 style="text-align:center;">Studenten Live Monitor</h1>
<table>
<thead><tr><th>Naam</th><th>Laatste PONG</th><th>Status</th></tr></thead>
<tbody id="students"></tbody>
</table>

<script>
async function update() {
    const res = await fetch('/status');
    const data = await res.json();
    data.students.sort((a,b)=>b.online - a.online);

    let html="";
    for(const s of data.students){
        html += `<tr>
            <td>${s.name}</td>
            <td>${s.last_pong}</td>
            <td class="${s.online?'online':'offline'}">${s.online?'ONLINE':'OFFLINE'}</td>
        </tr>`;
    }
    document.getElementById("students").innerHTML=html;
}
setInterval(update,1000);
update();
</script>
</body>
</html>
"""

# ---------- ROUTES ----------
@app.route('/dashboard')
def dashboard():
    return render_template_string(DASHBOARD_HTML)

@app.route('/status')
def status():
    now = datetime.now()
    data = []
    for name, last in students.items():
        online = (now - last).total_seconds() <= TIMEOUT_SECONDS
        data.append({
            "name": name,
            "last_pong": last.strftime("%H:%M:%S"),
            "online": online
        })
    return {"students": data}

# ---------- LOGGING FUNCTIE ----------
def log_status(name, online):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"{ts} - {name} - {'ONLINE' if online else 'OFFLINE'}\n")

# ---------- SOCKET.IO EVENTS ----------
@socketio.on("connect")
def handle_connect(auth):
    name = request.args.get("name")
    if not name and auth and isinstance(auth, dict):
        name = auth.get("name")
    if not name:
        print("[ERROR] Connect zonder naam")
        return disconnect()

    sid_map[request.sid] = name
    students[name] = datetime.now()
    status_cache[name] = True
    log_status(name, True)

    print(f"[AANGEMELD] {name} | SID={request.sid}")

@socketio.on("pong_client")
def handle_pong():
    name = sid_map.get(request.sid)
    if name:
        students[name] = datetime.now()

@socketio.on("disconnect")
def handle_disconnect():
    name = sid_map.get(request.sid)
    if name:
        # Zet onmiddellijk offline
        students[name] = datetime.now() - timedelta(seconds=TIMEOUT_SECONDS+1)
        status_cache[name] = False
        log_status(name, False)
        print(f"[AFGEMELD] {name} | SID={request.sid}")
        sid_map.pop(request.sid, None)

# ---------- PING LOOP ----------
def ping_loop():
    while True:
        socketio.emit("ping_server")
        now = datetime.now()
        for name, last in list(students.items()):
            online = (now - last).total_seconds() <= TIMEOUT_SECONDS
            if status_cache.get(name) != online:
                status_cache[name] = online
                log_status(name, online)
                print(f"[STATUS] {name} is nu {'ONLINE' if online else 'OFFLINE'}")
                # Disconnect SIDs indien offline
                if not online:
                    for sid, n in list(sid_map.items()):
                        if n == name:
                            socketio.server.disconnect(sid)
        time.sleep(PING_INTERVAL)

# ---------- START SERVER ----------
if __name__ == "__main__":
    # Logbestand leegmaken bij serverstart
    with open(LOG_FILE, "w") as f:
        f.write("")
    print("[INFO] Logbestand gereset")

    # Start ping loop in aparte thread
    threading.Thread(target=ping_loop, daemon=True).start()
    print("SERVER MET DASHBOARD EN LOGGING RUNNING ON http://0.0.0.0:8000/dashboard")

    # Start de Socket.IO server
    socketio.run(app, host="0.0.0.0", port=8000)
