import socket
import threading
import argparse
import json
import struct
import sys

# --- Framing Utilities ---
def send_msg(sock, msg_dict):
    """Packs a JSON dict with a 4-byte length prefix (!I)."""
    try:
        payload = json.dumps(msg_dict).encode('utf-8')
        header = struct.pack('!I', len(payload))
        sock.sendall(header + payload)
    except Exception as e:
        print(f"[ERROR] Failed to send message: {e}")

def recv_exact(sock, n):
    """Reads exactly n bytes from the socket."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)

def recv_msg(sock):
    """Unpacks the 4-byte length prefix and reads the JSON payload."""
    header = recv_exact(sock, 4)
    if not header:
        return None
    payload_len = struct.unpack('!I', header)[0]
    payload = recv_exact(sock, payload_len)
    if not payload:
        return None
    return json.loads(payload.decode('utf-8'))


# --- Game Engine (Shared State) ---
game_lock = threading.Lock()
board = [[" " for _ in range(7)] for _ in range(6)]
clients = []  # Stores tuples: (client_socket, player_role, address)
active_turn = "X"

def apply_gravity(col, role):
    """Drops the piece to the lowest available row. Returns True if successful."""
    for row in range(5, -1, -1):
        if board[row][col] == " ":
            board[row][col] = role
            return True
    return False

def check_win(piece):
    """Checks the board for a 4-in-a-row alignment."""
    # Horizontal
    for c in range(4):
        for r in range(6):
            if board[r][c] == piece and board[r][c+1] == piece and board[r][c+2] == piece and board[r][c+3] == piece:
                return True
    # Vertical
    for c in range(7):
        for r in range(3):
            if board[r][c] == piece and board[r+1][c] == piece and board[r+2][c] == piece and board[r+3][c] == piece:
                return True
    # Positive Diagonal
    for c in range(4):
        for r in range(3):
            if board[r][c] == piece and board[r+1][c+1] == piece and board[r+2][c+2] == piece and board[r+3][c+3] == piece:
                return True
    # Negative Diagonal
    for c in range(4):
        for r in range(3, 6):
            if board[r][c] == piece and board[r-1][c+1] == piece and board[r-2][c+2] == piece and board[r-3][c+3] == piece:
                return True
    return False

def broadcast(msg):
    """Pushes a message to both clients synchronously."""
    for client_sock, _, _ in clients:
        send_msg(client_sock, msg)


# --- Client Threading ---
def handle_client(client_sock, role, addr):
    global active_turn
    
    while True:
        try:
            msg = recv_msg(client_sock)
            if not msg:
                break  # Clean EOF disconnection
            
            if msg.get("msg_type") == "MOVE":
                with game_lock:
                    if active_turn != role:
                        send_msg(client_sock, {"msg_type": "ERROR", "message": "Not your turn!"})
                        continue
                    
                    try:
                        col = int(msg["payload"]["col"])
                    except (ValueError, KeyError):
                        send_msg(client_sock, {"msg_type": "ERROR", "message": "Malformed coordinates."})
                        continue

                    if col < 0 or col > 6:
                        send_msg(client_sock, {"msg_type": "ERROR", "message": "Invalid column (0-6)."})
                        continue
                        
                    if not apply_gravity(col, role):
                        send_msg(client_sock, {"msg_type": "ERROR", "message": "Column is full."})
                        continue
                    
                    # Check if this move won the game
                    if check_win(role):
                        update = {"msg_type": "STATE_UPDATE", "board": board, "active_turn": None}
                        broadcast(update)
                        broadcast({"msg_type": "GAME_OVER", "result": "WIN", "winner": role})
                        break # Exit loop, game is over
                    
                    # Otherwise, swap turn and broadcast
                    active_turn = "O" if role == "X" else "X"
                    update = {"msg_type": "STATE_UPDATE", "board": board, "active_turn": active_turn}
                    broadcast(update)
                    
        except (ConnectionResetError, BrokenPipeError):
            break  # Abrupt link drop

    # Teardown & Forfeit Notification
    print(f"[!] Client {role} ({addr}) disconnected.")
    with game_lock:
        if client_sock in [c[0] for c in clients]:
            clients[:] = [c for c in clients if c[0] != client_sock]
            if len(clients) == 1:
                broadcast({"msg_type": "GAME_OVER", "result": "FORFEIT", "winner": "Opponent disconnected"})
    client_sock.close()


def main():
    parser = argparse.ArgumentParser(description="Connect 4 Game Server")
    parser.add_argument('-p', type=int, required=True, help="Listening port")
    args = parser.parse_args()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('0.0.0.0', args.p))
    server.listen(2)
    print(f"[*] Server listening on 0.0.0.0:{args.p}")

    roles = ["X", "O"]
    
    while len(clients) < 2:
        client_sock, addr = server.accept()
        role = roles[len(clients)]
        clients.append((client_sock, role, addr))
        print(f"[*] Player {role} connected from {addr}")
        
        if len(clients) == 1:
            send_msg(client_sock, {"msg_type": "LOBBY_WAIT", "message": "Waiting for Player 2 to join..."})
        elif len(clients) == 2:
            # Send targeted GAME_START to tell each client their specific role
            for sock, r, a in clients:
                send_msg(sock, {"msg_type": "GAME_START", "role": r, "starting_turn": "X"})
            
            
            broadcast({
                "msg_type": "STATE_UPDATE", 
                "board": board, 
                "active_turn": active_turn
            })
         
            
            for sock, r, a in clients:
                threading.Thread(target=handle_client, args=(sock, r, a), daemon=True).start()
    # Keep main thread alive while workers handle sockets
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("\n[*] Shutting down server.")
        sys.exit(0)

if __name__ == "__main__":
    main()
