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
#   squeeze_blank    {keep_before}
#                    post-pass: drop every blank line except one kept right before
#                    a line matching `keep_before` (start of a new prompt/turn) when
#                    the source had blanks there. Leading/trailing blanks are dropped.
#                    VIPMud adds a blank line after most server messages; this keeps
#                    the colored paste compact.
#   drop_with_echo   {pattern, message_group, continuation, lookback, max_prefix,
#                     max_prefix_words, prefix_reject}
#                    drop the matching line (and the `continuation` lines right after it, which
#                    belong to the same wrapped message), then remove the most recent line among
#                    the last `lookback` non-blank emitted lines whose text (prompt removed,
#                    spaces collapsed) ends with the message (group `message_group` plus the
#                    continuation lines). What precedes the message must be at most
#                    `max_prefix` characters, end on a space, have at most `max_prefix_words`
#                    words and not match `prefix_reject`. Used to remove a typed tell command
#                    whatever its alias; lines in between are kept. No state across inputs.
#   drop             also accepts `continuation`: following lines matching it are dropped too.
# Any rule may carry "option": "<name>"; it only runs when that option is enabled. The only
# option is "hide_private" (on by default; CLI --keep-private, checkbox in the web page).
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

        # --- Private messages (option "hide_private", on by default): tells and telepathy ---
        # Players type tells through aliases (t, tell, r, telepatia, custom words, even a stray
        # DEL char), so the typed command is found by its message, never by its command word.
        {
            # "X te dice: msg" / "te pregunta:" / "te exclama:", also numbered in history lists
            # ("26: X te dice: ..."). The ':' ban in the name keeps public chat lines out.
            # Indented lines right after it are the wrapped rest of the message (or the
            # "Debido a tu invisibilidad..." notice); an indented "[exits]" line is not.
            "id": "private_tell_in",
            "option": "hide_private",
            "kind": "drop",
            "pattern": r"^(?:[>\]][ \t]*)?(?:\d+:[ \t]*)?[^:\n]{1,80}? te (?:dice|pregunta|exclama):",
            "continuation": r"^[ \t]{2,}[^ \t\[]",
        },
        {
            "id": "private_telepathy_notice",
            "option": "hide_private",
            "kind": "drop",
            "pattern": r"^(?:[>\]][ \t]*)?[^:\n]{1,80}? contacta telepáticamente con ",
        },
        {
            # "Dices a X: msg" (also Preguntas / Exclamas): the server echo of your own tell,
            # plus the command you typed to send it.
            "id": "private_tell_out",
            "option": "hide_private",
            "kind": "drop_with_echo",
            "pattern": r"^(?:[>\]][ \t]*)?(?:Dices|Preguntas|Exclamas) a [^:\n]{1,60}:[ \t]*(.*)$",
            "message_group": 1,
            "continuation": r"^[ \t]{2,}[^ \t\[]",
            "lookback": 15,
            "max_prefix": 40,
            "max_prefix_words": 3,
            "prefix_reject": r":",
        },

        # --- VIPMud status block (Pv/SL/PL/NM/LD/Jgd/Imágenes/Pieles + closing prompt) ---
        {
            # Always dropped: when HP changes the game prints its own "Pvs: N/N (+-N) Pe: ..." line.
            "id": "vip_status_pv",
            "kind": "drop",
            "clients": ["vipmud"],
            "group": "status",
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
            # Prompt variant with the nearby-enemies lists ("NM:", "LD:") instead of "Jgd:".
            "id": "vip_status_nm_ld",
            "kind": "drop",
            "clients": ["vipmud"],
            "group": "status",
            "pattern": r"^(?:NM|LD):",
        },
        {
            "id": "vip_status_jgd",
            "kind": "drop",
            "clients": ["vipmud"],
            "group": "status",
            "pattern": r"^Jgd:",
        },
        {
            # Status counters are shown only when there is something (images, skins, astucia, inercia).
            "id": "vip_status_counters_zero",
            "kind": "drop",
            "clients": ["vipmud"],
            "group": "status",
            "pattern": r"^(?:Imágenes|Pieles|Astucia|Inercia):0[ \t]*$",
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
            "id": "vip_status_astucia",
            "kind": "dedupe_on_change",
            "clients": ["vipmud"],
            "group": "status",
            "scope_id": "astucia",
            "pattern": r"^Astucia:(\d+)[ \t]*$",
            "key_group": 1,
        },
        {
            "id": "vip_status_inercia",
            "kind": "dedupe_on_change",
            "clients": ["vipmud"],
            "group": "status",
            "scope_id": "inercia",
            "pattern": r"^Inercia:(\d+)[ \t]*$",
            "key_group": 1,
        },
        {
            "id": "vip_status_closer",
            "kind": "drop_closer",
            "clients": ["vipmud"],
            "group": "status",
            "pattern": r"^[>\]][ \t]*$",
        },
        # VIPMud pads most server messages with a blank line; keep one only before a new
        # turn: a prompt (`>` / `]`), a `Pv:` status line, or a room line with exits.
        {
            "id": "vip_squeeze_blank",
            "kind": "squeeze_blank",
            "clients": ["vipmud"],
            # Never matches: every blank line of a VIPMud log is dropped.
            "keep_before": r"(?!)",
        },
    ],
}


