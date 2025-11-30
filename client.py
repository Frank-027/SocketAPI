import socket

HEADER = 64  # Size of the header for message length    
FORMAT = 'utf-8' #  Encoding format
DISCONNECT_MESSAGE = "!DISCONNECT"  
SERVER = "192.168.0.35"  # Replace with the server's IP address       
PORT = 5050
ADDR = (SERVER, PORT) # Define server address

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Create a TCP socket
client.connect(ADDR) # Connect to the server    

def send(msg):
    message = msg.encode(FORMAT) # Encode the message
    msg_length = len(message) # Get the length of the message
    send_length = str(msg_length).encode(FORMAT) # Encode the length
    send_length += b' ' * (HEADER - len(send_length)) # Pad the length to fit the header size
    client.send(send_length) # Send the length
    client.send(message) # Send the actual message
    print(client.recv(2048).decode(FORMAT)) # Print server response (if any)

send("Hello Server!")  # Example message
input("Press Enter to continue...")  # Wait for user input before sending next message
send("This is a test message.")
input("Press Enter to continue...")  # Wait for user input before sending next message
send(DISCONNECT_MESSAGE)  # Disconnect from the server  
