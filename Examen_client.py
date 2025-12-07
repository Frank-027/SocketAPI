import socket
import time

SERVER = "192.168.0.10"   # jouw server IP
PORT = 5050
HEADER = 64
FORMAT = "utf-8"

name = input("Geef je naam: ")

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((SERVER, PORT))

# eerst naam naar server
def send(msg):
    message = msg.encode(FORMAT)
    msg_length = len(message)
    send_length = str(msg_length).encode(FORMAT)
    send_length += b' ' * (HEADER - len(send_length))
    client.send(send_length)
    client.send(message)

send(name)

# hoofdloop
while True:
    try:
        # server stuurt PING
        msg_length = client.recv(HEADER).decode(FORMAT)
        if msg_length:
            msg_length = int(msg_length)
            msg = client.recv(msg_length).decode(FORMAT)

            if msg == "PING":
                send("PONG")
    except:
        break
client.close()
print("Verbinding verbroken.")