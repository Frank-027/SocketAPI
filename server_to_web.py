import socket
import threading
import json
from flask import Flask, render_template_string

# ---------- Socket server setup ----------
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()

SERVER = get_local_ip()
PORT = 5050
ADDR = (SERVER, PORT)
HEADER = 64
FORMAT = 'utf-8'
DISCONNECT_MESSAGE = "!DISCONNECT"

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(ADDR)

# Globale variabele voor laatste data
latest_data = {"temperature": None, "pressure": None, "altitude": None}

# ---------- Handle TCP clients ----------
def handle_client(conn, addr):
    global latest_data
    print(f"[NEW CONNECTION] {addr} connected.")
    connected = True
    while connected:
        msg_length = conn.recv(HEADER).decode(FORMAT)
        if msg_length:
            msg_length = int(msg_length)
            msg = conn.recv(msg_length).decode(FORMAT)
            if msg == DISCONNECT_MESSAGE:
                connected = False
            else:
                print(f"[{addr}] {msg}")
                try:
                    latest_data = json.loads(msg)
                except json.JSONDecodeError:
                    print("[ERROR] Invalid JSON received")
            conn.send("ACK".encode(FORMAT))
    conn.close()
    print(f"[DISCONNECTED] {addr} disconnected.")

def start_socket_server():
    server.listen()
    print(f"[LISTENING] Socket server listening on {SERVER}:{PORT}")
    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_client, args=(conn, addr))
        thread.start()
        print(f"[ACTIVE CONNECTIONS] {threading.active_count() - 1}")

# ---------- Flask webserver ----------
app = Flask(__name__)

@app.route('/')
def index():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ESP32 Sensor Data</title>
        <meta http-equiv="refresh" content="2">
        <style>
            body { font-family: Arial; text-align:center; padding-top:50px; background:#f0f0f0; }
            .card { background:white; display:inline-block; padding:20px; border-radius:10px; box-shadow:0 0 10px rgba(0,0,0,0.1); }
            h1 { margin-bottom:20px; }
            p { font-size:1.5em; margin:5px 0; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>ESP32 Sensor Data</h1>
            <p>Temperature: {{ temperature }}</p>
            <p>Pressure: {{ pressure }}</p>
            <p>Altitude: {{ altitude }}</p>
        </div>
    </body>
    </html>
    """
    return render_template_string(html, **latest_data)

def start_flask():
    app.run(host='0.0.0.0', port=8080)

# ---------- Start beide servers ----------
if __name__ == "__main__":
    threading.Thread(target=start_socket_server, daemon=True).start()
    start_flask()  # Flask loopt in main thread
