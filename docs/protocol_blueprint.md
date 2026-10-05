# Conect 4 Application Protocol Blueprint

## Transport Layer & Packet Framing Mechanism

### Transport Protocol & Serialization
*   **Protocol:** TCP 
*   **Serialization Format:** TUTF-8 Encoded JSON

### The TCP Byte-Stream Problem
TCP is a continuous byte-stream protocol without built-in message boundaries. If a client sends multiple messages rapidly, they may arrive in a single `recv()` chunk (**coalescing**). Conversely, a single message may be split across multiple chunks (**fragmentation**). 

### Selected Framing Rule: Length-Prefixed Framing
To delimit message boundaries, this protocol uses a **4-byte length prefix**. 
Every message is preceded by a 4-byte unsigned integer in Network Byte Order (Big-Endian). This header specifies the exact byte length $N$ of the JSON payload that follows. The receiver first reads exactly the 4-byte header to determine payload size N, and then reads exactly N bytes from the stream before parsing.

**Receiver Extraction:**
The receiver must never pass `sock.recv()` directly to the JSON Parser. Instead, it must do these things isntead:
1. Read exactly 4 bytes to unpack the payload length $N$.
2. Loop `recv_exact` until exactly $N$ bytes are accumulated
3. Decode the accumulated bytes as UTF-8 JSON.

### Wire Stream Example
Example of a `CONNECT` message (69 bytes) and a `MOVE` message (76 bytes) sent back to back!

[4-Byte Length: 0x00000045 (69 bytes)] {"msg_type":"CONNECT","player_id":"Alice","timestamp":1727000000} [4-Byte Length: 0x0000005C (92 bytes)] {"msg_type":"MOVE","player_id":"Alice","payload":{"row":0,"col":2},"timestamp":1727000005}

### Application Message Types

## CONNECT
* **Direction:** Client -> Server
* **Purpose:** Client requests to join the game server with a player alias.

```json
{
        "msg_type": "CONNECT",
        "player_id": "Alice",
        "timestamp": 1727000000
}
```
## LOBBY_WAIT
* **Direction:** Server -> Client
* **Purpose:** Server notifies Player 1 that thier connection is accepted and it is waiting for Player 2.

```json
{
        "msg_type": "LOBBY_WAIT",
        "player_id": "Waiting for opponent to connect...",
        "timestamp": 1727000001
}
```
## GAME_START
* **Direction:** Server -> Both CLients
* **Purpose:** Server notifies both clients that the match has started, assigns roles (X/0), and dictates who goes first.

```json
{
        "msg_type": "GAME_START",
        "role": "X",
        "oppoenent_id": "Bob",
        "starting_turn": "Alice",
        "timestamp": 1727000005
}
```
## MOVE
* **Direction:** Client -> Server
* **Purpose:** Active player submits the column choice (0-6).

```json
{
        "msg_type": "MOVE",
        "player_id": "Alice",
        "payload": {
            "col": 3
        },
        "timestamp": 1727000010
}
```
## STATE_UPDATE
* **Direction:** Server -> Both CLients
* **Purpose:** Broadcasts the updated 6x7 game board, the cordinated of the last dropped symbol, and the next active turn.

```json
{
  "msg_type": "STATE_UPDATE",
  "board": [
    [" ", " ", " ", " ", " ", " ", " "],
    [" ", " ", " ", " ", " ", " ", " "],
    [" ", " ", " ", " ", " ", " ", " "],
    [" ", " ", " ", " ", " ", " ", " "],
    [" ", " ", " ", "X", " ", " ", " "],
    [" ", " ", "O", "X", "O", " ", " "]
  ],
  "last_move": {
    "player_id": "Alice",
    "row": 4,
    "col": 3
  },
  "active_turn": "Bob",
  "timestamp": 1727000011
}
```
## ERROR
* **Direction:** Server -> Client
* **Purpose:** Server rejects and invalid move, such as; column full, out of turn- without advancing the game state.

```json
{
        "msg_type": "ERROR",
        "code": "COLUMN_FULL",
        "message": "Column 2 is full. Pick a different column!",
        "timestamp": 1727000012
}
```
## DISCONNECT
* **Direction:** Client -> Server
* **Purpose:** Client notifes the server of an intentonal quit or departure.

```json
{
        "msg_type": "DISCONNECT",
        "player_id": "Alice",
        "reason": "USER_QUIT",
        "timestamp": 1727000020
}
```
## GAME_OVER
* **Direction:** Server -> Both Clients
* **Purpose:** Broadcasts final game outcome and the coordinates of the winning life if it exists.

```json
{
  "msg_type": "GAME_OVER",
  "result": "WIN",
  "winner": "Alice",
  "winning_line": [
    {"row": 5, "col": 3},
    {"row": 4, "col": 3},
    {"row": 3, "col": 3},
    {"row": 2, "col": 3}
  ],
  "timestamp": 1727000025

}
```

### Connection Termination & Socket Lifecycle Management

## Graceful Disconnection (Application Layer)
When a user exits the game on purpose, the client send a `DISCONNECT` messages and calls `sock.close()`, initating the TCP 4 way FIN-ACK Handshake. 
The Server then receives the message, awards a forfeit win to the remaining opponent via a `GAME_OVER` broadcast, and then finally cleaning uo socket resources.

## Transport Layer EOF Rule (0-Byte Detection)
When a remote host closes its connection cleanly, `sock.recv()` does not raise an exception. Instead, it returns `b""` (0 bytes) indicating (EOF).

* Prevention of Infinite Loops: The server's `recv_exact` loop must explicitly check `if not chunk: break`. If this is omitted, the application will enter a 100% CPU infinite loop repeatedly reading 0 bytes.

## Abrupt Termination (TCP RST)
If a client process crashes, loses power, or drops network connection, no FIN handshake is completed.

* Handling Exceptions: Subsequent attempts to read or write to the dead socket will raise `ConnectionResetError` (TCP RST) or `BrokenPipeError` (EPIPE).

* State Machine Action: The server wraps all socket I/O in a `try & except` block. Catching these exceptions triggers an immediate state transition to `GAME_OVER`, awarding a forfeit victory to the connected peer and executing server-side cleanup.




