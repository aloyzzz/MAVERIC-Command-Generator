# MAVERIC Command Generator

Web-based command packet builder for the MAVERIC satellite ground station. Builds uplink command packets, manages a transmit queue, and exports files readable by **MAV_TX2**.

---

## Quick Start

```bash
streamlit run maveric_command_gen.py
```

Opens at `http://localhost:8501`.

### Requirements

```bash
pip install streamlit pyyaml
pip install crc        # optional — faster CRC-16; pure Python fallback used if absent
```

---

## Packet Format

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

## UI Guide

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

---

### Tab: History

Every packet saved via **📋 Save to History** appears here. Export the full session as `.txt` or `.json`.

---

### Loading Command Definitions

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
