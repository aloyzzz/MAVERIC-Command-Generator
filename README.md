# MAVERIC Command Generator

Web-based command packet builder for the MAVERIC satellite ground station. Builds uplink command packets, manages a transmit queue, and exports files readable by **MAV_TX2**.

---

## Overview

The project has two parts:

| Component | What it does |
|---|---|
| `maveric_command_gen.py` | Streamlit web UI — build packets, manage TX queue, export |
| `MAVERIC_GSS/` | Ground Station Software — terminal dashboards for TX and RX |

---

## Quick Start

### Command Generator (Web UI)

```bash
streamlit run maveric_command_gen.py
```

Opens at `http://localhost:8501`.

### MAV_TX2 (Uplink Terminal)

```bash
cd MAVERIC_GSS
python3 MAV_TX2.py
```

### MAV_RX2 (Downlink Monitor)

```bash
cd MAVERIC_GSS
python3 MAV_RX2.py
```

---

## Requirements

```bash
pip install streamlit pyyaml
pip install crc        # optional — faster CRC-16; pure Python fallback used if absent
```

MAV_TX2 and MAV_RX2 additionally require:
- **GNU Radio 3.10+** with **gr-satellites**
- **PyZMQ** and **pmt** (included in radioconda)
- Python 3.8+, Linux/macOS (curses)

---

## Command Generator — UI Guide

### Packet format

Every MAVERIC command is a space-delimited string:

```
SRC DEST ECHO PTYPE CMD [ARGS...]
```

| Field | Description | Example values |
|---|---|---|
| `SRC` | Origin node | `GS` (6), `EPS` (2) |
| `DEST` | Destination node | `EPS` (2), `LPPM` (1) |
| `ECHO` | Echo/relay node | `NONE` (0) |
| `PTYPE` | Packet type | `REQ` (1), `RES` (2), `ACK` (3) |
| `CMD` | Command ID | `ping`, `set_voltage` |
| `ARGS` | Space-separated arguments | `3.3` |

**Node IDs**

| Name | ID |
|---|---|
| NONE | 0 |
| LPPM | 1 |
| EPS | 2 |
| UPPM | 3 |
| HOLONAV | 4 |
| ASTROBOARD | 5 |
| GS | 6 |
| FTDI | 7 |

---

### Tab: Build Packet

Use dropdowns and form inputs to construct a packet.

1. Select **SRC**, **DEST**, **ECHO**, and **PTYPE** from the header section.
2. Select a **Command** from the loaded command list.
3. Fill in any required arguments. Argument types are enforced:
   - `int` — decimal or hex (e.g. `255` or `0xFF`)
   - `float` — e.g. `3.3`
   - `epoch_ms` — Unix timestamp in milliseconds; use the **NOW** button to insert the current time
   - `bool` — `true` / `false` / `1` / `0`
   - `str` — free text
4. The generated packet string is shown live at the bottom.
5. Click **➕ Add to Queue** to stage the command for transmission.

---

### Tab: Raw Input Parser

Type a packet string in flexible shorthand and the UI resolves it.

**Accepted formats:**

```
GS EPS NONE REQ set_voltage 3.3   # full names
6 2 0 1 set_voltage 3.3            # numeric IDs
2 0 1 set_voltage 3.3              # SRC omitted → defaults to GS (6)
2 1 set_voltage 3.3                # SRC and ECHO omitted → GS, NONE
```

The parser shows the resolved fields and a color-coded packet display. Click **➕ Add to Queue** to stage the command.

---

### Tab: TX Queue

Manage the list of commands to be sent.

- **↑ / ↓** — reorder commands
- **🗑️** — remove a single command
- **Clear All** — empty the queue

**Exporting the queue for MAV_TX2:**

| Button | What it produces |
|---|---|
| **⬇️ Download pending_queue.txt** | Download a plain-text file, one command per line |
| **📤 Write to queue file** | Write directly to `MAVERIC_GSS/logs/pending_queue.txt` |

The exported file format is one packet string per line:

```
6 2 0 1 set_voltage 3.3
6 1 0 1 ping
6 2 0 1 set_mode nominal
```

MAV_TX2 reads this file on startup and loads the commands directly into its TX queue.

---

### Tab: History

Every packet saved via **📋 Save to History** appears here. Export the full session as `.txt` or `.json`.

---

### Loading command definitions

The sidebar lets you define which commands are available.

**Upload a YAML or JSON file** with this structure:

```yaml
commands:
  ping:
    args: []

  set_voltage:
    args:
      - name: voltage
        type: float

  tlm_beacon:
    args:
      - name: seq
        type: int
      - name: unix_time
        type: epoch_ms
      - name: status_a
        type: int
      - name: status_b
        type: int

  set_mode:
    args:
      - name: mode
        type: str
```

Supported argument types: `str`, `int`, `float`, `epoch_ms`, `bool`.
Add `variadic: true` to a command to allow extra arguments beyond the schema.

