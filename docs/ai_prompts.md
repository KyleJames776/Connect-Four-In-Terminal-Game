# AI Prompting & Constraint Strategy

To ensure AI coding assistants generate compliant socket logic rather than hallucinating broken byte-stream handling, I used the following constrained system prompts.

## Prompt 1: Enforcing Deterministic TCP Framing
**Context:** AI tools frequently write networking code that assumes `json.loads(sock.recv(1024))` is safe. This prompt forces the AI to use the exact length-prefixed specification designed in the blueprint.

**Prompt:**
> "Write a Python TCP socket helper module with two functions: `send_msg(sock, payload_dict)` and `recv_msg(sock)`. 
> Constraint 1: You must strictly use a 4-byte Big-Endian unsigned integer (`struct.pack('!I')`) as a length prefix before the UTF-8 JSON payload. 
> Constraint 2: For `recv_msg`, you must implement a strict `while` loop that accumulates exact bytes (`recv_exact`). You are forbidden from passing a raw `sock.recv()` directly into `json.loads()`."

## Prompt 2: Enforcing Socket Teardown & EOF
**Context:** This prompt forces strict exception and EOF handling aligned with the server FSM.

**Prompt:**
> "Write the server-side event loop for a 2-player Connect 4 game. 
> Constraint 1: Inside your `recv_exact` loop, if `sock.recv()` returns `b""`, you must immediately return `None` to signal EOF. 
> Constraint 2: Wrap the message dispatch logic in a `try...except (ConnectionResetError, BrokenPipeError)` block. If an exception is caught or EOF is detected, trigger the forfeit logic and cleanly close the remaining sockets without crashing the server process."