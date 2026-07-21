#!/usr/bin/env python3
"""
MUD Connection Manager - Persistent netcat connection with structured output parsing
"""

import socket
import json
import argparse
import time
import re
import os
from datetime import datetime
from pathlib import Path
import tempfile
import sys

# Session storage in temp directory
SESSIONS_DIR = Path(tempfile.gettempdir()) / "mud_sessions"
SESSIONS_DIR.mkdir(exist_ok=True)

# Per-character memory files live in data/players/, one <login>.md per known
# character (see data/players/TEMPLATE.md). Resolved relative to this script
# so it works regardless of the caller's cwd.
PLAYERS_DIR = Path(__file__).resolve().parent.parent / "data" / "players"

# tbaMUD prompts don't share one end character: the login sequence ends in
# "?" or ":" while the in-game prompt ends in ">" — so reading-until-quiet is
# used instead of matching a fixed marker (see MUDConnection._read_response).
ANSI_ESCAPE_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
CONTROL_CHAR_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')


def clean_output(raw_bytes):
    """Decode raw telnet bytes and strip ANSI color codes / control bytes.

    Downstream parsing (and anything written into the memory files) works on
    this cleaned text rather than the raw bytes, which are full of color
    codes and stray telnet negotiation bytes that survive utf-8 decoding.
    """
    text = raw_bytes.decode('utf-8', errors='ignore')
    text = ANSI_ESCAPE_RE.sub('', text)
    text = CONTROL_CHAR_RE.sub('', text)
    return text


