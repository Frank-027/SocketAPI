import socket
import threading

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Dit maakt geen echte verbinding, maar dwingt het OS te kiezen
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()

SERVER = get_local_ip() # Get local machine IP address        
PORT = 5050
ADDR = (SERVER, PORT) # Define server address
HEADER = 64  # Size of the header for message length    
FORMAT = 'utf-8' #  Encoding format
DISCONNECT_MESSAGE = "!DISCONNECT"  

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Create a TCP socket
server.bind(ADDR) # Bind the socket to the address  

def handle_client(conn, addr):
    print(f"[NEW CONNECTION] {addr} connected.")
    
    connected = True
    while connected:
        msg_length = conn.recv(HEADER).decode(FORMAT) # Receive message length
        if msg_length:
            msg_length = int(msg_length) # Convert length to integer
            msg = conn.recv(msg_length).decode(FORMAT) # Receive the actual message
            if msg == DISCONNECT_MESSAGE:
                connected = False
            
            print(f"[{addr}] {msg}") # Print the received message
            conn.send("ACK".encode(FORMAT)) # Send acknowledgment back to client       
            
    conn.close() # Close the connection
    print(f"[DISCONNECTED] {addr} disconnected.")

def start():
    server.listen() # Start listening for connections
    print(f"[LISTENING] Server is listening on {SERVER}")
    while True:
        conn, addr = server.accept() # Accept a new connection
        thread = threading.Thread(target=handle_client, args=(conn, addr)) # Create a new thread for the client
        thread.start() # Start the thread
        print(f"[ACTIVE CONNECTIONS] {threading.active_count() - 1}") # Print number of active connections  

print("[STARTING] Server is starting...")
start()  # Start the server
