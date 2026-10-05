# Connect 4 Server State Machine 

## Game State Machine Diagram
This Finite State Machine tracks the server-side lifecycle of the Connect 4 match!

```mermaid
stateDiagram-v2
    [*] --> INIT: Server Boot

    INIT --> WAITING_FOR_PLAYERS: Bind & Listen on Port

    WAITING_FOR_PLAYERS --> WAITING_FOR_PLAYERS: Player 1 Connects (Send LOBBY_WAIT)
    WAITING_FOR_PLAYERS --> GAME_START: Player 2 Connects

    GAME_START --> PLAYER_TURN_P1: Assign Roles & Send GAME_START

    PLAYER_TURN_P1 --> PLAYER_TURN_P1: Invalid Move or P2 Out-of-Turn (Send ERROR)
    PLAYER_TURN_P1 --> EVALUATE_MOVE_P1: Valid MOVE from P1
    PLAYER_TURN_P1 --> GAME_OVER: Any Player Disconnects (Forfeit)

    EVALUATE_MOVE_P1 --> GAME_OVER: Win / Draw Detected
    EVALUATE_MOVE_P1 --> PLAYER_TURN_P2: No Win (Send STATE_UPDATE)

    PLAYER_TURN_P2 --> PLAYER_TURN_P2: Invalid Move or P1 Out-of-Turn (Send ERROR)
    PLAYER_TURN_P2 --> EVALUATE_MOVE_P2: Valid MOVE from P2
    PLAYER_TURN_P2 --> GAME_OVER: Any Player Disconnects (Forfeit)

    EVALUATE_MOVE_P2 --> GAME_OVER: Win / Draw Detected
    EVALUATE_MOVE_P2 --> PLAYER_TURN_P1: No Win (Send STATE_UPDATE)

    GAME_OVER --> CLEANUP: Broadcast GAME_OVER Result
    CLEANUP --> [*]: Close Sockets & Reset to INIT
```

### State Machine Logic
The server steps through the following definitive states:
* `INIT`: The server allocates memory for the 6x7 grid, zeroes out game variables, and prepares network sockets.
* `WAITING_FOR_PLAYERS`: The server accepts the first TCP connection, transitions into a holding state (LOBBY_WAIT), and waits for the second connection.
* `GAME_START`: Triggered exactly when the second player connects. Assigns Player 1 as "X" and Player 2 as "O".
* `PLAYER_TURN` (P1/P2): The server blocks and waits for a MOVE payload. It validates the sender ID against the active turn identifier.
* `EVALUATE_MOVE`: The server applies gravity to the submitted column index (dropping the disc to the lowest empty row) and scans the 4 intersecting axes for a 4-in-a-row alignment or a 42-move board draw.
* `GAME_OVER`: Broadcasts the final result (WIN, DRAW, FORFEIT) and the winning player.CLEANUP: Sever connections cleanly, release port bindings/threads, and reset the board array to prepare for the next lobby.
## Error Handling, Edge Cases & Disconnect Transitions
To prevent server crashes or deadlocks, the FSM explicitly catches and handles the following failure paths:

## Invalid Moves & Out-of-Turn Actions
If the server is in `PLAYER_TURN_P1` and receives a `MOVE` from Player 2, or if Player 1 selects a column that is already full or out-of-bounds (<0 or >6), the FSM does not transition to `EVALUATE_MOVE`.
* Action: It traps the state, emits an ERROR message directly to the offending client, and immediately returns to awaiting valid input for the current turn.

## Abrupt Mid-Game Disconnections
At any point during `WAITING_FOR_PLAYERS`, `PLAYER_TURN`, or `EVALUATE_MOVE`, a client may drop abruptly.
* Action: The socket exception triggers an immediate forced transition directly to `GAME_OVER`. The server generates a synthetic forfeit event, declares the surviving connection the winner, broadcasts the result, and immediately moves to `CLEANUP`.