class MUDParser:
    """Parse MUD output into structured format"""

    @staticmethod
    def parse_inventory(output):
        """Extract inventory from output"""
        items = []
        weight = None

        # Look for inventory section
        if "You are carrying" in output or "carrying the following" in output:
            lines = output.split('\n')
            in_inventory = False
            for line in lines:
                if "carrying" in line.lower():
                    in_inventory = True
                    continue
                if in_inventory:
                    if line.strip() == "" or "Total weight" in line:
                        break
                    # Extract item names (usually indented)
                    item = line.strip()
                    if item and not item.startswith('>'):
                        items.append(item)
                    # Extract weight if present
                    if "Total weight" in line or "Weight:" in line:
                        match = re.search(r'(\d+)/(\d+)', line)
                        if match:
                            weight = f"{match.group(1)}/{match.group(2)}"

        return {"items": items, "weight": weight} if items or weight else None

    @staticmethod
    def parse_character_stats(output):
        """Extract character stats (health, mana, level, etc.)

        Two real formats confirmed by playing on this tbaMUD server (neither
        looks like the generic "Hp: 100/100" pattern a lot of MUDs use, so both
        are matched explicitly):
          - the prompt line, on every command's response: "24H 100M 85V"
            (current values only, no max)
          - `score` output: "You have 24(24) hit, 100(100) mana and 85(85)
            movement points." ... "This ranks you as Queen the Swordpupil
            (level 1)." ... "You have 124 exp, 10 gold coins, and 0
            questpoints." ... "You need 1876 exp to reach your next level."
        """
        stats = {}

        # Generic "Hp: 100/100" style, in case a different area/command uses it
        hp_match = re.search(r'(?:Hp|Hit points?):\s*(\d+)/(\d+)', output, re.IGNORECASE)
        if hp_match:
            stats['health'] = int(hp_match.group(1))
            stats['max_health'] = int(hp_match.group(2))

        mana_match = re.search(r'(?:Ma|Mana):\s*(\d+)/(\d+)', output, re.IGNORECASE)
        if mana_match:
            stats['mana'] = int(mana_match.group(1))
            stats['max_mana'] = int(mana_match.group(2))

        # score output: "You have 24(24) hit, 100(100) mana and 85(85) movement points."
        score_match = re.search(
            r'You have (\d+)\((\d+)\) hit,\s*(\d+)\((\d+)\) mana and\s*(\d+)\((\d+)\) movement points',
            output, re.IGNORECASE)
        if score_match:
            stats['health'] = int(score_match.group(1))
            stats['max_health'] = int(score_match.group(2))
            stats['mana'] = int(score_match.group(3))
            stats['max_mana'] = int(score_match.group(4))
            stats['movement'] = int(score_match.group(5))
            stats['max_movement'] = int(score_match.group(6))

        # prompt line: "24H 100M 85V" — current values only, no max
        prompt_match = re.search(r'(\d+)H\s+(\d+)M\s+(\d+)V', output)
        if prompt_match:
            stats.setdefault('health', int(prompt_match.group(1)))
            stats.setdefault('mana', int(prompt_match.group(2)))
            stats.setdefault('movement', int(prompt_match.group(3)))

        # Level pattern: "Level: 5" or "This ranks you as ... (level 1)."
        level_match = re.search(r'Level:\s*(\d+)', output, re.IGNORECASE)
        if not level_match:
            level_match = re.search(r'\(level (\d+)\)', output, re.IGNORECASE)
        if level_match:
            stats['level'] = int(level_match.group(1))

        # Experience: "Exp: 1000" or "You have 124 exp, 10 gold coins, and 0 questpoints."
        exp_match = re.search(r'(?:Exp|Experience):\s*(\d+)', output, re.IGNORECASE)
        if not exp_match:
            exp_match = re.search(r'You have (\d+) exp,\s*(\d+) gold coins', output, re.IGNORECASE)
            if exp_match:
                stats['gold'] = int(exp_match.group(2))
        if exp_match:
            stats['experience'] = int(exp_match.group(1))

        exp_needed_match = re.search(r'need (\d+) exp to reach your next level', output, re.IGNORECASE)
        if exp_needed_match:
            stats['exp_to_next_level'] = int(exp_needed_match.group(1))

        return stats if stats else None

    @staticmethod
    def parse_room(output):
        """Extract room information (name, description, exits, NPCs, items)"""
        room = {}
        lines = output.split('\n')

        # Room name is usually the first line (in caps or special format)
        if lines:
            first_line = lines[0].strip()
            if first_line and len(first_line) > 3:
                room['name'] = first_line

        # Extract exits: [Exits: north, south, east] or [ Exits: n e s w ]
        exits_match = re.search(r'\[\s*Exits:\s*([^\]]+)\]', output, re.IGNORECASE)
        if exits_match:
            exits_str = exits_match.group(1)
            room['exits'] = [e.strip() for e in re.split(r'[,\s]+', exits_str) if e.strip()]

        # Look for NPCs (usually listed with @ symbol or specific format)
        # This is a heuristic - different MUDs format differently
        npc_pattern = r'^\s*\[.*\]\s+(.+?)(?:\s+is here|$)'
        npcs = re.findall(npc_pattern, output, re.MULTILINE | re.IGNORECASE)
        if npcs:
            room['npcs'] = npcs

        # Extract items (usually lines with "lying here" or similar)
        item_pattern = r'(.+?)\s+(?:is lying|are lying|here)'
        items = re.findall(item_pattern, output, re.IGNORECASE)
        if items:
            room['items'] = items

        return room if room else None

    @staticmethod
    def parse_combat_state(output):
        """Extract combat information"""
        combat = {'in_combat': False}

        # Check for combat indicators
        if any(keyword in output.lower() for keyword in ['you hit', 'you miss', 'begins to combat', 'fighting']):
            combat['in_combat'] = True

            # Try to extract target
            target_match = re.search(r'(?:You attack|fighting|combat with)\s+(.+?)(?:\s+for|\s+and|\.|$)', output, re.IGNORECASE)
            if target_match:
                combat['target'] = target_match.group(1).strip()

        return combat if combat.get('in_combat') else None

    @classmethod
    def parse_output(cls, output, command):
        """Main parsing function - returns structured state"""
        parsed = {}

        # Try to extract each component
        room = cls.parse_room(output)
        if room:
            parsed['current_room'] = room

        stats = cls.parse_character_stats(output)
        if stats:
            parsed['character'] = stats

        inventory = cls.parse_inventory(output)
        if inventory:
            parsed['inventory'] = inventory

        combat = cls.parse_combat_state(output)
        if combat:
            parsed['combat_state'] = combat

        return parsed