# Shared regex fragments for the third-person rules. Actor/target names are generic: any
# capitalized text (accents, commas, several words) without ":" or quotes, so a sentence quoted
# inside chat ("Dices: '...'") or a tell ("X te dice: ...") can never match.
ACTOR = r'[A-ZÁÉÍÓÚÑÜ][^:"¡!?.]*?'
NAME = r'[^:"¡!?.]+?'
REFLECT_BOUNCE = (
    r'(?:(?:El|La|Los|Las) [a-záéíóúñ ]+? convocad[oa]s? por|La magia de) ' + NAME
    + r' se vuelve contra (?:[ée]l|ella) [^:"]*\.'
    + r'|El Ojo del cintur[oó]n brilla (?:con fuerza dispersando|enviando el hechizo a su lanzador)[^:"]*'
)
HOWL_EFFECTS = (
    ACTOR + r' emite un aullido [^:"]*\.'
    + r'|¡U{3,}O{3,}R{3,}H!'
    + r'|¡?Te retuerces d(?:e|el) [^:"]*aullido de [^:"]+[.!]'
    + r'|¡Tus t[ií]mpanos revientan [^:"]*!'
    + r'|De pronto el mundo a tu alrededor queda en silencio\.'
    + r'|' + ACTOR + r' parece no ser consciente de los sonidos que le rodean\.'
)

# Health tiers (composite_health_tier). Chosen to stay >= 60 RGB distance from every other
# color used by the rules and >= 4.5 contrast on black (checked by tests/test_health_tiers.py).
HEALTH_TIERS = [
    {"min": 70, "color": "#5fd75f"},
    {"min": 31, "color": "#ffcc4b"},
    {"min": -100000, "color": "#ea063f"},
]

