"""
MAVERIC Satellite Command Generator
Streamlit UI for building and parsing satellite command packets.
"""

import os
import sys
import streamlit as st
import yaml
import json
import time
import re
from datetime import datetime, timezone
from pathlib import Path

# ─── Protocol import (for raw_cmd computation) ───────────────────────────────
_GSS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MAVERIC_GSS")
if _GSS_PATH not in sys.path:
    sys.path.insert(0, _GSS_PATH)
try:
    from mav_gss_lib.protocol import build_cmd_raw as _build_cmd_raw
    _PROTOCOL_OK = True
except ImportError:
    _PROTOCOL_OK = False

# ─── Default built-in YAML ───────────────────────────────────────────────────
DEFAULT_YAML = """\
commands:
  ping:
    args: []

  tlm_beacon:
    args:
      - name: seq
        type: int
      - name: unix time
        type: epoch_ms
      - name: status_a
        type: int
      - name: status_b
        type: int

  set_mode:
    args:
      - name: mode
        type: str

  set_voltage:
    args:
      - name: voltage
        type: float
"""

# ─── Constants ───────────────────────────────────────────────────────────────
NODE_MAP = {
    "NONE": 0, "LPPM": 1, "EPS": 2, "UPPM": 3,
    "HOLONAV": 4, "ASTROBOARD": 5, "GS": 6, "FTDI": 7,
}
NODE_MAP_INV = {v: k for k, v in NODE_MAP.items()}

PTYPE_MAP = {"NONE": 0, "REQ": 1, "RES": 2, "ACK": 3}
PTYPE_MAP_INV = {v: k for k, v in PTYPE_MAP.items()}

NODE_OPTIONS   = list(NODE_MAP.keys())
PTYPE_OPTIONS  = list(PTYPE_MAP.keys())

EPOCH_MS_MIN = 1_700_000_000_000   # ~Nov 2023
EPOCH_MS_MAX = 1_893_456_000_000   # ~2030

# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MAVERIC Command Generator",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Rajdhani', sans-serif;
}

/* Warm off-white background */
.stApp {
    background: #F7F5F2;
    color: #1F1F1F;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #EDEAE4 !important;
    border-right: 1px solid #D9D4CC;
}
section[data-testid="stSidebar"] * {
    color: #3D3A36 !important;
}