class MUDConnection:
    """Manages persistent MUD connection via netcat"""

    def __init__(self, host='localhost', port=4000, timeout=8):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.socket = None
        self.connected = False
        self.last_response = ""
        self.character_name = None

    def connect(self):
        """Establish connection to MUD (does not read the banner — login() does)"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.host, self.port))
            self.connected = True
            return True
        except Exception as e:
            self.connected = False
            raise Exception(f"Connection failed: {e}")

    def disconnect(self):
        """Close connection"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        self.connected = False

    def _read_response(self, quiet_period=1.5):
        """Read until the server stops sending data for `quiet_period` seconds.

        tbaMUD prompts don't share a fixed end character (login prompts end in
        "?" or ":", the in-game prompt ends in ">"), so a fixed end_marker
        misses the login sequence entirely. Waiting for a quiet gap after data
        stops arriving works regardless of which prompt is showing.

        quiet_period must be generous: the initial banner arrives in two
        bursts ("Attempting to Detect Client..." then, after the server's
        telnet option negotiation, the rest of the banner + name prompt) with
        a gap around a second between them. A short quiet_period returns after
        the first burst, sending the username into the negotiation gap where
        it's lost — which silently misdirects login into creating a new
        character instead of reaching the intended one.
        """
        response = b""
        start_time = time.time()
        self.socket.settimeout(quiet_period)
        try:
            while True:
                if time.time() - start_time > self.timeout:
                    break
                try:
                    chunk = self.socket.recv(4096)
                    if not chunk:
                        raise ConnectionError("Connection closed by server")
                    response += chunk
                except socket.timeout:
                    if response:
                        break
                    continue
        finally:
            self.socket.settimeout(self.timeout)

        if not response:
            raise TimeoutError(f"No response from MUD within {self.timeout}s")

        self.last_response = clean_output(response)
        return self.last_response

    def send_command(self, command):
        """Send a command and get response"""
        if not self.connected:
            raise ConnectionError("Not connected to MUD")

        try:
            self.socket.sendall((command + '\n').encode('utf-8'))
            response = self._read_response()
            return response
        except Exception as e:
            self.connected = False
            raise Exception(f"Command execution failed: {e}")

    def login(self, username, password):
        """Log in to MUD"""
        try:
            # Initial response should ask for username
            initial = self._read_response()

            # Send username
            response = self.send_command(username)

            # Send password
            response = self.send_command(password)

            self.character_name = username
            return response
        except Exception as e:
            raise Exception(f"Login failed: {e}")


class SessionManager:
    """Manage multiple MUD sessions"""

    @staticmethod
    def create_session_id():
        """Generate unique session ID"""
        import uuid
        return str(uuid.uuid4())[:8]

    @staticmethod
    def save_session(session_id, data):
        """Save session data to disk"""
        session_file = SESSIONS_DIR / f"{session_id}.json"
        with open(session_file, 'w') as f:
            json.dump(data, f)

    @staticmethod
    def load_session(session_id):
        """Load session data from disk"""
        session_file = SESSIONS_DIR / f"{session_id}.json"
        if not session_file.exists():
            return None
        with open(session_file, 'r') as f:
            return json.load(f)

    @staticmethod
    def delete_session(session_id):
        """Delete session data"""
        session_file = SESSIONS_DIR / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()


