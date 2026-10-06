"""
Comprehensive Rules Compiler for RL MUD Colorizer (v5)
Enriched with patterns from Velkyn (caster), Thildarg (classic client),
and community standard RL color formatting.
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RULES_FILE = BASE_DIR / "rules.json"

# ---------------------------------------------------------------------------
# PREPROCESS LAYER (shared by engine.py and webapp/engine.js)
#
# Runs on the raw text BEFORE colorizing: removes login/credentials and
# client-specific status noise so the colorizing rules only see game output.
# Patterns use the regex subset that behaves identically in Python `re` and
# JavaScript RegExp: anchors ^ $, classes, groups, alternation, quantifiers.
# No lookbehind, no \Z, no inline flags; prefer [ \t] over \s. They are applied
# with "search" semantics (always anchor with ^ when you mean line start).
#
# Rule kinds (evaluated in list order; the first rule that consumes a line wins,
# except `rewrite`, which edits the line and lets later rules see the result):
#   drop             {pattern}                          drop one matching line
#   drop_block       {start, end, include_end, max_lines}
#                    drop from a `start` line through the `end` line (end kept
#                    unless include_end). Only fires when `end` is found within
#                    max_lines lines, so a truncated fragment is never swallowed.
#   drop_after       {pattern, until, include_until, max_lines, echo}
#                    drop the matching line and every following line up to (not
#                    including, unless include_until) a line matching `until`;
#                    at most max_lines (default 8) lines. Used for echoed input.
#                    With `echo`, also stop at the first non-blank line that does
#                    not match it, so a fragment without `until` keeps its game text.
#   dedupe_on_change {pattern, scope_id, key_group | key}
#                    keep the line only when its key differs from the last kept
#                    line of the same scope_id. Key = capture group N
#                    (key_group), a template such as "$1|$2" (key), or the whole
#                    line by default. Trailing blanks are ignored. State starts
#                    empty for every input.
#   rewrite          {pattern, replace}                 replace uses $1..$9
#   drop_closer      {group, pattern}
#                    drop `pattern` (e.g. the lone prompt) when it immediately
#                    follows a run of lines of `group` (drop/dedupe rules with
#                    the same "group") that kept nothing.
#   drop_before      {pattern, candidate, max_lines, login}
#                    when `pattern` matches, remove up to max_lines already-emitted
#                    lines right before it (blank lines skipped) that match
#                    `candidate`; the matching line itself is processed normally.
#                    Catches type-ahead credentials that precede their own prompt.
#                    Skipped when a login rule fired on the 2 previous lines (those
#                    lines were already consumed).
#   drop_secret      {window}
#                    defense in depth: drop a line exactly equal to a token that was
#                    removed as a login echo (drop_after `record`, drop_before
#                    candidates) but only within `window` lines after a rule flagged
#                    "login": true fired, so gameplay commands elsewhere are safe.
# Any rule may carry "clients": [...]; without it the rule is client-agnostic.
# Client detection: the client whose "signatures" match the most lines wins
# (ties: first declared); no match -> only client-agnostic rules apply.
# ---------------------------------------------------------------------------
PREPROCESS_DATA = {
    "clients": [
        {
            "id": "vipmud",
            "label": "VIPMud",
            "signatures": [
                # Only signatures exclusive to VIPMud logs. "SL:", "PL:", "Pieles:" and
                # "Imágenes:" also appear in Mudlet logs (custom prompts), so they must
                # not trigger detection or Mudlet output would lose those lines.
                r"^Pv:\d+\\\d+ Pe:\d+\\\d+",
                r"^Jgd:",
                r"^LPmud version:",
            ],
        },
        {
            "id": "mudlet",
            "label": "Mudlet",
            "signatures": [
                r"^Pvs?:[ \t]*\d+[ \t]+Pe:[ \t]*\d+",
            ],
        },
    ],
    "rules": [
        # --- Login region: credentials must never reach the output (client-agnostic) ---
        # Type-ahead: echoed name/password can appear BEFORE the prompt that reveals
        # them (log starts mid-login, or typed ahead of the banner). Look backwards.
        {
            "id": "login_echo_before_recover_hint",
            "kind": "drop_before",
            "pattern": r"^Escribe \"recuperar clave\"",
            "candidate": r"^\S{1,40}$",
            "max_lines": 3,
            "login": True,
        },
        {
            "id": "login_echo_before_banner",
            "kind": "drop_before",
            "pattern": r"^LPmud version:",
            "candidate": r"^\S{1,40}$",
            "max_lines": 3,
            "login": True,
        },
        {
            "id": "login_echo_before_name_prompt",
            "kind": "drop_before",
            "pattern": r"^Introduce el nombre de tu personaje:",
            "candidate": r"^\S{1,40}$",
            "max_lines": 2,
            "login": True,
        },
        {
            "id": "login_banner",
            "login": True,
            "kind": "drop_block",
            "start": r"^LPmud version:",
            "end": r"^Introduce el nombre de tu personaje:",
            "include_end": False,
            "max_lines": 90,
        },
        {
            "id": "login_name_prompt",
            "login": True,
            "kind": "drop_after",
            "pattern": r"^Introduce el nombre de tu personaje:",
            "until": r"^(?:Escribe \"recuperar clave\"|Introduce la clave de tu ficha)",
            "include_until": False,
            "record": r"^\S{1,40}$",
            "echo": r"^\S{1,40}$",
            "max_lines": 8,
        },
        {
            "id": "login_recover_hint",
            "login": True,
            "kind": "drop",
            "pattern": r"^Escribe \"recuperar clave\"",
        },
        {
            "id": "login_password_prompt",
            "login": True,
            "kind": "drop_after",
            "pattern": r"^Introduce la clave de tu ficha o de tu cuenta",
            "until": r"^(?:[ \t]*Los Dioses te dan la bienvenida|Tu personaje ya se encuentra|LPmud version:|Introduce el nombre de tu personaje:)",
            "include_until": False,
            "record": r"^\S{1,40}$",
            "echo": r"^\S{1,40}$",
            "max_lines": 6,
        },
        {
            "id": "login_motd",
            "login": True,
            "kind": "drop_block",
            "start": r"^[ \t]*Los Dioses te dan la bienvenida a sus Reinos de Leyenda",
            "end": r"^\[.+ orbita a Eirea.*\][ \t]*$",
            "include_end": True,
            "max_lines": 150,
        },
        {
            "id": "login_secret_echo",
            "kind": "drop_secret",
            "window": 6,
        },
        {
            "id": "login_last_connection",
            "login": True,
            "kind": "drop",
            "pattern": r"^- Tu última conexión fue el .* desde la IP ",
        },

        # --- VIPMud status block (Pv/SL/PL/Jgd/Imágenes/Pieles + closing prompt) ---
        {
            "id": "vip_status_pv",
            "kind": "dedupe_on_change",
            "clients": ["vipmud"],
            "group": "status",
            "scope_id": "pv",
            "pattern": r"^Pv:\d+\\\d+ Pe:\d+\\\d+ Xp:\d+",
        },
        {
            "id": "vip_status_sl",
            "kind": "drop",
            "clients": ["vipmud"],
            "group": "status",
            "pattern": r"^SL:",
        },
        {
            "id": "vip_status_pl",
            "kind": "drop",
            "clients": ["vipmud"],
            "group": "status",
            "pattern": r"^PL:",
        },
        {
            "id": "vip_status_jgd",
            "kind": "drop",
            "clients": ["vipmud"],
            "group": "status",
            "pattern": r"^Jgd:",
        },
        {
            "id": "vip_status_imagenes",
            "kind": "dedupe_on_change",
            "clients": ["vipmud"],
            "group": "status",
            "scope_id": "imagenes",
            "pattern": r"^Imágenes:(\d+)[ \t]*$",
            "key_group": 1,
        },
        {
            "id": "vip_status_pieles",
            "kind": "dedupe_on_change",
            "clients": ["vipmud"],
            "group": "status",
            "scope_id": "pieles",
            "pattern": r"^Pieles:(\d+)[ \t]*$",
            "key_group": 1,
        },
        {
            "id": "vip_status_closer",
            "kind": "drop_closer",
            "clients": ["vipmud"],
            "group": "status",
            "pattern": r"^[>\]][ \t]*$",
        },
    ],
}


RULES_DATA = {
    "theme": {
        "bg": "#000000",
        "default_fg": "#c0c0c0",
        "font_family": "'Bitstream Vera Sans Mono', 'Courier New', monospace"
    },
    "colors": {
        "white": "#ffffff",
        "silver": "#c0c0c0",
        "gray": "#808080",
        "dark_gray": "#555555",
        "red": "#ff4444",
        "dark_red": "#aa0000",
        "bright_red": "#ff0000",
        "green": "#00ff00",
        "dark_green": "#008000",
        "yellow": "#ffff00",
        "olive": "#717100",
        "blue": "#0800ff",
        "dark_blue": "#0000aa",
        "cyan": "#00ffff",
        "dark_cyan": "#008080",
        "magenta": "#ff00ff"
    },
    "race_colors": {
        "elfo": "#008000",
        "elf": "#008000",
        "melf": "#008000",
        "semi-elfo": "#008000",
        "s-e": "#008000",
        "enano": "#808000",
        "ena": "#808000",
        "kobold": "#800000",
        "kob": "#800000",
        "drow": "#808080",
        "mdro": "#808080",
        "semi-drow": "#808080",
        "s-d": "#808080",
        "duergar": "#800080",
        "duer": "#800080",
        "drg": "#800080",
        "goblin": "#00ff00",
        "gob": "#00ff00",
        "gnomo": "#00ffff",
        "gno": "#00ffff",
        "humano": "#ffff00",
        "hum": "#ffff00",
        "gnoll": "#ff0000",
        "gnl": "#ff0000",
        "gnol": "#ff0000",
        "halfling": "#ff00ff",
        "hal": "#ff00ff",
        "hlf": "#ff00ff",
        "lagarto": "#0000ff",
        "hombre-lagarto": "#0000ff",
        "hlag": "#0000ff",
        "lag": "#0000ff",
        "minotauro": "#c0c0c0",
        "min": "#c0c0c0",
        "mino": "#c0c0c0",
        "orco": "#ffffff",
        "semi-orco": "#ffffff",
        "orc": "#ffffff",
        "s-o": "#ffffff",
        "ogro-mago": "#008080",
        "ogro": "#008080",
        "org": "#008080",
        "orgo": "#008080"
    },
    "room_colors": {},
    "preprocess": PREPROCESS_DATA,
    "rules": [
        # --- 1. PROMPTS & HEALTH DELTAS ---
        {
            "id": "prompt_vitals",
            "category": "prompt",
            "priority": 9,
            "pattern": r"^(\s*)(Pvs?:\s*)(\d+)(\()(\d+)(\)\s+Pe:\s*\d+\(\d+\)\s+Fe:\s*)(\d+)(.*)$",
            "type": "composite_prompt_vitals"
        },
        {
            "id": "prompt_full",
            "category": "prompt",
            "priority": 10,
            "pattern": r"^(\s*)(Pvs?:\s*(?:\d+(?:[/(\\]\d+\)?)?)?)(?:(\s*)\(([+-]?\d+)\))?(\s*Pe:\s*\d+(?:[/(\\]\d+\)?)?)?(?:(\s*)\(([+-]?\d+)\))?(.*)$",
            "type": "composite_prompt_extended"
        },
        {
            "id": "prompt_pe_xp",
            "category": "prompt",
            "priority": 10,
            "pattern": r"^(\s*)(Pe:\s*\d+(?:[/(\\]\d+\)?)?)(\s*\([+-]?\d+\))?(.*)$",
            "replace": r'$1<span style="color: #008000;">$2$3$4</span>'
        },
        {
            "id": "prompt_hp_delta",
            "category": "prompt",
            "priority": 11,
            "pattern": r"^(\s*HP:\s*)([+-]?\d+)\s*$",
            "type": "composite_hp_delta"
        },

        # --- 1b. COMBAT / SKILL LINES WITH A LEADING MARKER ---
        # The reference colors only the marker (`#` our attacks, `*` incoming attacks,
        # `+` skill preparation); the body stays default. The marker color encodes the
        # kind of event: first matching category wins, otherwise `color`.
        {
            "id": "marker_hash",
            "category": "combat",
            "priority": 13,
            "pattern": r"^(#)(\s.*)$",
            "type": "composite_marker",
            "color": "#008000",
            "categories": [
                {"pattern": r"esquiv|parar|bloquea|desaparece al golpearlo|rebota en|No logras acertar|Intentas", "color": "#800080"}
            ]
        },
        {
            "id": "marker_star",
            "category": "combat",
            "priority": 13,
            "pattern": r"^(\*)(\s.*)$",
            "type": "composite_marker",
            "color": "#800000",
            "categories": [
                {"pattern": r"esquiv|dejarse intimidar", "color": "#800080"},
                {"pattern": r"^\s¡?(?:\d+ misiles|Un rayo|Una esfera de energía|El aire se congela|El rayo de)", "color": "#0000ff"},
                {"pattern": r"^\s¡?El cielo ruge", "color": "#008080"},
                {"pattern": r"malherido,|Te tambaleas cuando|Un brutal golpe|surge de alguna parte", "color": "#ff0000"}
            ]
        },
        {
            "id": "marker_plus",
            "category": "skill",
            "priority": 13,
            "pattern": r"^(\+)(\s.*)$",
            "type": "composite_marker",
            "color": "#ffff00",
            "categories": []
        },

        # --- 2. SYSTEM EXP, GLORY, LOGROS & LOCKS (GRAY BASE + HIGHLIGHTED NUMBERS) ---
        {
            "id": "system_glory",
            "category": "system",
            "priority": 21,
            "pattern": r"^(?:[>\]]\s*)?(\[Obtienes )(\d+)( puntos de gloria\])\s*$",
            "replace": r'<span style="color: #c0c0c0;">$1</span><span style="color: #ffff00; font-weight: bold;">$2</span><span style="color: #c0c0c0;">$3</span>'
        },
        {
            "id": "system_oficio",
            "category": "system",
            "priority": 22,
            "pattern": r"^(?:[>\]]\s*)?(\[Obtienes )(\d+)( puntos? de oficio\])\s*$",
            "replace": r'<span style="color: #c0c0c0;">$1</span><span style="color: #ffffff; font-weight: bold;">$2</span><span style="color: #c0c0c0;">$3</span>'
        },
        {
            "id": "system_logro",
            "category": "system",
            "priority": 23,
            "pattern": r"^(?:[>\]]\s*)?(\[Obtienes el logro ')('?[^']+?'?)(' \([^)]+\)\])\s*$",
            "replace": r'<span style="color: #c0c0c0;">$1</span><span style="color: #ffff00; font-weight: bold;">$2</span><span style="color: #c0c0c0;">$3</span>'
        },
        {
            "id": "system_lock",
            "category": "system",
            "priority": 24,
            "pattern": r"^(?:[>\]]\s*)?(\[El bloqueo )('?[^']+?'?)(\s+termina\])\s*$",
            "replace": r'<span style="color: #c0c0c0;">$1</span><span style="color: #ffff00;">$2</span><span style="color: #c0c0c0;">$3</span>'
        },
        {
            "id": "system_faith",
            "category": "system",
            "priority": 25,
            "pattern": r"^(?:[>\]]\s*)?(\[Tu fe en .+? ha (?:disminuido|aumentado) en )(\d+)( puntos\])\s*$",
            "replace": r'<span style="color: #c0c0c0;">$1</span><span style="color: #ffffff; font-weight: bold;">$2</span><span style="color: #c0c0c0;">$3</span>'
        },
        {
            "id": "system_tiradas",
            "category": "system",
            "priority": 26,
            "pattern": r"^(?:[>\]]\s*)?(\[)(Tiradas)(\]:?\s+.*?\s+Tirada:\s+\d+\s*\()((?:Éxito|Fallo|Exito))(\)\.?)\s*$",
            "type": "composite_tirada"
        },
        {
            "id": "system_info_tags",
            "category": "system",
            "priority": 27,
            "pattern": r"^(?:[>\]]\s*)?(\[)(INFO|AYUDA|ADVERTENCIA|ERROR)(\]:\s*)(.*)$",
            "type": "composite_info"
        },
        {
            "id": "system_command_queue",
            "category": "system",
            "priority": 28,
            "pattern": r"^(?:[>\]]\s*)?(Cola de comandos borrada \(')(peleas parar)(' detendr[áa] los (?:ataques|combates) si es lo que quer[íi]as\)\.?)\s*$",
            "replace": r'<span style="color: #c0c0c0;">$1</span><span style="color: #ffff00;">$2</span><span style="color: #c0c0c0;">$3</span>'
        },
        {
            "id": "system_buff_tracker",
            "category": "system",
            "priority": 29,
            "pattern": r"^(?:[>\]]\s*)?(Pieles:|Imágenes:)(\d+)\s*$",
            "replace": r'<span style="color: #008000;">$1</span><span style="color: #ffff00; font-weight: bold;">$2</span>'
        },

        # --- 3. CHANNELS & COMMUNICATION ---

        # --- 4. SPELLS, CASTING & MAGICAL EFFECTS ---
        {
            "id": "spell_chant",
            "category": "spell",
            "priority": 40,
            "pattern": r"^(?:[>\]]\s*)?([A-ZÁÉÍÓÚ][\w\s'-]+?\s+pronuncia el cántico:\s*|Pronuncias el cántico:\s*)('[^']+')$",
            "replace": r'<span style="color: #008080;">$1</span><span style="color: #00ffff; font-style: italic;">$2</span>'
        },
        {
            "id": "spell_cast_enemy",
            "category": "spell",
            "priority": 42,
            "pattern": r"^(?:[>\]]\s*)?([A-ZÁÉÍÓÚ][\w\s'-]+?\s+(?:empieza a formular un hechizo|mueve la boca mientras dice lo que para ti son palabras sin sentido)\b[^¡]*?)(\s*)(¡¡ HECHIZO !!)\s*$",
            "replace": r'<span style="color: #ff00f3;">$1</span>$2<span style="color: #ff0000;">$3</span>'
        },

        # --- 5. MOVEMENTS, ROOM EXITS & ENTITIES ---
        {
            "id": "room_exits_inline",
            "category": "movement",
            "priority": 50,
            "pattern": r"^(?:([>\]])\s*)?(.+?)(\s+)([\[\(](?:[|-]?[a-zA-ZáéíóúÁÉÍÓÚ]+[|-]?)(?:,(?:[|-]?[a-zA-ZáéíóúÁÉÍÓÚ]+[|-]?))*[\]\)])\s*$",
            "type": "composite_room_exits"
        },
        {
            "id": "room_title_standalone",
            "category": "movement",
            "priority": 50,
            "pattern": r"^(?:([>\]])\s*)?([A-ZÁÉÍÓÚ][\w\s'-]+:\s+[A-ZÁÉÍÓÚ][\w\s'-]+)\s*$",
            "type": "composite_room_title"
        },
        {
            "id": "movement_enter_exit",
            "category": "movement",
            "priority": 51,
            "pattern": r"^(?:([>\]])\s*)?((?:\b(?:un|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s+)?[*|\-~/]*\s*[A-Za-zÁÉÍÓÚáéíóúñÑ0-9\x27_-]+(?:\s+[|*\-~/]+)?\s*(?:\((?:Hlag|Lag|Melf|Elf|S-e|Gob|Gno|Hum|Orc|S-o|Ena|Mdro|Drow|S-d|Hal|Hlf|Duer|Drg|Min|Mino|Gnl|Gnol|Kob|Org|Orgo|Drax|Ctd|Cent|Kuo|Ggt|S-g)\)(?:es)?(?:\s+\([^)]+\))?|(?:\([^)]+\))?)?(?:\s*[|*\-~/]+)?)\s+(se va en dirección|se va hacia|huye hacia|se dirige a|llega nadando desde|llega de la superficie|llega de la|llega desde|se va|llega)\s+(.*?)(\.?)$",
            "type": "composite_movement"
        },
        {
            "id": "room_exits_list",
            "category": "movement",
            "priority": 52,
            "pattern": r"^(?:[>\]]\s*)?(Puedes ver (?:una|dos|tres|cuatro|cinco|seis|[a-z]+) salidas?:\s*)(.*)$",
            "replace": r'<span style="color: #c0c0c0;">$1</span><span style="color: #808080;">$2</span>'
        },
        {
            "id": "follower_npc_shout",
            "category": "movement",
            "priority": 54,
            "pattern": r"^(?:[>\]]\s*)?([A-ZÁÉÍÓÚ][a-z0-9'-].*?\s+(?:te sigue|te siguen)!)\s*$",
            "replace": r'<span style="color: #00ffff;">$1</span>'
        },
        {
            "id": "room_player_present",
            "category": "movement",
            "priority": 53,
            "pattern": r"^(?:([>\]])\s*)?([^.\n]*?\((?:Hlag|Lag|Melf|Elf|S-e|Gob|Gno|Hum|Orc|S-o|Ena|Mdro|Drow|S-d|Hal|Hlf|Duer|Drg|Min|Mino|Gnl|Gnol|Kob|Org|Orgo|Drax|Ctd|Cent|Kuo|Ggt|S-g)\)[^.\n]*?)(\s+)(está aquí|están aquí|está allí|están allí)\.\s*$",
            "type": "composite_room_player"
        },
        {
            "id": "room_npc_present",
            "category": "movement",
            "priority": 53,
            "pattern": r"^(?:([>\]])\s*)?([^.\n]+?)(\s+)(está aquí|están aquí|está allí|están allí)\.\s*$",
            "type": "composite_room_npc"
        },

        # --- 6. COMBAT (DEATH, FATAL BLOWS, CRITS, ATTACKS) ---
        {
            "id": "combat_under_attack",
            "category": "combat",
            "priority": 60,
            "pattern": r"^([>\]]\s*)?(Est[áa]s siendo atacad[ao] por\s+.*?\.)\s*$",
            "replace": r'<span style="color: #c0c0c0;">$1</span><span style="color: #ff0000; font-weight: bold;">$2</span>'
        },

        # --- 7. BUFFS, SKILLS, EQUIPMENT & CRAFTING ---

        {
            "id": "system_resistance_fade",
            "category": "system",
            "priority": 70,
            "pattern": r"^(?:[>\]]\s*)?(Tu resistencia de [a-z]+ se desvanece\.?)\s*$",
            "replace": r'<span style="color: #ff00ff;">$1</span>'
        },

        # --- 8. PLAYER COMMAND ECHOES ---
        {
            "id": "command_explicit_prompt",
            "category": "command",
            "priority": 80,
            "prompt_only": True,
            "pattern": r"^([a-zñáéíóú0-9_'-]+.*)$",
            "replace": r'<span style="color: #717100;">$1</span>'
        },
        {
            "id": "command_standalone_short",
            "category": "command",
            "priority": 81,
            "pattern": r"^(ojear|mirar|w|si\s+[a-z]+|no|se|so|ne|n|s|e|o|d|arriba|abajo|norte|sur|este|oeste|noreste|noroeste|sudeste|sudoeste|esc|buscar|deso|desollar|sigilar|esconderse|quitar\s+.*|poner\s+.*|coger\s+.*|dejar\s+.*|F\d+|1|2|3|4|5|11|111|cc|int|l|l\s+.*|q|r|pa|co|mo|dn|os|hi|z|a|ge|gne|cn|re|li|gl|lr|cme|cse|cle|cic\s+.*|formular\s+.*|cobardia\s+\d+|vendar\s+.*|nick\s+.*|mnick\s+.*|nickear\s+.*|estado\s+.*|des\s+.*|trepar\s+.*|saltar\s+.*|sacudir\s+.*|peleas\s+.*|stop|parar|pc|go|gn|gs|c|ab|gar|sg|ac|abalanzarse(?:\s+.*)?|desgarrar(?:\s+.*)?|morder(?:\s+.*)?|tajar(?:\s+.*)?|aplastar(?:\s+.*)?|golpecertero(?:\s+.*)?|corte(?:\s+.*)?|estocada(?:\s+.*)?|furia(?:\s+.*)?|concentraci[oó]n)$",
            "replace": r'<span style="color: #717100;">$1</span>'
        },
        {
            "id": "command_echo_bare",
            "category": "command",
            "priority": 82,
            "pattern": r"^(?=.{1,30}$)([a-zñáéíóú][a-zñáéíóú0-9]*(?: [a-zñáéíóú0-9:#-]+){0,3})$",
            "replace": r'<span style="color: #717100;">$1</span>'
        }
    ]
}

ROOMS_FILE = BASE_DIR / "rooms.json"
WEBAPP_RULES_FILE = BASE_DIR / "webapp" / "rules.js"

def build_rules_data(verbose=False):
    """Return the full compiled rules dict (RULES_DATA + room colors from rooms.json)."""
    if ROOMS_FILE.exists():
        with open(ROOMS_FILE, 'r', encoding='utf-8') as rf:
            rooms_catalog = json.load(rf)
        RULES_DATA["room_colors"] = {k.lower(): v for k, v in rooms_catalog.items()}
        if verbose:
            print(f"Loaded {len(RULES_DATA['room_colors'])} room colors from rooms.json")
    elif verbose:
        print("Warning: rooms.json not found!")
    return RULES_DATA


def render_rules_json(data):
    return json.dumps(data, indent=2, ensure_ascii=False)


def render_rules_js(data):
    return "// Auto-generated from build_rules.py\nwindow.COLORIZER_RULES = " + render_rules_json(data) + ";\n"


def save_rules():
    data = build_rules_data(verbose=True)

    with open(RULES_FILE, 'w', encoding='utf-8', newline='\n') as f:
        f.write(render_rules_json(data))
    print(f"Generated v5 rules.json at: {RULES_FILE}")

    WEBAPP_RULES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(WEBAPP_RULES_FILE, 'w', encoding='utf-8', newline='\n') as f:
        f.write(render_rules_js(data))
    print(f"Generated webapp/rules.js at: {WEBAPP_RULES_FILE}")

if __name__ == '__main__':
    save_rules()