/* Top header banner */
.maveric-header {
    background: linear-gradient(90deg, #EDE9E2 0%, #F2EFE9 40%, #EDE9E2 100%);
    border: 1px solid #D4CFC6;
    border-radius: 4px;
    padding: 16px 28px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    gap: 16px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.maveric-header h1 {
    font-family: 'Share Tech Mono', monospace;
    font-size: 1.6rem;
    color: #C26D3A;
    margin: 0;
    letter-spacing: 0.12em;
}
.maveric-header .subtitle {
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.72rem;
    color: #9A8E82;
    letter-spacing: 0.18em;
    margin-top: 2px;
}

/* Section labels */
.section-label {
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.65rem;
    color: #9A8E82;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    margin-bottom: 6px;
    border-bottom: 1px solid #D9D4CC;
    padding-bottom: 4px;
}

/* Packet output box */
.packet-box {
    background: #FFFFFF;
    border: 1px solid #D4CFC6;
    border-left: 3px solid #C26D3A;
    border-radius: 4px;
    padding: 18px 22px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 1.05rem;
    color: #3D3A36;
    letter-spacing: 0.08em;
    word-break: break-all;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    margin: 8px 0;
}
.packet-box .field-src  { color: #C0392B; }
.packet-box .field-dst  { color: #C87A2A; }
.packet-box .field-echo { color: #5A8A3C; }
.packet-box .field-ptype{ color: #3A7AB5; }
.packet-box .field-cmd  { color: #8B5CA8; }
.packet-box .field-arg  { color: #2A8A72; }

/* Numeric field tags */
.num-tag {
    display: inline-block;
    background: #F0EDE8;
    border: 1px solid #D4CFC6;
    border-radius: 3px;
    padding: 1px 7px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.78rem;
    color: #C26D3A;
    margin-right: 4px;
}

/* Raw input field */
.stTextInput > div > div > input {
    background: #FFFFFF !important;
    border: 1px solid #D4CFC6 !important;
    border-radius: 4px !important;
    color: #1F1F1F !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 0.92rem !important;
}
.stTextInput > div > div > input:focus {
    border-color: #C26D3A !important;
    box-shadow: 0 0 0 1px #C26D3A33 !important;
}

/* Selectboxes */
.stSelectbox > div > div {
    background: #FFFFFF !important;
    border: 1px solid #D4CFC6 !important;
    color: #1F1F1F !important;
}

/* Number inputs */
.stNumberInput > div > div > input {
    background: #FFFFFF !important;
    border: 1px solid #D4CFC6 !important;
    color: #1F1F1F !important;
    font-family: 'Share Tech Mono', monospace !important;
}

/* Buttons */
.stButton > button {
    background: #F0EDE8 !important;
    border: 1px solid #D4CFC6 !important;
    color: #C26D3A !important;
    font-family: 'Rajdhani', sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    transition: all 0.2s !important;
}
.stButton > button:hover {
    background: #E8E2D9 !important;
    border-color: #C26D3A !important;
    box-shadow: 0 1px 4px rgba(194,109,58,0.15) !important;
}

/* Alerts */
.stSuccess {
    background: #F2F8F0 !important;
    border-left: 3px solid #5A8A3C !important;
}
.stError {
    background: #FDF2F2 !important;
    border-left: 3px solid #C0392B !important;
}
.stWarning {
    background: #FDF6EE !important;
    border-left: 3px solid #C87A2A !important;
}
.stInfo {
    background: #F0F5FC !important;
    border-left: 3px solid #3A7AB5 !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: #EDEAE4;
    border-bottom: 1px solid #D9D4CC;
    gap: 0;
}
.stTabs [data-baseweb="tab"] {
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 0.75rem !important;
    letter-spacing: 0.12em !important;
    color: #9A8E82 !important;
    background: transparent !important;
    border: none !important;
    padding: 8px 20px !important;
}
.stTabs [aria-selected="true"] {
    color: #C26D3A !important;
    border-bottom: 2px solid #C26D3A !important;
}

/* Expander */
.streamlit-expanderHeader {
    background: #F0EDE8 !important;
    border: 1px solid #D4CFC6 !important;
    color: #C26D3A !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 0.78rem !important;
    letter-spacing: 0.1em !important;
}

/* Status dot */
.status-dot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #5A8A3C;
    box-shadow: 0 0 6px rgba(90,138,60,0.4);
    margin-right: 8px;
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0%,100% { opacity:1; } 50% { opacity:0.4; }
}

/* Divider */
hr { border-color: #D9D4CC !important; }

/* Packet history table */
.history-item {
    background: #FFFFFF;
    border: 1px solid #D9D4CC;
    border-radius: 3px;
    padding: 8px 14px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.78rem;
    color: #7A6E65;
    margin-bottom: 4px;
    cursor: pointer;
}
.history-item:hover {
    border-color: #C26D3A;
    color: #3D3A36;
}
</style>
""", unsafe_allow_html=True)

# ─── Helpers ─────────────────────────────────────────────────────────────────
def load_commands(yaml_text: str) -> dict:
    try:
        data = yaml.safe_load(yaml_text)
        return data.get("commands", {}) if data else {}
    except Exception as e:
        st.error(f"YAML parse error: {e}")
        return {}

def node_id(val: str) -> int:
    val = val.strip().upper()
    if val in NODE_MAP:
        return NODE_MAP[val]
    try:
        return int(val)
    except ValueError:
        return -1

def ptype_id(val: str) -> int:
    val = val.strip().upper()
    if val in PTYPE_MAP:
        return PTYPE_MAP[val]
    try:
        return int(val)
    except ValueError:
        return -1

def validate_epoch_ms(val) -> tuple[bool, str]:
    try:
        v = int(val)
        if EPOCH_MS_MIN <= v <= EPOCH_MS_MAX:
            dt = datetime.fromtimestamp(v / 1000, tz=timezone.utc)
            return True, dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        return False, f"Out of mission range ({EPOCH_MS_MIN}–{EPOCH_MS_MAX})"
    except:
        return False, "Not a valid integer"

def now_epoch_ms() -> int:
    return int(time.time() * 1000)

def format_packet_html(src, dst, echo, ptype, cmd, args_list):
    src_s  = f'<span class="field-src">{src}</span>'
    dst_s  = f'<span class="field-dst">{dst}</span>'
    echo_s = f'<span class="field-echo">{echo}</span>'
    pt_s   = f'<span class="field-ptype">{ptype}</span>'
    cmd_s  = f'<span class="field-cmd">{cmd}</span>'
    args_s = " ".join(f'<span class="field-arg">{a}</span>' for a in args_list)
    parts  = [src_s, dst_s, echo_s, pt_s, cmd_s]
    if args_s:
        parts.append(args_s)
    return " ".join(parts)

def parse_raw_input(raw: str, commands: dict) -> dict | None:
    """
    Parse flexible input formats:
      GS EPS REQ SET_VOLTAGE 3.3
      6 2 0 1 SET_VOLTAGE 3.3
      2 0 1 SET_VOLTAGE 3.3  → src defaults to 6 (GS)
    Returns dict with keys: src, dst, echo, ptype, cmd, args_str, errors
    """
    tokens = raw.strip().split()
    if not tokens:
        return None

    errors = []
    result = {}

    # Detect if cmd token — find first token that matches a command name (case-insensitive)
    cmd_names_lower = {k.lower(): k for k in commands.keys()}

    # Find the command position
    cmd_idx = None
    for i, t in enumerate(tokens):
        if t.upper() in [k.upper() for k in commands.keys()]:
            cmd_idx = i
            break

    if cmd_idx is None:
        errors.append("No recognized command found in input.")
        return {"errors": errors}

    header_tokens = tokens[:cmd_idx]
    cmd_token     = tokens[cmd_idx]
    arg_tokens    = tokens[cmd_idx + 1:]

    # Resolve command name (case-insensitive match)
    actual_cmd = cmd_names_lower.get(cmd_token.lower(), cmd_token.upper())

    # Parse header: expect 4, 3, or 2 tokens (fallback rules)
    src = dst = echo = ptype = None

    if len(header_tokens) == 4:
        src   = node_id(header_tokens[0])
        dst   = node_id(header_tokens[1])
        echo  = node_id(header_tokens[2])
        ptype = ptype_id(header_tokens[3])
    elif len(header_tokens) == 3:
        # SRC = 6 (GS) fallback
        src   = 6
        dst   = node_id(header_tokens[0])
        echo  = node_id(header_tokens[1])
        ptype = ptype_id(header_tokens[2])
    elif len(header_tokens) == 2:
        src   = 6
        dst   = node_id(header_tokens[0])
        echo  = 0
        ptype = ptype_id(header_tokens[1])
    elif len(header_tokens) == 1:
        src   = 6
        dst   = node_id(header_tokens[0])
        echo  = 0
        ptype = 1  # REQ default
    elif len(header_tokens) == 0:
        src   = 6
        dst   = 0
        echo  = 0
        ptype = 1
        errors.append("No header tokens; defaulting SRC=GS DST=NONE ECHO=NONE PTYPE=REQ")

    for label, val in [("SRC", src), ("DST", dst), ("ECHO", echo), ("PTYPE", ptype)]:
        if val is None or val < 0:
            errors.append(f"Could not resolve {label}")

    result = {
        "src": src if src is not None else 6,
        "dst": dst if dst is not None else 0,
        "echo": echo if echo is not None else 0,
        "ptype": ptype if ptype is not None else 1,
        "cmd": actual_cmd,
        "args_str": " ".join(arg_tokens),
        "errors": errors,
    }
    return result

def build_packet_string(src, dst, echo, ptype, cmd, args_list) -> str:
    parts = [str(src), str(dst), str(echo), str(ptype), cmd]
    parts += [str(a) for a in args_list]
    return " ".join(parts)

def build_queue_entry(src, dst, echo, ptype, cmd, args_list) -> dict:
    args_str = " ".join(str(a) for a in args_list)
    raw_hex = ""
    if _PROTOCOL_OK:
        try:
            raw = _build_cmd_raw(dst, cmd.lower(), args_str, echo=echo, ptype=ptype, origin=src)
            raw_hex = bytes(raw).hex()
        except Exception:
            pass
    return {
        "src": src, "dest": dst, "echo": echo, "ptype": ptype,
        "cmd": cmd.lower(), "args": args_str, "raw_cmd": raw_hex,
    }

# ─── Session state ────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []
if "yaml_text" not in st.session_state:
    st.session_state.yaml_text = DEFAULT_YAML
if "tx_queue" not in st.session_state:
    st.session_state.tx_queue = []

# ─── Header ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="maveric-header">
  <div>
    <div style="font-size:2rem; line-height:1">🛰️</div>
  </div>
  <div>
    <h1>MAVERIC  COMMAND  GENERATOR</h1>
    <div class="subtitle"><span class="status-dot"></span>MISSION OPERATIONS · PACKET BUILDER v1.0</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ─── Sidebar: YAML loader ─────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="section-label">Command Definitions</div>', unsafe_allow_html=True)

    uploaded = st.file_uploader("Upload YAML / JSON", type=["yml", "yaml", "json"])
    if uploaded:
        raw_bytes = uploaded.read()
        if uploaded.name.endswith(".json"):
            try:
                j = json.loads(raw_bytes)
                st.session_state.yaml_text = yaml.dump({"commands": j.get("commands", j)})
            except Exception as e:
                st.error(f"JSON parse error: {e}")
        else:
            st.session_state.yaml_text = raw_bytes.decode()
        st.success(f"Loaded: {uploaded.name}")

    with st.expander("✏️ Edit YAML inline", expanded=False):
        new_yaml = st.text_area("", value=st.session_state.yaml_text, height=340, label_visibility="collapsed")
        if st.button("Apply YAML"):
            st.session_state.yaml_text = new_yaml
            st.success("YAML updated.")

    commands = load_commands(st.session_state.yaml_text)
    st.markdown(f'<div class="section-label">{len(commands)} commands loaded</div>', unsafe_allow_html=True)
    for cname in commands:
        nargs = len(commands[cname].get("args", []))
        variadic = commands[cname].get("variadic", False)
        tag = "∞" if variadic else str(nargs)
        st.markdown(f'<span class="num-tag">{tag}</span> `{cname}`', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div class="section-label">Node Reference</div>', unsafe_allow_html=True)
    for name, nid in NODE_MAP.items():
        st.markdown(f'<span class="num-tag">{nid}</span> {name}', unsafe_allow_html=True)

    st.markdown('<div class="section-label" style="margin-top:12px">Packet Types</div>', unsafe_allow_html=True)
    for name, pid in PTYPE_MAP.items():
        st.markdown(f'<span class="num-tag">{pid}</span> {name}', unsafe_allow_html=True)

# ─── Main content ─────────────────────────────────────────────────────────────
commands = load_commands(st.session_state.yaml_text)

tab_build, tab_raw, tab_queue, tab_history = st.tabs(["⚡  BUILD PACKET", "📡  RAW INPUT PARSER", "📤  TX QUEUE", "📋  HISTORY"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — GUI BUILDER
# ══════════════════════════════════════════════════════════════════════════════
with tab_build:
    col_hdr, col_cmd = st.columns([2, 3])

    with col_hdr:
        st.markdown('<div class="section-label">Packet Header</div>', unsafe_allow_html=True)
        hcol1, hcol2 = st.columns(2)
        with hcol1:
            src_sel  = st.selectbox("SRC (Origin)",  NODE_OPTIONS, index=NODE_OPTIONS.index("GS"), key="b_src")
            echo_sel = st.selectbox("ECHO",          NODE_OPTIONS, index=NODE_OPTIONS.index("NONE"), key="b_echo")
        with hcol2:
            dst_sel   = st.selectbox("DST (Dest)",   NODE_OPTIONS, index=NODE_OPTIONS.index("EPS"), key="b_dst")
            ptype_sel = st.selectbox("PTYPE",        PTYPE_OPTIONS, index=PTYPE_OPTIONS.index("REQ"), key="b_ptype")

    with col_cmd:
        st.markdown('<div class="section-label">Command</div>', unsafe_allow_html=True)
        if not commands:
            st.warning("No commands loaded. Upload a YAML file or edit inline.")
        else:
            cmd_names = list(commands.keys())
            cmd_sel   = st.selectbox("Command ID", cmd_names, key="b_cmd")

            cmd_def  = commands.get(cmd_sel, {})
            arg_defs = cmd_def.get("args", [])
            variadic = cmd_def.get("variadic", False)

            arg_values = []
            epoch_warnings = []

            if arg_defs:
                st.markdown('<div class="section-label" style="margin-top:10px">Arguments</div>', unsafe_allow_html=True)
                for i, adef in enumerate(arg_defs):
                    aname = adef.get("name", f"arg{i}")
                    atype = adef.get("type", "str")
                    acol1, acol2 = st.columns([3, 1])
                    with acol2:
                        st.markdown(f'<div style="margin-top:28px"><span class="num-tag">{atype}</span></div>', unsafe_allow_html=True)
                    with acol1:
                        if atype == "int":
                            val = st.text_input(f"{aname}", value="0", key=f"arg_{i}", placeholder="int or 0x…")
                        elif atype == "float":
                            val = st.text_input(f"{aname}", value="0.0", key=f"arg_{i}", placeholder="float")
                        elif atype == "epoch_ms":
                            epoch_col, btn_col = st.columns([3, 1])
                            with btn_col:
                                st.markdown('<div style="margin-top:20px">', unsafe_allow_html=True)
                                use_now = st.button("NOW", key=f"now_{i}", help="Insert current epoch_ms")
                                st.markdown('</div>', unsafe_allow_html=True)
                            with epoch_col:
                                default_epoch = str(now_epoch_ms()) if use_now else "1767230528021"
                                val = st.text_input(f"{aname} (epoch_ms)", value=default_epoch, key=f"arg_{i}")
                            ok, info = validate_epoch_ms(val)
                            if ok:
                                epoch_warnings.append(f"✓ {aname}: {info}")
                            else:
                                epoch_warnings.append(f"✗ {aname}: {info}")
                        elif atype == "bool":
                            bool_val = st.selectbox(f"{aname}", ["true", "false", "1", "0"], key=f"arg_{i}")
                            val = bool_val
                        else:  # str
                            val = st.text_input(f"{aname}", value="", key=f"arg_{i}")
                    arg_values.append(val)

            if variadic:
                st.markdown('<div class="section-label" style="margin-top:8px">Extra Args (variadic)</div>', unsafe_allow_html=True)
                extra = st.text_input("Additional space-delimited args", value="", key="b_extra")
                if extra.strip():
                    arg_values.extend(extra.strip().split())

            for ew in epoch_warnings:
                if ew.startswith("✓"):
                    st.success(ew)
                else:
                    st.error(ew)

    st.markdown("---")
    build_col, copy_col = st.columns([4, 1])

    src_int   = NODE_MAP[src_sel]
    dst_int   = NODE_MAP[dst_sel]
    echo_int  = NODE_MAP[echo_sel]
    ptype_int = PTYPE_MAP[ptype_sel]

    packet_str = build_packet_string(src_int, dst_int, echo_int, ptype_int,
                                     cmd_sel if commands else "NONE", arg_values)

    packet_html = format_packet_html(
        src_sel, dst_sel, echo_sel, ptype_sel,
        cmd_sel if commands else "NONE", arg_values
    )

    with build_col:
        st.markdown('<div class="section-label">Generated Packet</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="packet-box">{packet_html}</div>', unsafe_allow_html=True)

    with copy_col:
        st.markdown('<div style="margin-top:24px">', unsafe_allow_html=True)
        if st.button("➕ Add to Queue", key="add_queue"):
            entry = build_queue_entry(src_int, dst_int, echo_int, ptype_int,
                                      cmd_sel if commands else "NONE", arg_values)
            st.session_state.tx_queue.append(entry)
            st.success(f"Queued ({len(st.session_state.tx_queue)})")
        if st.button("📋 Save to History", key="save_hist"):
            ts = datetime.now().strftime("%H:%M:%S")
            st.session_state.history.append({"ts": ts, "packet": packet_str})
            st.success("Saved!")
        st.markdown('</div>', unsafe_allow_html=True)

    # Breakdown table
    with st.expander("🔍 Packet Field Breakdown"):
        fields = {
            "SRC (orgn)":  f"{src_int} = {src_sel}",
            "DST (dest)":  f"{dst_int} = {dst_sel}",
            "ECHO":        f"{echo_int} = {echo_sel}",
            "PTYPE":       f"{ptype_int} = {ptype_sel}",
            "CMD":         cmd_sel if commands else "—",
            "ARGS":        " ".join(arg_values) if arg_values else "(none)",
        }
        for field, val in fields.items():
            fc1, fc2 = st.columns([2, 5])
            fc1.markdown(f'<span class="num-tag">{field}</span>', unsafe_allow_html=True)
            fc2.markdown(f'`{val}`')

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — RAW INPUT PARSER
# ══════════════════════════════════════════════════════════════════════════════
with tab_raw:
    st.markdown('<div class="section-label">Raw Packet Input</div>', unsafe_allow_html=True)
    st.info(
        "Accepts flexible formats:\n\n"
        "- `GS EPS NONE REQ SET_VOLTAGE 3.3`\n"
        "- `6 2 0 1 SET_VOLTAGE 3.3`\n"
        "- `2 0 1 SET_VOLTAGE 3.3` → SRC auto-set to 6 (GS)\n"
        "- `2 1 SET_VOLTAGE 3.3` → SRC=GS, ECHO=NONE auto-set"
    )

    raw_input = st.text_input(
        "Enter raw packet string",
        value="GS EPS NONE REQ SET_VOLTAGE 3.3",
        key="raw_input",
        placeholder="SRC DST ECHO PTYPE CMD [ARGS…]"
    )

    if raw_input.strip():
        parsed = parse_raw_input(raw_input, commands)
        if parsed:
            if parsed.get("errors"):
                for e in parsed["errors"]:
                    st.warning(e)

            if "cmd" in parsed:
                src_p   = parsed["src"]
                dst_p   = parsed["dst"]
                echo_p  = parsed["echo"]
                ptype_p = parsed["ptype"]
                cmd_p   = parsed["cmd"]
                args_p  = parsed["args_str"].split() if parsed["args_str"].strip() else []

                src_name   = NODE_MAP_INV.get(src_p, str(src_p))
                dst_name   = NODE_MAP_INV.get(dst_p, str(dst_p))
                echo_name  = NODE_MAP_INV.get(echo_p, str(echo_p))
                ptype_name = PTYPE_MAP_INV.get(ptype_p, str(ptype_p))

                packet_html_r = format_packet_html(
                    src_name, dst_name, echo_name, ptype_name, cmd_p, args_p
                )
                st.markdown('<div class="section-label" style="margin-top:16px">Parsed Packet</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="packet-box">{packet_html_r}</div>', unsafe_allow_html=True)

                packet_str_r = build_packet_string(src_p, dst_p, echo_p, ptype_p, cmd_p, args_p)

                rcol1, rcol2 = st.columns([3, 1])
                with rcol2:
                    if st.button("➕ Add to Queue", key="raw_add_queue"):
                        entry = build_queue_entry(src_p, dst_p, echo_p, ptype_p, cmd_p, args_p)
                        st.session_state.tx_queue.append(entry)
                        st.success(f"Queued ({len(st.session_state.tx_queue)})")
                    if st.button("📋 Save to History", key="raw_save"):
                        ts = datetime.now().strftime("%H:%M:%S")
                        st.session_state.history.append({"ts": ts, "packet": packet_str_r})
                        st.success("Saved!")

                with st.expander("🔍 Resolved Fields"):
                    rf = {
                        "SRC":   f"{src_p} ({src_name})",
                        "DST":   f"{dst_p} ({dst_name})",
                        "ECHO":  f"{echo_p} ({echo_name})",
                        "PTYPE": f"{ptype_p} ({ptype_name})",
                        "CMD":   cmd_p,
                        "ARGS":  " ".join(args_p) if args_p else "(none)",
                    }
                    for field, val in rf.items():
                        rc1, rc2 = st.columns([2, 5])
                        rc1.markdown(f'<span class="num-tag">{field}</span>', unsafe_allow_html=True)
                        rc2.markdown(f'`{val}`')

                # Validate args against schema if command known
                cmd_def_r  = commands.get(cmd_p, {})
                arg_defs_r = cmd_def_r.get("args", [])
                if arg_defs_r:
                    with st.expander("🧪 Argument Validation"):
                        for i, adef in enumerate(arg_defs_r):
                            aname = adef.get("name", f"arg{i}")
                            atype = adef.get("type", "str")
                            if i < len(args_p):
                                raw_val = args_p[i]
                                valid = True
                                note  = ""
                                try:
                                    if atype == "int":
                                        int(raw_val, 0)
                                    elif atype == "float":
                                        float(raw_val)
                                    elif atype == "epoch_ms":
                                        ok, info = validate_epoch_ms(raw_val)
                                        valid = ok
                                        note  = info
                                    elif atype == "bool":
                                        if raw_val.lower() not in ("true", "false", "1", "0", "yes", "no"):
                                            valid = False
                                except:
                                    valid = False

                                icon = "✅" if valid else "❌"
                                msg  = f"{icon} **{aname}** `{raw_val}` → `{atype}`"
                                if note:
                                    msg += f"  _{note}_"
                                st.markdown(msg)
                            else:
                                st.markdown(f"⚠️ **{aname}** → missing")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — TX QUEUE
# ══════════════════════════════════════════════════════════════════════════════
with tab_queue:
    q = st.session_state.tx_queue

    qcol1, qcol2 = st.columns([5, 1])
    with qcol1:
        st.markdown(
            f'<div class="section-label">{len(q)} command{"s" if len(q) != 1 else ""} queued</div>',
            unsafe_allow_html=True,
        )
    with qcol2:
        if q and st.button("🗑️ Clear All", key="q_clear"):
            st.session_state.tx_queue = []
            st.rerun()

    if not q:
        st.info("Queue is empty. Use '➕ Add to Queue' in the Build or Raw Input tabs.")
    else:
        for i, entry in enumerate(q):
            src_name_q   = NODE_MAP_INV.get(entry["src"],   str(entry["src"]))
            dst_name_q   = NODE_MAP_INV.get(entry["dest"],  str(entry["dest"]))
            echo_name_q  = NODE_MAP_INV.get(entry["echo"],  str(entry["echo"]))
            ptype_name_q = PTYPE_MAP_INV.get(entry["ptype"], str(entry["ptype"]))
            packet_html_q = format_packet_html(
                src_name_q, dst_name_q, echo_name_q, ptype_name_q,
                entry["cmd"], entry["args"].split() if entry["args"] else [],
            )
            qr1, qr2, qr3, qr4 = st.columns([1, 8, 1, 1])
            with qr1:
                st.markdown(
                    f'<div style="margin-top:14px"><span class="num-tag">{i + 1}</span></div>',
                    unsafe_allow_html=True,
                )
            with qr2:
                st.markdown(
                    f'<div class="packet-box" style="padding:10px 16px;font-size:0.9rem">{packet_html_q}</div>',
                    unsafe_allow_html=True,
                )
            with qr3:
                if st.button("↑", key=f"q_up_{i}", disabled=(i == 0), help="Move up"):
                    q[i - 1], q[i] = q[i], q[i - 1]
                    st.rerun()
                if st.button("↓", key=f"q_dn_{i}", disabled=(i == len(q) - 1), help="Move down"):
                    q[i + 1], q[i] = q[i], q[i + 1]
                    st.rerun()
            with qr4:
                if st.button("🗑️", key=f"q_del_{i}", help="Remove"):
                    st.session_state.tx_queue.pop(i)
                    st.rerun()

    st.markdown("---")
    st.markdown('<div class="section-label">Export for MAV_TX2</div>', unsafe_allow_html=True)

    if not _PROTOCOL_OK:
        st.warning("mav_gss_lib not importable — raw_cmd fields will be empty. Ensure MAVERIC_GSS/ is present.")

    if q:
        queue_lines = [
            build_packet_string(
                e["src"], e["dest"], e["echo"], e["ptype"],
                e["cmd"], e["args"].split() if e["args"] else [],
            )
            for e in q
        ]
        export_data = "\n".join(queue_lines) + "\n"

        _default_queue_path = os.path.join(_GSS_PATH, "logs", ".pending_queue.txt")

        ec1, ec2 = st.columns(2)
        with ec1:
            st.download_button(
                "⬇️ Download pending_queue.txt",
                data=export_data,
                file_name="pending_queue.txt",
                mime="text/plain",
                help="Download plain-text queue file readable by MAV_TX2",
            )
        with ec2:
            queue_path = st.text_input("Write directly to queue file", value=_default_queue_path, key="queue_path")
            if st.button("📤 Write to queue file", key="write_queue"):
                try:
                    os.makedirs(os.path.dirname(os.path.abspath(queue_path)), exist_ok=True)
                    with open(queue_path, "w") as _qf:
                        _qf.write(export_data)
                    st.success(f"Written {len(q)} command{'s' if len(q) != 1 else ''} → {queue_path}")
                except Exception as _e:
                    st.error(f"Write failed: {_e}")
    else:
        st.info("Add commands to the queue to enable export.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — HISTORY
# ══════════════════════════════════════════════════════════════════════════════
with tab_history:
    st.markdown('<div class="section-label">Command History</div>', unsafe_allow_html=True)
    if not st.session_state.history:
        st.info("No packets saved yet. Build or parse a packet and click 'Save to History'.")
    else:
        hcol1, hcol2 = st.columns([5, 1])
        with hcol2:
            if st.button("🗑️ Clear All"):
                st.session_state.history = []
                st.rerun()

        for i, entry in enumerate(reversed(st.session_state.history)):
            idx = len(st.session_state.history) - 1 - i
            hc1, hc2 = st.columns([5, 1])
            with hc1:
                st.markdown(
                    f'<div class="history-item">'
                    f'<span style="color:#2a6090;margin-right:12px">[{entry["ts"]}]</span>'
                    f'{entry["packet"]}'
                    f'</div>',
                    unsafe_allow_html=True
                )
            with hc2:
                if st.button("🗑️", key=f"del_{idx}"):
                    st.session_state.history.pop(idx)
                    st.rerun()

        st.markdown("---")
        st.markdown('<div class="section-label">Export</div>', unsafe_allow_html=True)
        export_text = "\n".join(e["packet"] for e in st.session_state.history)
        st.download_button(
            "⬇️ Download as .txt",
            data=export_text,
            file_name=f"maveric_commands_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
        )
        export_json = json.dumps(st.session_state.history, indent=2)
        st.download_button(
            "⬇️ Download as .json",
            data=export_json,
            file_name=f"maveric_commands_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
        )
