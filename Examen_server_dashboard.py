import socket
import threading
import time
from datetime import datetime
from flask import Flask, jsonify, render_template_string

# ---------------- Config ----------------
SERVER = "0.0.0.0"
PORT = 5050
HEADER = 64
FORMAT = "utf-8"

PING_INTERVAL = 5      # seconden
TIMEOUT_SECONDS = 10   # als er geen PONG binnen deze tijd → offline

# Dictionaries om verbonden clients bij te houden
clients = {}       # socket → studentnaam
last_pong = {}     # studentnaam → datetime

# ---------------- Socket-server ----------------
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((SERVER, PORT))

def handle_client(conn, addr):
    """Per client/thread"""
    print(f"[NIEUWE VERBINDING] {addr}")

    try:
        # Eerst de naam ontvangen
        name_length = conn.recv(HEADER).decode(FORMAT)
        if not name_length:
            conn.close()
            return
        name_length = int(name_length)
        name = conn.recv(name_length).decode(FORMAT)
        clients[conn] = name
        last_pong[name] = datetime.now()
        print(f"[AANGEMELD] {name} is verbonden.")

        connected = True
        while connected:
            try:
                msg_length = conn.recv(HEADER).decode(FORMAT)
                if msg_length:
                    msg_length = int(msg_length)
                    msg = conn.recv(msg_length).decode(FORMAT)
                    if msg == "PONG":
                        last_pong[name] = datetime.now()
                    elif msg == "!DISCONNECT":
                        break
            except:
                break

    finally:
        print(f"[VERBINDING VERBROKEN] {clients.get(conn,'?')}")
        if conn in clients:
            del last_pong[clients[conn]]
            del clients[conn]
        conn.close()

def send_ping_loop():
    """Stuur elke PING_INTERVAL seconden een PING naar alle clients"""
    while True:
        time.sleep(PING_INTERVAL)
        now = datetime.now()
        for conn, name in list(clients.items()):
            try:
                msg = "PING".encode(FORMAT)
                msg_length = str(len(msg)).encode(FORMAT)
                msg_length += b' ' * (HEADER - len(msg_length))
                conn.send(msg_length)
                conn.send(msg)
            except:
                continue

# Start socket-server in aparte thread
def start_socket_server():
    server.listen()
    print(f"[LISTENING] Socket-server actief op {SERVER}:{PORT}")
    threading.Thread(target=send_ping_loop, daemon=True).start()
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

# ---------------- Flask-dashboard ----------------
app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Heartbeat Monitor</title>
    <meta charset="utf-8">
</head>
<body style="font-family: Arial; margin: 40px;">
    <h1>Studenten Live Monitor</h1>
    <p>Status wordt elke seconde bijgewerkt.</p>
    <table border="1" cellpadding="10">
        <thead>
            <tr>
                <th>Naam</th>
                <th>Laatste PONG tijd</th>
                <th>Inactiviteit (s)</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody id="students"></tbody>
    </table>
    <script>
        async function update() {
            const res = await fetch('/status');
            const data = await res.json();
            let html = "";
            for (const s of data.students) {
                html += `
                    <tr>
                        <td>${s.name}</td>
                        <td>${s.last_pong}</td>
                        <td>${s.inactive_seconds.toFixed(1)}</td>
                        <td style="color:${s.online ? 'green' : 'red'}; font-weight:bold;">
                            ${s.online ? 'ONLINE' : 'OFFLINE'}
                        </td>
                    </tr>
                `;
            }
            document.getElementById("students").innerHTML = html;
        }
        setInterval(update, 1000);
        update();
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/status")
def status():
    now = datetime.now()
    students = []
    for conn, name in clients.items():
        last = last_pong[name]
        diff = (now - last).total_seconds()
        online = diff <= TIMEOUT_SECONDS
        students.append({
            "name": name,
            "last_pong": last.strftime("%H:%M:%S"),
            "inactive_seconds": diff,
            "online": online
        })
    return jsonify({"students": students})

# ---------------- Main ----------------
if __name__ == "__main__":
    threading.Thread(target=start_socket_server, daemon=True).start()
    # Debug mode uitzetten of reload uitzetten
    app.run(host="0.0.0.0", port=8000, debug=False, use_reloader=False)

