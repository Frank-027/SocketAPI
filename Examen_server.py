# Examen_server.py
import socket
import threading
import time
from datetime import datetime
import Examen_core as core

SERVER = "0.0.0.0"
PORT = 5050
HEADER = 64
FORMAT = "utf-8"
PING_INTERVAL = 5  # seconden

# Socket opzetten
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((SERVER, PORT))

def handle_client(conn, addr):
    print(f"[NIEUWE VERBINDING] {addr}")

    # Eerst de naam ontvangen
    try:
        name_length = int(conn.recv(HEADER).decode(FORMAT))
        name = conn.recv(name_length).decode(FORMAT)
    except:
        conn.close()
        return

    core.clients[conn] = name
    core.last_pong[name] = datetime.now()
    print(f"[AANGEMELD] {name} is verbonden.")

    connected = True
    while connected:
        try:
            msg_length = conn.recv(HEADER).decode(FORMAT)
            if not msg_length:
                break
            msg_length = int(msg_length)
            msg = conn.recv(msg_length).decode(FORMAT)

            if msg == "PONG":
                core.last_pong[name] = datetime.now()
                print(f"[PONG ontvangen] {name}")
            elif msg == "!DISCONNECT":
                break
        except:
            break

    print(f"[VERBINDING VERBROKEN] {name}")
    conn.close()
    del core.clients[conn]
    del core.last_pong[name]

def send_ping_loop():
    """Stuurt elke X seconden PING naar alle clients."""
    while True:
        time.sleep(PING_INTERVAL)
        now = datetime.now()
        for conn, name in list(core.clients.items()):
            try:
                msg = "PING".encode(FORMAT)
                msg_length = str(len(msg)).encode(FORMAT)
                msg_length += b' ' * (HEADER - len(msg_length))
                conn.send(msg_length)
                conn.send(msg)
            except:
                continue
            # Status check
            diff = (now - core.last_pong[name]).total_seconds()
            if diff > core.TIMEOUT_SECONDS:
                print(f"[OFFLINE] {name} reageert niet meer ({diff:.1f}s)")
            else:
                print(f"[ONLINE] {name} ({diff:.1f}s geleden PONG)")

def start():
    server.listen()
    print(f"[LISTENING] Server actief op {SERVER}:{PORT}")
    threading.Thread(target=send_ping_loop, daemon=True).start()
    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_client, args=(conn, addr))
        thread.start()

if __name__ == "__main__":
    print("[STARTING] Server wordt gestart...")
    start()