# Composite rule types are rendered by engine.py / webapp/engine.js (kept in parity):
#   composite_health_tier  {tiers, tier_groups, tier_source}
#       Every capture group is emitted in order (the pattern must cover the whole line so the
#       visible text is unchanged). Groups listed in `tier_groups` take the color of the first
#       tier whose `min` <= the integer found in group `tier_source` (the percentage); the other
#       groups keep the default color.
# Block context (any rule): `sets_context: "<name>"` opens a context when the rule matches a line;
#   `requires_context: "<name>"` makes a rule eligible only while that context is open. The context
#   stays open while consecutive lines match a `requires_context` rule and closes on a blank line
#   or on any other line.
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
        # kind of event: first matching category wins, otherwise `color`. Lines without a
        # marker keep falling through to the full-line rules below.
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
            "id": "system_exp",
            "category": "system",
            "priority": 20,
            "pattern": r"^(?:[>\]]\s*)?(\[Obtienes )(\d+)( puntos de experiencia\])\s*$",
            "replace": r'<span style="color: #c0c0c0;">$1</span><span style="color: #ffffff; font-weight: bold;">$2</span><span style="color: #c0c0c0;">$3</span>'
        },
        {
            "id": "system_glory",
            "category": "system",
            "priority": 21,
            "pattern": r"^(?:[>\]]\s*)?(\[Obtienes )(\d+)( puntos de gloria\])\s*$",
            "replace": r'<span style="color: #c0c0c0;">$1</span><span style="color: #ffff00; font-weight: bold;">$2</span><span style="color: #c0c0c0;">$3</span>'
        },
        # The following game colors were checked against colored Mudlet logs on Deathlogs:
        # each one shows the same way in dozens of logs from different players.
        {
            "id": "system_faction_status",
            "category": "system",
            "priority": 22,
            "pattern": r"^(?:[>\]]\s*)?(\[Tu estatus con )(.+?)( ha )(?:(aumentado)|(disminu[ií]do))(\])\s*$",
            "replace": r'<span style="color: #c0c0c0;">$1</span><span style="color: #ffff00;">$2</span><span style="color: #c0c0c0;">$3</span><span style="color: #00ff00;">$4</span><span style="color: #c0c0c0;">$5$6</span>'
        },
        {
            "id": "system_alignment_change",
            "category": "system",
            "priority": 23,
            "pattern": r"^(?:[>\]]\s*)?(\[Tu alineamiento ha )(aumentado|disminu[ií]do)(\])\s*$",
            "replace": r'<span style="color: #c0c0c0;">$1</span><span style="color: #ffffff;">$2</span><span style="color: #c0c0c0;">$3</span>'
        },
        {
            "id": "system_cancel_hint",
            "category": "system",
            "priority": 24,
            "pattern": r"^(?:[>\]]\s*)?(Escribe )(cancelar)( para finalizar la acci[óo]n prematuramente\.)\s*$",
            "replace": r'<span style="color: #c0c0c0;">$1</span><span style="color: #ffff00;">$2</span><span style="color: #c0c0c0;">$3</span>'
        },
        {
            # The game echoes the unknown command in green; the rest keeps the gray of
            # system_actions_warning.
            "id": "system_unknown_command",
            "category": "system",
            "priority": 25,
            "pattern": r"^(?:[>\]]\s*)?(Parece que )(.+?)( no produjo efecto alguno\.)\s*$",
            "replace": r'<span style="color: #808080;">$1</span><span style="color: #00ff00;">$2</span><span style="color: #808080;">$3</span>'
        },
        {
            "id": "combat_acid_arrow_damage",
            "category": "combat",
            "priority": 26,
            "pattern": r"^(?:[>\]]\s*)?(¡Sufres daño a causa del )(ácido)( de la flecha!)\s*$",
            "replace": r'<span style="color: #c0c0c0;">$1</span><span style="color: #ffff00;">$2</span><span style="color: #c0c0c0;">$3</span>'
        },
        {
            "id": "status_skin_back_to_normal",
            "category": "status",
            "priority": 27,
            "pattern": r"^(?:[>\]]\s*)?((?:! ){5}Tu PIEL vuelve a su ESTADO NORMAL(?: !){5})\s*$",
            "replace": r'<span style="color: #ff0000;">$1</span>'
        },
        {
            "id": "stealth_discovered",
            "category": "status",
            "priority": 28,
            "pattern": r"^(?:[>\]]\s*)?(¡Descubres a " + ACTOR + r" intentando moverse en silencio!)\s*$",
            "replace": r'<span style="color: #ff00ff;">$1</span>'
        },
        {
            "id": "stealth_presence_sensed",
            "category": "status",
            "priority": 29,
            "pattern": r"^(?:[>\]]\s*)?(Te haces consciente de la presencia de " + ACTOR + r"\.)\s*$",
            "replace": r'<span style="color: #ff00ff;">$1</span>'
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
            "pattern": r"^(?:[>\]]\s*)?(Pieles:|Imágenes:|Astucia:|Inercia:)(\d+)\s*$",
            "replace": r'<span style="color: #008000;">$1</span><span style="color: #ffff00; font-weight: bold;">$2</span>'
        },

        # --- 3. CHANNELS & COMMUNICATION ---
        {
            "id": "channels_standard",
            "category": "channel",
            "priority": 30,
            "pattern": r"^(?:[>\]]\s*)?(\[[A-Za-z0-9_]+\])(\s+[^:]+:)(.*)$",
            "replace": r'<span style="color: #008080;">$1</span><span style="color: #ffffff;">$2</span><span style="color: #00ffff;">$3</span>'
        },
        {
            "id": "say_player",
            "category": "channel",
            "priority": 31,
            "pattern": r"^(?:[>\]]\s*)?(Dices(?: en [^:]+)?:)(.*)$",
            "replace": r'<span style="color: #00ffff;">$1</span><span style="color: #ffffff;">$2</span>'
        },
        {
            "id": "say_other",
            "category": "channel",
            "priority": 32,
            "pattern": r"^(?:[>\]]\s*)?([A-Z][a-z0-9'-]+ dice(?: en [^:]+)?:)(.*)$",
            "replace": r'<span style="color: #008080;">$1</span><span style="color: #c0c0c0;">$2</span>'
        },
        {
            "id": "tell_player",
            "category": "channel",
            "priority": 33,
            "pattern": r"^(?:[>\]]\s*)?([A-Z][a-z0-9'-]+ te dice:)(.*)$",
            "replace": r'<span style="color: #00ffff;">$1</span><span style="color: #ffffff;">$2</span>'
        },

        # --- Health percentages (tiered colors, only the percentage token is colored) ---
        {
            # With a leading "> " / "] " the line used to be colored as a command echo (olive,
            # command_explicit_prompt); keep that color and still open the block context.
            "id": "group_status_header_prompted",
            "category": "status",
            "priority": 35,
            "prompt_only": True,
            "pattern": r"^(De un fugaz vistazo, examinas el estado de los que te rodean\.)\s*$",
            "sets_context": "group_status",
            "replace": r'<span style="color: #717100;">$1</span>'
        },
        {
            "id": "group_status_header",
            "category": "status",
            "priority": 35,
            "pattern": r"^(De un fugaz vistazo, examinas el estado de los que te rodean\.)\s*$",
            "sets_context": "group_status",
            "replace": r'<span style="color: #c0c0c0;">$1</span>'
        },
        {
            # "<Name><padding>NN%" lines, only right after the header above (a bare "Name 28%" elsewhere,
            # such as an inventory durability, is left alone). Names are generic (commas, accents, spaces).
            "id": "group_status_health",
            "category": "status",
            "priority": 36,
            "requires_context": "group_status",
            "type": "composite_health_tier",
            "pattern": r'^([^\s:"¡!?][^:"¡!?]*?)(\s+)(-?\d{1,3}%)(\s*)$',
            "tier_groups": [3],
            "tier_source": 3,
            "tiers": HEALTH_TIERS
        },
        {
            # "<Name><padding>Vida: NN% Energía: NN%" in the same block; only the Vida percentage is tiered.
            "id": "group_status_health_energy",
            "category": "status",
            "priority": 36,
            "requires_context": "group_status",
            "type": "composite_health_tier",
            "pattern": r'^([^\s:"¡!?][^:"¡!?]*?)(\s+Vida: )(-?\d{1,3}%)( Energía: -?\d{1,3}%\s*)$',
            "tier_groups": [3],
            "tier_source": 3,
            "tiers": HEALTH_TIERS
        },
        {
            # "Puntos de Vida        : [########    ] (21637/50601) (42%)": the two numbers and the percentage.
            "id": "vitals_health_bar_line",
            "category": "status",
            "priority": 37,
            "type": "composite_health_tier",
            "pattern": r"^(Puntos de Vida\s*:\s*\[[# ]*\]\s*\()(\d+)(/)(\d+)(\)\s*\()(\d{1,3}%)(\)\s*)$",
            "tier_groups": [2, 4, 6],
            "tier_source": 6,
            "tiers": HEALTH_TIERS
        },
        {
            "id": "vitals_health_line",
            "category": "status",
            "priority": 37,
            "type": "composite_health_tier",
            "pattern": r"^(Puntos de Vida: )(\d+)( de )(\d+)( \()(\d{1,3}%)(\)\s*)$",
            "tier_groups": [2, 4, 6],
            "tier_source": 6,
            "tiers": HEALTH_TIERS
        },
        # --- 4. SPELLS, CASTING & MAGICAL EFFECTS ---
        {
            "id": "spell_chant",
            "category": "spell",
            "priority": 40,
            "pattern": r"^(?:[>\]]\s*)?([A-ZÁÉÍÓÚ][\w\s'-]+?\s+pronuncia el cántico:\s*|Pronuncias el cántico:\s*)('[^']+')$",
            "replace": r'<span style="color: #008080;">$1</span><span style="color: #00ffff; font-style: italic;">$2</span>'
        },
        {
            "id": "spell_cast_start",
            "category": "spell",
            "priority": 41,
            "pattern": r"^(?:[>\]]\s*)?(.*?(?:formular el hechizo|formular el cántico|obrar un hechizo|concentras en el hechizo|concentras en tu hechizo de)\s*)('[^']+'\.?)(.*)$",
            "replace": r'<span style="color: #ffffff;">$1</span><span style="color: #00ffff;">$2</span><span style="color: #c0c0c0;">$3</span>'
        },
        {
            "id": "spell_cast_enemy",
            "category": "spell",
            "priority": 42,
            "pattern": r"^(?:[>\]]\s*)?([A-ZÁÉÍÓÚ][\w\s'-]+?\s+(?:empieza a formular un hechizo|mueve la boca mientras dice lo que para ti son palabras sin sentido)\b[^¡]*?)(\s*)(¡¡ HECHIZO !!)\s*$",
            "replace": r'<span style="color: #ff00f3;">$1</span>$2<span style="color: #ff0000;">$3</span>'
        },
        {
            "id": "spell_cast_enemy_plain",
            "category": "spell",
            "priority": 42,
            "pattern": r"^(?:[>\]]\s*)?([A-ZÁÉÍÓÚ][\w\s'-]+?\s+(?:empieza a formular un hechizo|mueve la boca mientras dice lo que para ti son palabras sin sentido)\b.*)$",
            "replace": r'<span style="color: #ff00f3; font-weight: bold;">$1</span>'
        },
        {
            # "Tocas a <X> mientras formulas el hechizo." Same teal as the "Pronuncias el cántico:"
            # prefix of spell_chant. That rule colors a prefix (plus the quoted words in cyan); this
            # sentence has no quoted part, so the whole sentence takes the prefix color.
            "id": "spell_touch_cast",
            "category": "spell",
            "priority": 41,
            "pattern": r'^(?:[>\]]\s*)?(Tocas a ' + NAME + r' mientras formulas el hechizo\.)\s*$',
            "replace": r'<span style="color: #008080;">$1</span>'
        },
        {
            # "<X> se concentra en un [oscuro] hechizo." (enemy starts casting): same magenta as the
            # friend's enemy-spellcasting rules (spell_cast_enemy_plain). "se concentra formando la
            # figura de..." and "en una brillante gema..." are other events and do not match.
            "id": "spell_cast_enemy_concentrate",
            "category": "spell",
            "priority": 42,
            "pattern": r'^(?:[>\]]\s*)?(' + ACTOR + r' se concentra en un(?: [a-záéíóúñ]+)? hechizo\.)\s*$',
            "replace": r'<span style="color: #ff00f3; font-weight: bold;">$1</span>'
        },
        {
            "id": "spell_cast_enemy_stop",
            "category": "spell",
            "priority": 43,
            "pattern": r"^(?:[>\]]\s*)?([A-Z][a-z0-9'-]+\s+deja de formular\..*)$",
            "replace": r'<span style="color: #808080;">$1</span>'
        },
        {
            "id": "spell_completion",
            "category": "spell",
            "priority": 44,
            "pattern": r"^(?:[>\]]\s*)?(Terminas tu hechizo\s*.*|Tu hechizo (?:de '[^']+' )?termina\s*.*|Finalizas el hechizo\s*.*)$",
            "type": "composite_spell_completion"
        },
        {
            "id": "spell_projectiles_invocations",
            "category": "spell",
            "priority": 45,
            "pattern": r"^(?:([>\]])\s*)?(#\s*)?(¡?El cielo ruge cuando invocas un relámpago\b.*|\d+\s+misiles mágicos surgen de tus dedos e impactan\b.*|¡?Invocas\b.*|Conjuras\b.*|Tu arco desaparece\b.*|Las llamas de tu arco\b.*|La flecha que lanzaste\b.*|\d+\s+rayos caen desde el cielo\b.*|Un rayo (?:de [^.]+ surge de|impacta (?:sobre|junto a))\b.*|Alzas tu mano, y alrededor de la misma comienzan a formarse\b.*|Trazas con ágiles movimientos en tus dedos\b.*|Posas las manos en el suelo e invocas\b.*|Tu hechizo termina a golpe de trompeta.*)$",
            "type": "composite_magic_missiles"
        },
        {
            "id": "spell_failed_distracted",
            "category": "spell",
            "priority": 46,
            "pattern": r"^(?:[>\]]\s*)?(.*?(?:pierde la concentración|arruinado|no eres capaz de concentrarte|Estás realizando los movimientos de un hechizo|Tus objetivos ya no están al alcance|Tu maniobra de \w+ se ve interrumpida|resiste los efectos de tu hechizo|Has agotado la energía necesaria|El destino de tu hechizo).*)$",
            "replace": r'<span style="color: #ff8080;">$1</span>'
        },
        {
            "id": "spell_healing_effect",
            "category": "spell",
            "priority": 47,
            "pattern": r"^(?:[>\]]\s*)?(Curas\s+(?:algunas|todas|gran parte)\s+de\s+(?:tus|las)\s+heridas\b.*?\.?)\s*$",
            "replace": r'<span style="color: #ff0000;">$1</span>'
        },
        {
            # Someone else healing: "<X> cura algunas de sus heridas más ligeras/moderadas/serias/críticas."
            # Healer and severity are generic. Enemy-spell magenta, so it reads apart from our own heal.
            "id": "spell_healing_other",
            "category": "spell",
            "priority": 47,
            "pattern": r'^(?:[>\]]\s*)?(' + ACTOR + r' cura (?:algunas|todas|gran parte) de sus heridas(?: más)?(?: [a-záéíóúñ]+)?\.)\s*$',
            "replace": r'<span style="color: #ff00f3;">$1</span>'
        },

        # Devolver conjuro / reflected spells. Own spell effects share the magic-missile blue
        # (#8cc4ff); the spell winding down uses the gray of "deja de formular"; effects that the
        # enemy lands on you use the enemy-effect red (#cc6666) of combat_enemy_attack.
        {
            "id": "spell_reflect_own_activates",
            "category": "spell",
            "priority": 48,
            "pattern": r'^(?:[>\]]\s*)?(¡?(?:Tu hechizo de devolver conjuro(?: mayor| menor)? se activa y fuerza al de|El Ojo de tu cintur[oó]n brilla y fuerza al hechizo de) [^:"]+? a cambiar su objetivo hacia s[ií] mism[ao]s?!)\s*$',
            "replace": r'<span style="color: #8cc4ff;">$1</span>'
        },
        {
            "id": "spell_reflect_bounce",
            "category": "spell",
            "priority": 48,
            "pattern": r'^(?:[>\]]\s*)?(' + REFLECT_BOUNCE + r')\s*$',
            "replace": r'<span style="color: #8cc4ff;">$1</span>'
        },
        {
            "id": "spell_reflect_ends",
            "category": "spell",
            "priority": 48,
            "pattern": r"^(?:[>\]]\s*)?(Tu hechizo de devolver conjuro(?: mayor| menor)? llega a su fin\.)\s*$",
            "replace": r'<span style="color: #808080;">$1</span>'
        },
        {
            "id": "spell_redirected_to_you",
            "category": "spell",
            "priority": 48,
            "pattern": r'^(?:[>\]]\s*)?(¡El hechizo de [^:"]+? cambia de objetivo hacia ti!)\s*$',
            "replace": r'<span style="color: #cc6666;">$1</span>'
        },
        # Howl sequence (hechizo aullido infernal): the enemy's howl and what it does to you.
        {
            "id": "spell_howl_effects",
            "category": "spell",
            "priority": 48,
            "pattern": r'^(?:[>\]]\s*)?(' + HOWL_EFFECTS + r')\s*$',
            "replace": r'<span style="color: #cc6666;">$1</span>'
        },
        # Own defensive spells taking effect ("Eres rodeada por un globo de protección.", gendered
        # rodead[oa] / envuelt[oa] / cubiert[oa]) and own damage spells (window sequence, aura
        # retaliation): the own-spell blue. Names are generic; every pattern starts with fixed text.
        {
            "id": "spell_own_defense_on",
            "category": "spell",
            "priority": 48,
            "pattern": r'^(?:[>\]]\s*)?(Eres (?:rodead|envuelt|cubiert)[oa] por (?:un|una) [^:"]*?(?:protecci[oó]n|aura|globo|escudo|campo|barrera|manto)[^:"]*\.|Un campo de energ[ií]a forma un escudo m[aá]gico ante ti\.|Un aura protectora empieza a formarse a tu alrededor\.)\s*$',
            "replace": r'<span style="color: #8cc4ff;">$1</span>'
        },
        {
            "id": "spell_own_damage_effects",
            "category": "spell",
            "priority": 48,
            "pattern": r'^(?:[>\]]\s*)?(Trazas con ambas manos un rect[aá]ngulo en el aire y una enorme ventana aparece justo detr[aá]s de ' + NAME
                       + r' entre una gran humareda chispeante\.'
                       + r'|¡Cierras con fuerza sendos pu[ñn]os y una r[aá]faga m[aá]gica sale disparada en direcci[oó]n a ' + NAME + r'!'
                       + r'|¡' + ACTOR + r' sale disparad[oa] contra la ventana y la revienta estruendosamente, volando \d+ metros? antes de caer malherid[oa] al suelo!'
                       + r'|Tu aura brilla castigando a ' + NAME + r' con el mismo dolor\.)\s*$',
            "replace": r'<span style="color: #8cc4ff;">$1</span>'
        },
        {
            "id": "spell_dispelled_on_you",
            "category": "spell",
            "priority": 48,
            "pattern": r'^(?:[>\]]\s*)?(Sientes como un poder m[aá]gico sin igual choca contigo y hace a[ñn]icos la magia que te rodeaba(?: mientras ' + NAME + r' finaliza su hechizo)?\.)\s*$',
            "replace": r'<span style="color: #cc6666;">$1</span>'
        },
        {
            "id": "spell_effect_ends",
            "category": "spell",
            "priority": 48,
            "pattern": r'^(?:[>\]]\s*)?(Tu (?:globo|escudo|armadura|aura|debilidad)[^:".]*? (?:empieza a parpadear hasta que desaparece|se desvanece)\.'
                       + r'|El globo que rodea a ' + NAME + r' empieza a parpadear hasta que desaparece\.'
                       + r'|(?:Notas como )?[Tt]u hechizo de [^:"]+? llega a su fin\.'
                       + r'|La regeneraci[oó]n m[aá]gica de ' + NAME + r' termina\.'
                       + r'|' + ACTOR + r' parece menos decidid[oa] que antes cuando su sortilegio llega a su fin\.)\s*$',
            "replace": r'<span style="color: #808080;">$1</span>'
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
            "replace": r'<span style="color: #c0c0c0;">$1</span><span style="color: #ffff00;">$2</span>'
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
        {
            "id": "follower_player_notification",
            "category": "movement",
            "priority": 54,
            "pattern": r"^(?:([>\]])\s*)?([A-ZÁÉÍÓÚ][a-z0-9'-].*?\((?:Hlag|Lag|Melf|Elf|S-e|Gob|Gno|Hum|Orc|S-o|Ena|Mdro|Drow|S-d|Hal|Hlf|Duer|Drg|Min|Mino|Gnl|Gnol|Kob|Org|Orgo|Drax|Ctd|Cent|Kuo|Ggt|S-g)\).*?)\s+(te sigue|te siguen)\.\s*$",
            "type": "composite_follower_player"
        },
        {
            "id": "follower_npc_notification",
            "category": "movement",
            "priority": 54,
            "pattern": r"^(?:[>\]]\s*)?([A-Z][a-z0-9'-].*?)\s+(te sigue|te siguen)\.\s*$",
            "replace": r'<span style="color: #c0c0c0;">$1 $2.</span>'
        },
        {
            "id": "corpse_room",
            "category": "movement",
            "priority": 55,
            "pattern": r"^(?:[>\]]\s*)?((?:Cuerpo|Restos putrefactos|Cadáver|Esqueleto) de [^.]+?\.|(?:Charco|Charcos) de sangre\.?)\s*$",
            "replace": r'<span style="color: #aa0000; font-weight: bold;">$1</span>'
        },

        # --- 6. COMBAT (DEATH, FATAL BLOWS, CRITS, ATTACKS) ---
        {
            "id": "combat_death_broadcast",
            "category": "combat",
            "priority": 60,
            "pattern": r"^(?:[>\]]\s*)?(.*?(?:ha muerto a manos de|ha muerto\.|cae al suelo sin vida|da un grito desgarrador|orbita al Limbo).*)$",
            "replace": r'<span style="color: #ff0000; font-weight: bold;">$1</span>'
        },
        {
            "id": "combat_under_attack",
            "category": "combat",
            "priority": 60,
            "pattern": r"^([>\]]\s*)?(Est[áa]s siendo atacad[ao] por\s+.*?\.)\s*$",
            "replace": r'<span style="color: #c0c0c0;">$1</span><span style="color: #ff0000; font-weight: bold;">$2</span>'
        },
        {
            "id": "combat_fatal_blow",
            "category": "combat",
            "priority": 61,
            "pattern": r"^(?:[>\]]\s*)?(Propinas el golpe mortal a\s+.*)$",
            "replace": r'<span style="color: #00ff00; font-weight: bold;">$1</span>'
        },
        {
            # Third person ("<X> se propina el golpe mortal." / "<X> propina el golpe mortal a <Y>.").
            # Darker green than the own-blow rule above (#00ff00), so ours and others' blows look different.
            # #1a9a1a instead of #008000: same idea, but readable on black (contrast 5.7 vs 4.1).
            # The actor may not contain ":" or quotes, so chat/tell lines never match.
            "id": "combat_fatal_blow_third",
            "category": "combat",
            "priority": 61,
            "pattern": r'^(?:[>\]]\s*)?(' + ACTOR + r' (?:se propina el golpe mortal|propina el golpe mortal a [^:"]+?)\.)\s*$',
            "replace": r'<span style="color: #1a9a1a; font-weight: bold;">$1</span>'
        },
        {
            "id": "combat_crit_eviscerate",
            "category": "combat",
            "priority": 62,
            "pattern": r"^(?:[>\]]\s*)?(.*?(?:eviscera|destriparte|un enorme boquete|sangre y carne triturada).*)$",
            "replace": r'<span style="color: #ff0000;">$1</span>'
        },
        {
            "id": "combat_skin_absorb",
            "category": "combat",
            "priority": 62,
            "pattern": r"^(?:[>\]]\s*)?(\*?\s*)(El ataque de\s+.*?\s+rebota en tu piel de piedra\.)\s*$",
            "replace": r'<span style="color: #ffff00;">$1$2</span>'
        },
        {
            "id": "combat_dodge_parry",
            "category": "combat",
            "priority": 63,
            "pattern": r"^(?:[>\]]\s*)?((?:#|\*)?\s*.*?(?:\b(?:esquiva|esquivas|esquivar|para|paras|parar|bloquea|bloqueas|bloquear)\b.*?(?:\b(?:tu ataque|su ataque|el ataque|el impacto|el golpe|la maniobra|la embestida|una lluvia)\b|mientras parpadea absorviendo)|fallas tu ataque|eludes la búsqueda|¡?Logras (?:esquivar|parar|bloquear)\b.*?).*)$",
            "replace": r'<span style="color: #808080;">$1</span>'
        },
        {
            "id": "combat_enemy_attack",
            "category": "combat",
            "priority": 64,
            "pattern": r"^(?:[>\]]\s*)?(\*?\s*)(.*? te (?:intenta\s+)?(?:golpea|corta|desgarra|lacera|fustiga|clava|rasguña|entierra|muerde|patea|raja|aplasta|arremete|abraza|sorbe|alcanza|fulmina|azota|electrocuta|castiga|purifica|perfora|corrompe|apuñalar|mutilar|desmembrar)\b.*)$",
            "replace": r'<span style="color: #aa0000;">$1</span><span style="color: #cc6666;">$2</span>'
        },
        {
            "id": "combat_enemy_maneuver",
            "category": "combat",
            "priority": 65,
            "pattern": r"^(?:([>\]])\s*)?(!\s*)?([A-Za-zÁÉÍÓÚáéíóúñÑ0-9'|\-/(), ]+?)(\s+)(se prepara para ejecutar|se prepara para|tensa sus músculos|se echa hacia atrás|empieza a centrar|comienza a serpentear|te examina|examina las defensas de|te mira fijamente|comienza a realizar|comienza a moverse)\b(.*)$",
            "type": "composite_enemy_maneuver"
        },
        {
            "id": "combat_poison_effects",
            "category": "combat",
            "priority": 66,
            "pattern": r"^(?:[>\]]\s*)?(.*?(?:te envenena|ponzoña virulenta|garras contaminadas|saliva tóxica).*)$",
            "replace": r'<span style="color: #cc6666;">$1</span>'
        },
        {
            "id": "combat_player_attacks",
            "category": "combat",
            "priority": 67,
            "pattern": r"^(?:([>\]])\s*)?(?:(#\s+)(.+)|(\*\s*)?((?:¡)?(?:Tu\s+(?:ataque|estocada|golpe|flecha|corte|puñetazo|patada|mordisco|zarpazo|mandoble|hachazo|embestida)\s+(?:desgarra|atraviesa|corta|raja|golpea|impacta|sorbe|alcanza|penetra|rebota|falla|choca)\b|Tu\s+[A-ZÁÉÍÓÚ][\w\s'-]+(?:se ilumina cuando|atraviesa|desgarra|golpea)\b|(?:Muerdes|Pateas|Golpeas|Desgarras|Atraviesas|Clavas|Rajas|Rajás|Cortas|Aplastas|Cabeceas|Alcanzas|Perforas|Enfermas|Envenenas|Hundes|Laceras|Pinchas|Fustigas|Empalas|Trituras|Acoceas|Descargas una furia de golpes)\b))(.*))$",
            "type": "composite_player_combat"
        },

        # --- 7. BUFFS, SKILLS, EQUIPMENT & CRAFTING ---
        {
            "id": "system_resistance_fade",
            "category": "system",
            "priority": 70,
            "pattern": r"^(?:[>\]]\s*)?(Tu resistencia de [a-z]+ se desvanece\.?)\s*$",
            "replace": r'<span style="color: #ff00ff;">$1</span>'
        },
        {
            "id": "system_buff_expire",
            "category": "system",
            "priority": 70,
            "pattern": r"^(?:[>\]]\s*)?(Tu armadura deja de estar expuesta\b.*|Tu capa derrama parte de la sangre\b.*|Tu resistencia de [a-z]+ se desvanece\b.*|Tu capacidad de movimiento vuelve\b.*|Tu poder mágico vuelve\b.*)$",
            "replace": r'<span style="color: #808080;">$1</span>'
        },
        {
            "id": "system_equipment_action",
            "category": "system",
            "priority": 71,
            "pattern": r"^(?:[>\]]\s*)?((?:Dejas de sostener|Empuñas|Te pones|Te quitas|Estás intentando equilibrar|Finalmente equilibras)\s+.*)$",
            "replace": r'<span style="color: #c0c0c0;">$1</span>'
        },
        {
            "id": "system_crafting_skinning",
            "category": "system",
            "priority": 72,
            "pattern": r"^(?:[>\]]\s*)?((?:Armado con tu|Continúas desollando|Continúas con tu sucio trabajo|Tras dedicar largos minutos desollando)\s+.*)$",
            "replace": r'<span style="color: #c0c0c0;">$1</span>'
        },
        {
            "id": "system_actions_warning",
            "category": "system",
            "priority": 73,
            "pattern": r"^(?:[>\]]\s*)?(Ignorando\s+.*|No puedes\s+.*|No estás\s+.*|No hay nadie\s+.*|El objetivo\s+.*|Parece que\s+.*|Ese nombre\s+.*|Has usado\s+.*|No tienes\s+.*)\s*$",
            "replace": r'<span style="color: #808080;">$1</span>'
        },
        {
            "id": "skills_player_prep",
            "category": "skill",
            "priority": 74,
            "pattern": r"^(?:[>\]]\s*)?(\+\s*)(.*)$",
            "replace": r'<span style="color: #ffff00; font-weight: bold;">+</span> <span style="color: #0800ff;">$2</span>'
        },
        {
            "id": "skills_actions",
            "category": "skill",
            "priority": 75,
            "pattern": r"^(?:[>\]]\s*)?(Empiezas a\b.*|Intentas\b.*|Preparas los componentes\b.*|Logras\b.*|Finalmente logras\b.*|Consigues zafarte\b.*|Te preparas para\b.*|Te mueves en silencio\b.*|Sufres cuando tus músculos\b.*|Tras tu dolorosa conversi[oó]n\b.*|Agotado, eres incapaz\b.*)$",
            "replace": r'<span style="color: #0800ff;">$1</span>'
        },

        # --- 8. PLAYER COMMAND ECHOES ---
        {
            "id": "command_explicit_prompt",
            "category": "command",
            "priority": 80,
            "prompt_only": True,
            # Typed commands start in lowercase, with a digit or as a function key (F12). Game
            # messages printed right after the prompt start in uppercase ("] Estás persiguiendo a X.").
            "pattern": r"^((?:[a-z0-9ñáéíóú_'-]|F\d)[^\n]*)$",
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
MAP_COLORS_FILE = BASE_DIR / "room_map_colors.json"
REFERENCE_COLORS_FILE = BASE_DIR / "room_reference_colors.json"
ITEM_COLORS_FILE = BASE_DIR / "item_colors.json"
WEBAPP_RULES_FILE = BASE_DIR / "webapp" / "rules.js"

# Room-title legibility rules (checked by tests/test_room_colors.py).
EXITS_COLOR = "#00ffff"
ROOM_FALLBACK = "#ffffff"
MIN_CONTRAST = 4.5
MIN_EXITS_DISTANCE = 80
# Readable alternatives used when a title color is too close to the exits color.
EXITS_ALTERNATIVES = ["#5fafff", "#00ff00", "#ffff00", "#ff5555", "#ff55ff", "#ff8000", "#c0c0c0", "#ffffff"]


def _rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(rgb)


def contrast_on_black(color):
    """WCAG contrast ratio of a #rrggbb color against #000000."""
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in _rgb(color))
    return (0.2126 * r + 0.7152 * g + 0.0722 * b + 0.05) / 0.05


def color_distance(a, b):
    return sum((x - y) ** 2 for x, y in zip(_rgb(a), _rgb(b))) ** 0.5


def make_readable(color):
    """Deterministically lighten (mix toward white) until contrast on black >= MIN_CONTRAST,
    then, if still too close to the exits color, switch to the nearest readable alternative."""
    color = color.lower()
    for _ in range(40):
        if contrast_on_black(color) >= MIN_CONTRAST:
            break
        color = _hex(round(c + (255 - c) * 0.1) for c in _rgb(color))
    else:
        color = "#ffffff"
    if color_distance(color, EXITS_COLOR) < MIN_EXITS_DISTANCE:
        ok = [c for c in EXITS_ALTERNATIVES if color_distance(c, EXITS_COLOR) >= MIN_EXITS_DISTANCE]
        color = min(ok, key=lambda c: (color_distance(c, color), c))
    return color


def _readable_table(table, adjustments):
    out = {}
    for key, color in table.items():
        fixed = make_readable(color)
        if fixed != color.lower():
            adjustments.append((color.lower(), fixed))
        out[key] = fixed
    return out


def build_rules_data(verbose=False):
    """Return the full compiled rules dict (RULES_DATA + room color tables)."""
    adjustments = []
    if ROOMS_FILE.exists():
        with open(ROOMS_FILE, 'r', encoding='utf-8') as rf:
            rooms_catalog = json.load(rf)
        RULES_DATA["room_colors"] = _readable_table({k.lower(): v for k, v in rooms_catalog.items()}, adjustments)
        if verbose:
            print(f"Loaded {len(RULES_DATA['room_colors'])} room colors from rooms.json")
    elif verbose:
        print("Warning: rooms.json not found!")
    map_colors = {"names": {}, "zones": {}}
    if MAP_COLORS_FILE.exists():
        with open(MAP_COLORS_FILE, 'r', encoding='utf-8') as mf:
            raw = json.load(mf)
        map_colors = {
            "names": _readable_table(raw.get("names", {}), adjustments),
            "zones": _readable_table(raw.get("zones", {}), adjustments),
        }
        if verbose:
            print(f"Loaded {len(map_colors['names'])} names and {len(map_colors['zones'])} zones from room_map_colors.json")
    elif verbose:
        print("Warning: room_map_colors.json not found!")
    RULES_DATA["room_map_colors"] = map_colors
    ref_colors = {"names": {}, "zones": {}}
    if REFERENCE_COLORS_FILE.exists():
        with open(REFERENCE_COLORS_FILE, 'r', encoding='utf-8') as rf:
            raw = json.load(rf)
        ref_colors = {
            "names": {k: [[n, make_readable(c)] for n, c in runs] for k, runs in raw.get("names", {}).items()},
            "zones": _readable_table(raw.get("zones", {}), adjustments),
        }
        if verbose:
            print(f"Loaded {len(ref_colors['names'])} names and {len(ref_colors['zones'])} zones from room_reference_colors.json")
    elif verbose:
        print("Warning: room_reference_colors.json not found!")
    RULES_DATA["room_reference_colors"] = ref_colors
    item_colors = {}
    if ITEM_COLORS_FILE.exists():
        with open(ITEM_COLORS_FILE, 'r', encoding='utf-8') as itf:
            item_colors = json.load(itf)
        if verbose:
            print(f"Loaded {len(item_colors)} colored items from item_colors.json")
    elif verbose:
        print("Warning: item_colors.json not found!")
    RULES_DATA["item_colors"] = item_colors
    RULES_DATA["room_fallback_color"] = ROOM_FALLBACK
    if verbose:
        pairs = sorted(set(adjustments))
        print(f"Adjusted {len(adjustments)} room colors ({len(pairs)} distinct): "
              + ", ".join(f"{a}->{b}" for a, b in pairs))
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