def format_response(success, command, raw_output, parsed_state=None, error=None):
    """Format response as JSON"""
    response = {
        "success": success,
        "command": command,
        "raw_output": raw_output.strip(),
        "parsed_state": parsed_state or {},
        "error": error,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    return response


def main():
    parser = argparse.ArgumentParser(description='MUD Connection Manager')
    parser.add_argument('--action', required=True,
                        choices=['init', 'execute', 'batch', 'close', 'status', 'list-players'],
                        help='Action to perform')
    parser.add_argument('--session-id', help='Session ID for execute/batch/close actions')
    parser.add_argument('--login', help='Character username')
    parser.add_argument('--password', help='Character password')
    parser.add_argument('--command', help='Command to execute (execute action)')
    parser.add_argument('--commands', nargs='+', help='Commands to run in sequence over one login (batch action)')
    parser.add_argument('--host', default='localhost', help='MUD host (default: localhost)')
    parser.add_argument('--port', type=int, default=4000, help='MUD port (default: 4000)')

    args = parser.parse_args()

    try:
        if args.action == 'init':
            # Initialize new session
            if not args.login or not args.password:
                print(json.dumps(format_response(False, 'init', '', error='login and password required')))
                return

            conn = MUDConnection(args.host, args.port)
            conn.connect()
            try:
                login_response = conn.login(args.login, args.password)
                # Login alone (or a reconnect) doesn't repeat the room description,
                # so send an explicit look to get real starting-room state.
                look_response = conn.send_command('look')
            finally:
                conn.disconnect()
            combined_output = (login_response + '\n' + look_response).strip()

            # Parse initial state
            parsed = MUDParser.parse_output(combined_output, 'login')

            # Create session. Password is stored because each `execute` call is a
            # fresh process with no access to the live socket from `init` — it has
            # to reconnect and log back in itself (see the execute branch below).
            session_id = SessionManager.create_session_id()
            SessionManager.save_session(session_id, {
                'character': args.login,
                'password': args.password,
                'host': args.host,
                'port': args.port,
                'created': datetime.utcnow().isoformat()
            })

            # Return session info with parsed output
            response = {
                "success": True,
                "session_id": session_id,
                "character": args.login,
                "raw_output": combined_output,
                "parsed_state": parsed,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            print(json.dumps(response, indent=2))

        elif args.action == 'execute':
            # Execute command
            if not args.session_id or not args.command:
                print(json.dumps(format_response(False, 'execute', '', error='session-id and command required')))
                return

            session = SessionManager.load_session(args.session_id)
            if not session:
                print(json.dumps(format_response(False, args.command, '', error='Session not found')))
                return

            # Each execute is a new process, so there's no live socket left over
            # from init/the previous execute — reconnect and log back in first.
            # tbaMUD treats this as a reconnect to the same live character rather
            # than a duplicate login, so game state (position, HP, etc.) carries
            # over on the server side even though the Python connection doesn't.
            conn = MUDConnection(session['host'], session['port'])
            conn.connect()
            try:
                conn.login(session['character'], session['password'])
                response = conn.send_command(args.command)
                parsed = MUDParser.parse_output(response, args.command)
                result = format_response(True, args.command, response, parsed)
            except Exception as e:
                result = format_response(False, args.command, '', error=str(e))
            finally:
                conn.disconnect()

            print(json.dumps(result, indent=2))

        elif args.action == 'batch':
            # Run several commands over a single login instead of paying the
            # reconnect+login round-trip for each one — much faster for
            # exploring several rooms or checking several character sheets in
            # one go than repeated `execute` calls would be.
            if not args.session_id or not args.commands:
                print(json.dumps(format_response(False, 'batch', '', error='session-id and commands required')))
                return

            session = SessionManager.load_session(args.session_id)
            if not session:
                print(json.dumps(format_response(False, 'batch', '', error='Session not found')))
                return

            conn = MUDConnection(session['host'], session['port'])
            conn.connect()
            results = []
            try:
                conn.login(session['character'], session['password'])
                for cmd in args.commands:
                    try:
                        response = conn.send_command(cmd)
                        parsed = MUDParser.parse_output(response, cmd)
                        results.append(format_response(True, cmd, response, parsed))
                    except Exception as e:
                        results.append(format_response(False, cmd, '', error=str(e)))
                        break
            except Exception as e:
                results.append(format_response(False, 'login', '', error=str(e)))
            finally:
                conn.disconnect()

            print(json.dumps({
                "success": all(r['success'] for r in results) if results else False,
                "action": "batch",
                "results": results,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }, indent=2))

        elif args.action == 'close':
            # Close session
            if not args.session_id:
                print(json.dumps(format_response(False, 'close', '', error='session-id required')))
                return

            SessionManager.delete_session(args.session_id)
            response = {
                "success": True,
                "action": "close",
                "session_id": args.session_id,
                "message": "Session closed",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            print(json.dumps(response, indent=2))

        elif args.action == 'status':
            # List active sessions
            sessions = list(SESSIONS_DIR.glob("*.json"))
            active_sessions = []
            for session_file in sessions:
                try:
                    with open(session_file, 'r') as f:
                        data = json.load(f)
                        active_sessions.append({
                            'session_id': session_file.stem,
                            'character': data.get('character'),
                            'created': data.get('created')
                        })
                except:
                    pass

            response = {
                "success": True,
                "action": "status",
                "active_sessions": active_sessions,
                "count": len(active_sessions),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            print(json.dumps(response, indent=2))

        elif args.action == 'list-players':
            # Known characters are whichever data/players/<login>.md files
            # exist — there's no hardcoded roster, so this is how callers
            # (and the agent) discover who's available to play without
            # guessing a login.
            known = []
            if PLAYERS_DIR.exists():
                known = sorted(
                    f.stem for f in PLAYERS_DIR.glob("*.md")
                    if f.stem.lower() != 'template'
                )

            response = {
                "success": True,
                "action": "list-players",
                "players": known,
                "count": len(known),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            print(json.dumps(response, indent=2))

    except Exception as e:
        print(json.dumps(format_response(False, args.action, '', error=str(e))))
        sys.exit(1)


if __name__ == '__main__':
    main()
