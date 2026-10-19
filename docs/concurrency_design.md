# Sprint 2: Server Concurrency & Game Behavior Architecture

## Detailed Architecture Specifications
The server implments the use of **Multi-Threading** using Python's native `threading.Thread` topic. I chose this architecture becasue it guarantees that the server can handle multiple simulantous client connections without blocking the main event loop, ensuring that the program will run silky smooth when running!

### Connection Lifecycle
1. **Boot & Bind** The main serbver starts by booting up, and initalizing the shared game state variables in memory, and then binds to a listening TCP port.
2. **Accept Loop** The main thread then will enger a `while True` loop, blocking only on `server_socket.accept()`.
3. **Client Registration** When the client connects, the main thread accepts the socket and immediatly spawns a new `ClientWorker` thread dedicated to that socket exclusively.
4. **Active Screening** The `ClientWorker` thread enters its own `recv_exact` blockiung loop to parse and iterate incoming network packets, like `MOVE`; without freezing the main server or any other clients.
5. **Teardown** If a client disconnects, the worker thread handles the teardown logic (awarding a forfeit), then closes its specific socket, and terminates cleanly.

## Thread Safety
Due to multiple `ClientWorker` threads operating concurrently, there will be a moment where they attempt to read or modify the game state at the exact same time. Without applying thread safetly mechanics a race conndition occurs.

### Shared Resources
To restrict the use of independent resources, I chose to allow shared resources so that variables reside in main process memory and are shared across all threads:
* `game_board`: The matrix tracking piece elements.
* `active_turn`: The string identifier of the player whose turn it currently is.
* `scores`: A dictionary tracking the current score for Player 1 and Player 2.
* `client_sockets`: A dictionary mapping player IDs to their active TCP socket objects which will be used for broadcasting.

### Locking Strategy
In help to preventing race conditions from occuring, the locking strategy that I'll use is a single Mutual Exclusion lock (`game_lock = threading.lock`)
* **Acquisition (`game_lock.acquire()`):** Before a worker thread validates a move, modifies the board, updates a score, or broadcasts a state update, it MUST acquire the lock. 
* **Critical Section:** While the lock is held, all other threads attempting to acquire it are paused. This guarantees sequential, atomic updates to the game state.
* **Release (`game_lock.release()`):** Once the state is modified and the `STATE_UPDATE` JSON is dispatched to the socket buffers, the lock is released.

## Move Validation & Time Synchronization
When the/a client submits a move, the server much act as the main authority, validatong the payload of the clients before the move can be finalized, and applied. Using move validation and time synchronization we can validate this:

### Synchronous State
1. **Request:** Player 1 sends a `MOVE` payload.
2. **Lock & Validate:** The server then acquires the `game_lock`. It checks if `active_turn == Player 1`. If true, it checks if the requested board column is legal.
3. **Mutation:** The server updates `game_board`. If the move results are in the clear or a win, it updates the `scores` dictionary.
4. **Broadcast:** The server loops through `client_sockets` and pushes the exact same `STATE_UPDATE` packet to **both** clients simultaneously. 
5. **Unlock:** The server releases the lock.

### Mermaid Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor C1 as Client 1 (Player X)
    participant S as Game Server (Shared State)
    actor C2 as Client 2 (Player O)

    C1->>S: MOVE {col: 3}
    
    Note over S: Thread 1 acquires game_lock
    Note over S: Validates active_turn == C1<br/>Checks column capacity & applies gravity
    
    alt Valid Move
        Note over S: Mutate game_board<br/>Switch active_turn to C2
        
        S-->>C1: STATE_UPDATE (Board, Turn: C2)
        S-->>C2: STATE_UPDATE (Board, Turn: C2)
        Note over S: Thread 1 releases game_lock
        
    else Invalid Move (e.g. Column Full)
        Note over S: State remains unchanged
        S-->>C1: ERROR ("Column Full - Pick Another")
        Note over S: Thread 1 releases game_lock
        
    else Out of Turn (Client 2 moves early)
        C2->>S: MOVE {col: 1}
        Note over S: Thread 2 acquires game_lock
        Note over S: active_turn != C2
        S-->>C2: ERROR ("Not your turn")
        Note over S: Thread 2 releases game_lock
    end