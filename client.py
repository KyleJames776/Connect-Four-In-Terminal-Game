import socket
import argparse
import sys
import json
import struct

# --- Framing Utilities ---
def send_msg(sock, msg_dict):
    payload = json.dumps(msg_dict).encode('utf-8')
    header = struct.pack('!I', len(payload))
    sock.sendall(header + payload)

def recv_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk: 
            return None
        buf.extend(chunk)
    return bytes(buf)

def recv_msg(sock):
    header = recv_exact(sock, 4)
    if not header: 
        return None
    payload_len = struct.unpack('!I', header)[0]
    payload = recv_exact(sock, payload_len)
    if not payload: 
        return None
    return json.loads(payload.decode('utf-8'))

# --- Terminal UI ---
def print_board(board):
    print("\n  0   1   2   3   4   5   6")
    print("+" + "---+" * 7)
    for row in board:
        print("| " + " | ".join(row) + " |")
        print("+" + "---+" * 7)
    print("")

def main():
    parser = argparse.ArgumentParser(description="Connect 4 Game Client")
    parser.add_argument('-i', required=True, help="Server DNS hostname")
    parser.add_argument('-p', type=int, required=True, help="Server port")
    args = parser.parse_args()

    # --- Mandatory Rubric Item: Graceful DNS Resolution Catch ---
    try:
        server_ip = socket.gethostbyname(args.i)
    except socket.gaierror:
        print(f"[ERROR] Unable to resolve DNS hostname '{args.i}'.")
        print("Please check your Cisco router DNS configuration ('ip dns server' / 'ip host') or verify domain spelling.")
        sys.exit(1)

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect((server_ip, args.p))
        print("[*] Connected to server successfully.")
    except Exception as e:
        print(f"[ERROR] Could not connect to {server_ip}:{args.p} - {e}")
        sys.exit(1)

    my_role = None

    while True:
        try:
            msg = recv_msg(client)
            if not msg:
                print("\n[!] Disconnected from server.")
                break

            msg_type = msg.get("msg_type")

            if msg_type == "LOBBY_WAIT":
                print(f"\n[*] {msg.get('message')}")
            
            elif msg_type == "GAME_START":
                my_role = msg.get("role")
                print("\n[*] Game Started! You will receive your role shortly.")
            
            elif msg_type == "STATE_UPDATE":
                print_board(msg["board"])
                active_turn = msg["active_turn"]
                
                # # Infer our role based on who gets the first turn if not set
                # if my_role is None:
                #     my_role = "X" if active_turn == "X" else "O"

                # Stop prompting if the game is over (active_turn will be None)
                if active_turn:
                    print(f"--- Turn: Player {active_turn} ---")
                    
                    if active_turn == my_role:
                        col = input("Your turn! Enter column (0-6): ")
                        send_msg(client, {"msg_type": "MOVE", "payload": {"col": col}})
                    else:
                        print("Waiting for opponent to move...")
            
            elif msg_type == "ERROR":
                print(f"\n[X] ERROR: {msg.get('message')}")
                col = input("Try again! Enter column (0-6): ")
                send_msg(client, {"msg_type": "MOVE", "payload": {"col": col}})
            
            elif msg_type == "GAME_OVER":
                print(f"\n[*] GAME OVER! Result: {msg.get('result')}")
                if msg.get('winner'):
                    print(f"Winner: Player {msg.get('winner')}")
                break

        except (ConnectionResetError, BrokenPipeError, KeyboardInterrupt):
            print("\n[!] Connection lost or terminated.")
            break

    client.close()

if __name__ == "__main__":
    main()
    