You can also **edit the YAML inline** using the expander in the sidebar, then click **Apply YAML**.

---

## MAV_TX2 — Uplink Terminal

```bash
cd MAVERIC_GSS
python3 MAV_TX2.py
# or skip the splash screen:
python3 MAV_TX2.py --nosplash
```

### Queue from Command Generator

If `logs/pending_queue.txt` exists when MAV_TX2 starts, it is loaded automatically into the TX queue — no extra steps needed.

### Typing commands directly

Use the input bar at the bottom:

```
[SRC] DEST ECHO PTYPE CMD [ARGS]
```

`SRC` is optional (defaults to `GS`). Command IDs are case-insensitive.

```
EPS NONE REQ set_voltage 3.3
GS EPS NONE REQ ping
2 0 1 set_mode nominal
```

### Keyboard shortcuts

| Key | Action |
|---|---|
| **Ctrl+S** | Send all queued commands |
| **Ctrl+Z** | Undo (remove last queued command) |
| **Ctrl+X** | Clear the entire queue |
| **↑ / ↓** | Recall command history |
| **PgUp / PgDn** | Scroll sent history |
| **Ctrl+A / Ctrl+E** | Jump to start / end of input |
| **Ctrl+W** | Delete word |
| **Ctrl+U** | Clear input line |
| **Ctrl+C / Esc** | Abort send or quit |

### Built-in commands

| Command | Action |
|---|---|
| `send` | Send all queued commands |
| `clear` | Clear TX queue |
| `undo` / `pop` | Remove last queued command |
| `hclear` | Clear sent history |
| `help` | Toggle help panel |
| `config` / `cfg` | Toggle config panel |
| `nodes` | Show node ID map |
| `csp [field] [value]` | Inspect or update CSP config |
| `ax25 [dest\|src] [callsign]` | Inspect or update AX.25 callsigns |
| `q` / `quit` | Exit |

### Logs

Each session writes to `MAVERIC_GSS/logs/`:
- `uplink_YYYYMMDD_HHMMSS.txt` — human-readable
- `uplink_YYYYMMDD_HHMMSS.jsonl` — machine-readable

---

## MAV_RX2 — Downlink Monitor

```bash
cd MAVERIC_GSS
python3 MAV_RX2.py
```

Subscribes to the GNU Radio ZMQ output and displays decoded downlink packets in real time.

### Keyboard shortcuts

| Key | Action |
|---|---|
| **↑ / ↓** | Navigate packet list |
| **Enter** | Expand / collapse packet detail |
| **PgUp / PgDn** | Page scroll |
| **Home / End** | Jump to first / last packet |
| **Ctrl+C** | Quit |

### Built-in commands

| Command | Action |
|---|---|
| `hex` | Toggle hex / ASCII display |
| `log` | Toggle session logging |
| `hclear` | Clear packet history |
| `help` | Toggle help panel |
| `config` / `cfg` | Toggle config panel |
| `q` / `quit` | Exit |

### Logs

Each session writes to `MAVERIC_GSS/logs/`:
- `downlink_YYYYMMDD_HHMMSS.txt` — human-readable
- `downlink_YYYYMMDD_HHMMSS.jsonl` — machine-readable

---

## Configuration

`MAVERIC_GSS/maveric_gss.yml` controls all runtime defaults. Missing keys fall back to hardcoded defaults so the file is optional.

```yaml
nodes:
  0: NONE
  1: LPPM
  2: EPS
  3: UPPM
  4: HOLONAV
  5: ASTROBOARD
  6: GS
  7: FTDI

ptypes:
  0: NONE
  1: REQ
  2: RES
  3: ACK

ax25:
  src_call:  "WM2XBB"   # ground station callsign
  src_ssid:  0
  dest_call: "WS9XSW"   # satellite callsign
  dest_ssid: 0

csp:
  priority:    2
  source:      0         # GS CSP address
  destination: 8         # satellite CSP address
  dest_port:   0
  src_port:    24
  flags:       0x00

tx:
  zmq_addr:  "tcp://127.0.0.1:52002"
  frequency: "437.25 MHz"
  delay_ms:  500          # inter-packet delay when sending a batch

rx:
  zmq_addr: "tcp://127.0.0.1:52001"

general:
  log_dir:      "logs"
  command_defs: "maveric_commands.yml"
```

AX.25 callsigns and CSP fields can also be changed at runtime from the `config` panel inside MAV_TX2 or MAV_RX2 without restarting.

---

## Typical Workflow

1. Start `maveric_command_gen.py` and load your command YAML.
2. Build packets in the **Build** or **Raw Input** tabs and add them to the queue.
3. Review order in the **TX Queue** tab; reorder or remove as needed.
4. Click **📤 Write to queue file** to write `MAVERIC_GSS/logs/pending_queue.txt`.
5. Start `MAV_TX2.py` — it loads the queue automatically.
6. Press **Ctrl+S** to transmit.
7. Monitor the downlink in a separate terminal with `MAV_RX2.py`.
