"""
Reinos de Leyenda (RL) Colorizer Engine (v5)
Transforms plain-text MUD logs into clean, accurate HTML formatted with terminal colors.
"""

import re
import json
import html
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RULES_FILE = BASE_DIR / "rules.json"

MUDLET_HEADER = (
    "<!DOCTYPE HTML PUBLIC '-//W3C//DTD HTML 4.01//EN' 'http://www.w3.org/TR/html4/strict.dtd'>\n"
    "<html>\n"
    " <head>\n"
    "  <meta http-equiv='content-type' content='text/html; charset=utf-8'>  <meta name='generator' content='Mudlet MUD Client version: 4.19.1'>\n"
    "  <title>Mudlet, main console extract from Reinos de Leyenda profile</title>\n"
    "  <style type='text/css'>\n"
    "   <!-- body { font-family: 'Bitstream Vera Sans Mono', 'Courier New', 'Monospace', 'Courier'; font-size: 100%; line-height: 1.125em; white-space: nowrap; color:rgb(255,255,255); background-color:rgb(0,0,0);}\n"
    "        span { white-space: pre-wrap; } -->\n"
    "  </style>\n"
    "  </head>\n"
    "  <body><div>"
)
MUDLET_FOOTER = " </div></body>\n</html>"
PROMPT_PREFIX_RE = re.compile(r'^([>\]](?:[ \t]+|$))(.*)$')
DEFAULT_MUDLET_STYLE = "color: rgb(192,192,192); background: rgb(0,0,0); "


def decode_log_bytes(raw):
    """Decode log bytes: strict UTF-8 first, windows-1252 fallback.

    Mudlet logs are UTF-8; VIPMud logs are windows-1252. Mirrors the webapp
    (TextDecoder utf-8 fatal -> windows-1252).
    """
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def read_text_file(path):
    """Read a log file with the utf-8 -> cp1252 fallback."""
    return decode_log_bytes(Path(path).read_bytes())


def hex_to_rgb(hex_str):
    h = hex_str.strip().lstrip("#")
    if len(h) == 3:
        return int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16)
    if len(h) == 6:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 192, 192, 192


def parse_color_to_rgb(val):
    if not val:
        return None
    val = val.strip()
    if val.startswith("#"):
        return hex_to_rgb(val)
    m = re.match(r"rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", val, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    named = {
        'white': (255, 255, 255),
        'silver': (192, 192, 192),
        'gray': (128, 128, 128),
        'green': (0, 128, 0),
        'red': (255, 0, 0),
        'yellow': (255, 255, 0),
        'blue': (8, 0, 255),
        'cyan': (0, 255, 255),
        'magenta': (255, 0, 255),
        'black': (0, 0, 0),
    }
    return named.get(val.lower(), (192, 192, 192))


def style_to_mudlet(style_str):
    color_m = re.search(r'color:\s*([^;"]+)', style_str, re.IGNORECASE)
    bg_m = re.search(r'background(?:-color)?:\s*([^;"]+)', style_str, re.IGNORECASE)

    fg_rgb = (192, 192, 192)
    if color_m:
        parsed = parse_color_to_rgb(color_m.group(1))
        if parsed:
            fg_rgb = parsed

    bg_rgb = (0, 0, 0)
    if bg_m:
        parsed = parse_color_to_rgb(bg_m.group(1))
        if parsed:
            bg_rgb = parsed

    if "underline" in style_str.lower():
        return f"color: rgb({fg_rgb[0]},{fg_rgb[1]},{fg_rgb[2]}); background: rgb({bg_rgb[0]},{bg_rgb[1]},{bg_rgb[2]});  text-decoration: underline"
    return f"color: rgb({fg_rgb[0]},{fg_rgb[1]},{fg_rgb[2]}); background: rgb({bg_rgb[0]},{bg_rgb[1]},{bg_rgb[2]}); "


def normalize_line_to_mudlet(line_html):
    if not line_html:
        return ""

    converted = re.sub(r'style="([^"]*)"', lambda m: f'style="{style_to_mudlet(m.group(1))}"', line_html)

    tokens = []
    pos = 0
    span_pattern = re.compile(r'<span\s+style="([^"]*)">(.*?)</span>')
    for m in span_pattern.finditer(converted):
        start, end = m.span()
        if start > pos:
            bare = converted[pos:start]
            if bare:
                tokens.append((DEFAULT_MUDLET_STYLE, bare))
        tokens.append((m.group(1), m.group(2)))
        pos = end

    if pos < len(converted):
        bare = converted[pos:]
        if bare:
            tokens.append((DEFAULT_MUDLET_STYLE, bare))

    merged = []
    for s_attr, content in tokens:
        if not content:
            continue
        if merged and merged[-1][0] == s_attr:
            merged[-1] = (s_attr, merged[-1][1] + content)
        else:
            merged.append((s_attr, content))

    return "".join(f'<span style="{s}">{c}</span>' for s, c in merged)


class RLColorizer:
    def __init__(self, rules_path=RULES_FILE, config=None):
        if config is not None:
            self.config = config
        else:
            with open(rules_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)

        self.rules = sorted(self.config['rules'], key=lambda r: r.get('priority', 100))
        self.colors = self.config.get('colors', {})
        self.race_colors = self.config.get('race_colors', {})
        self.room_colors = self.config.get('room_colors', {})
        self.theme = self.config.get('theme', {})
        
        self.races_str = r'Hlag|Lag|Melf|Elf|S-e|Gob|Gno|Hum|Orc|S-o|Ena|Mdro|Drow|S-d|Hal|Hlf|Duer|Drg|Min|Mino|Gnl|Gnol|Kob|Org|Orgo|Drax|Ctd|Cent|Kuo|Ggt|S-g'
        self.race_tag_regex = re.compile(rf'\((?:{self.races_str})\)', re.IGNORECASE)
        self.player_entity_regex = re.compile(
            rf'((?:\b(?:un|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s+)?[*|\-~/]*\s*[A-Za-zÁÉÍÓÚáéíóúñÑ0-9\x27_-]+(?:\s+[|*\-~/]+)?\s*\((?:{self.races_str})\)(?:es)?(?:\s*[|*\-~/]+)?)',
            re.IGNORECASE
        )
        self.cardinal_regex = re.compile(r'\b(norte|sur|este|oeste|noreste|noroeste|sudeste|sudoeste|arriba|abajo|n|s|e|o|ne|no|se|so)\b', re.IGNORECASE)
        
        self.detected_client = None
        self._init_preprocess(self.config.get('preprocess') or {})

        # Precompile regular expressions
        self.compiled_rules = []
        self.marker_rules = []
        for r in self.rules:
            (self.marker_rules if r.get('type') == 'composite_marker' else self.compiled_rules).append({
                **r,
                '_regex': re.compile(r['pattern']),
                '_categories': [{**c, '_regex': re.compile(c['pattern'])} for c in r.get('categories', [])],
            })

    def colorize_line(self, line):
        raw_text = line.rstrip('\r\n')
        raw_text = raw_text.replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&')
        
        if not raw_text.strip():
            return ""

        # A leading prompt symbol ("> " / "] ") is split off verbatim; rules see the rest.
        prompt = ""
        pm = PROMPT_PREFIX_RE.match(raw_text)
        if pm:
            prompt, raw_text = pm.group(1), pm.group(2)
        prompt_html = f'<span style="color: #c0c0c0;">{html.escape(prompt)}</span>' if prompt else ""
        if prompt and not raw_text:
            return normalize_line_to_mudlet(prompt_html)

        line_html = None
        # Match rules in priority order
        for rule in self.compiled_rules:
            if rule.get('prompt_only') and not prompt:
                continue
            m = rule['_regex'].match(raw_text)
            if not m:
                continue
                
            rule_type = rule.get('type')
            
            # 1. Composite Prompt Handler
            if rule_type == 'composite_prompt_extended':
                line_html = self._render_prompt_extended(m)
                break

            elif rule_type == 'composite_prompt_vitals':
                line_html = self._render_prompt_vitals(m)
                break
                
            # 2. Composite HP Delta Handler
            elif rule_type == 'composite_hp_delta':
                prefix, delta = m.groups()
                d_color = "#ff0000" if delta.startswith('-') else "#00ff00"
                line_html = f'<span style="color: #008000;">{html.escape(prefix)}</span><span style="color: {d_color}; font-weight: bold;">{html.escape(delta)}</span>'
                break
                
            # 3. Composite Movement Handler
            elif rule_type == 'composite_movement':
                line_html = self._render_movement(m)
                break
                
            # 4. Composite Tirada Handler
            elif rule_type == 'composite_tirada':
                line_html = self._render_tirada(m)
                break
                
            # 5. Composite Info Handler
            elif rule_type == 'composite_info':
                line_html = self._render_info(m)
                break
                
            # 6. Composite Spell Completion
            elif rule_type == 'composite_spell_completion':
                line_html = self._render_spell_completion(m)
                break
                
            # 7. Composite Magic Missiles
            elif rule_type == 'composite_magic_missiles':
                prompt_sym, prefix_sym, rest = m.groups()
                lead_html = '<span style="color: #c0c0c0;">&gt; </span>' if prompt_sym else ''
                p_html = '<span style="color: #0000ff;">#</span> ' if prefix_sym else ''
                line_html = f'{lead_html}{p_html}<span style="color: #8cc4ff;">{html.escape(rest)}</span>'
                break
                
            # 8. Composite Enemy Maneuver
            elif rule_type == 'composite_enemy_maneuver':
                line_html = self._render_enemy_maneuver(m)
                break

            # 9. Composite Player Combat
            elif rule_type == 'composite_player_combat':
                line_html = self._render_player_combat(m)
                break

            # 12. Composite Follower Player
            elif rule_type == 'composite_follower_player':
                line_html = self._render_follower_player(m)
                break

            # 10. Composite Room Player
            elif rule_type == 'composite_room_player':
                line_html = self._render_room_player(m)
                break

            # 11. Composite Room NPC
            elif rule_type == 'composite_room_npc':
                line_html = self._render_room_npc(m)
                break

            # 13. Composite Room Exits
            elif rule_type == 'composite_room_exits':
                res = self._render_room_exits(m)
                if res is not None:
                    line_html = res
                    break

            # 14. Composite Room Title
            elif rule_type == 'composite_room_title':
                res = self._render_room_title(m)
                if res is not None:
                    line_html = res
                    break
                
            # 15. Direct Regex Replacement
            elif 'replace' in rule:
                line_html = self._apply_template(m, rule['replace'])
                break
                
        if line_html is None:
            escaped = html.escape(raw_text)
            line_html = f'<span style="color: {self.theme.get("default_fg", "#c0c0c0")};">{escaped}</span>'
            
        marker = self._marker_color(raw_text)
        if marker:
            line_html = self._apply_marker(line_html, *marker)
        return normalize_line_to_mudlet(prompt_html + line_html)

    @staticmethod
    def _prompt_delta_html(ws, delta):
        """` (+12)` after a stat: only the signed number is colored; a zero delta stays default."""
        color = "#ff0000" if delta.startswith('-') else ("#00ff00" if delta.startswith('+') else None)
        number = html.escape(delta)
        if color and delta.lstrip('+-').strip('0'):
            number = f'<span style="color: {color};">{number}</span>'
        return f'{html.escape(ws)}(' + number + ')'

    def _render_prompt_extended(self, m):
        lead, pvs, pvs_ws, pvs_delta, pe, pe_ws, pe_delta, extra = m.groups()
        out = [html.escape(lead or '')]
        out.append(f'<span style="color: #008000;">{html.escape(pvs)}</span>')
        if pvs_delta:
            out.append(self._prompt_delta_html(pvs_ws, pvs_delta))
        if pe:
            out.append(f'<span style="color: #008000;">{html.escape(pe)}</span>')
        if pe_delta:
            out.append(self._prompt_delta_html(pe_ws, pe_delta))
        if extra:
            out.append(f'<span style="color: #008000;">{html.escape(extra)}</span>')
        return "".join(out)

    def _render_prompt_vitals(self, m):
        """`Pvs: 4381(4381)  Pe: 550(980)  Fe: 67(220) ...`: numbers colored by health, Fe white."""
        lead, label, cur, mid, mx, rest, fe, tail = m.groups()
        ratio = int(cur) / int(mx) if int(mx) else 1
        color = "#ff0000" if ratio < 0.3 else "#00ff00"
        return (
            f'{html.escape(lead)}{html.escape(label)}'
            f'<span style="color: {color};">{html.escape(cur)}</span>{html.escape(mid)}'
            f'<span style="color: {color};">{html.escape(mx)}</span>{html.escape(rest)}'
            f'<span style="color: #ffffff;">{html.escape(fe)}</span>{html.escape(tail)}'
        )

    def get_race_color(self, text):
        if not text:
            return "#ffff00"
        m = self.race_tag_regex.search(text)
        if m:
            raw_tag = m.group(0)[1:-1].lower()
            return self.race_colors.get(raw_tag, "#ffff00")
        return "#ffff00"

    def _colorize_player_entities(self, text):
        parts = []
        last_end = 0
        for m in self.player_entity_regex.finditer(text):
            start, end = m.span(1)
            if start > last_end:
                parts.append(html.escape(text[last_end:start]))
            raw_matched = m.group(1)
            token = raw_matched.strip()
            leading_ws = raw_matched[:len(raw_matched) - len(raw_matched.lstrip())]
            trailing_ws = raw_matched[len(raw_matched.rstrip()):]
            color = self.get_race_color(token)
            parts.append(html.escape(leading_ws) + f'<span style="color: {color};">{html.escape(token)}</span>' + html.escape(trailing_ws))
            last_end = end
        if last_end < len(text):
            parts.append(html.escape(text[last_end:]))
        return "".join(parts)

    def _render_movement(self, m):
        prompt_sym, actor, verb, dest, period = m.groups()
        prompt_html = '<span style="color: #c0c0c0;">&gt; </span>' if prompt_sym else ''
        tag_m = self.race_tag_regex.search(actor)
        if tag_m:
            actor_color = self.get_race_color(actor)
            actor_html = f'<span style="color: {actor_color}; font-weight: bold;">{html.escape(actor)}</span>'
        else:
            actor_html = f'<span style="color: #c0c0c0;">{html.escape(actor)}</span>'
        verb_html = f'<span style="color: #ffffff;">{html.escape(verb)}</span>'
        dest_html = f'<span style="color: #c0c0c0;">{html.escape(dest + period)}</span>'
        return f'{prompt_html}{actor_html} {verb_html} {dest_html}'

    def get_room_color(self, room_title):
        """(color, n) with the first n characters of the title to color, or None when unknown.

        An exact catalog match colors the whole title; a zone match colors only the zone
        prefix, up to the ":" or the first "-" (the reference leaves the rest default).
        """
        if not room_title:
            return None
        clean_title = re.sub(r'\s+', ' ', re.sub(r'\s*-\s*', ' - ', room_title)).strip().lower()
        clean_title = re.sub(r'\s*:\s*', ': ', clean_title)
        if clean_title in self.room_colors:
            return self.room_colors[clean_title], len(room_title)
        if ':' in clean_title:
            zone = clean_title.split(':')[0].strip()
            if zone in self.room_colors:
                return self.room_colors[zone], room_title.index(':') + 1
        if ' - ' in clean_title:
            zone = clean_title.split(' - ')[0].strip()
            if zone in self.room_colors:
                return self.room_colors[zone], len(room_title[:room_title.index('-')].rstrip())
        return None

    def _room_title_html(self, room_title):
        found = self.get_room_color(room_title)
        if not found:
            return html.escape(room_title)
        color, n = found
        return f'<span style="color: {color};">{html.escape(room_title[:n])}</span>{html.escape(room_title[n:])}'

    def _render_room_exits(self, m):
        prompt_sym, room_title, sep, exits = m.groups()
        title_html = self._room_title_html(room_title)
        if not self.get_room_color(room_title):
            title_html = f'<span style="color: #008000; font-weight: bold;">{html.escape(room_title)}</span>'
        return f'{title_html}{html.escape(sep)}<span style="color: #00ffff;">{html.escape(exits)}</span>'

    def _render_room_title(self, m):
        prompt_sym, room_title = m.groups()
        if not self.get_room_color(room_title):
            return None
        return self._room_title_html(room_title)

    def _render_tirada(self, m):
        b1, tag, body, result, b2 = m.groups()
        res_color = "#00ff00" if "Éxito" in result or "Exito" in result else "#ff0000"
        return (
            f'<span style="color: #c0c0c0;">[</span>'
            f'<span style="color: #ffff00; font-weight: bold;">{tag}</span>'
            f'<span style="color: #c0c0c0;">{html.escape(body)}</span>'
            f'<span style="color: {res_color}; font-weight: bold;">{html.escape(result)}</span>'
            f'<span style="color: #c0c0c0;">{html.escape(b2)}</span>'
        )

    def _render_info(self, m):
        b1, tag, sep, rest = m.groups()
        tag_colors = {
            'INFO': '#ffff00',
            'AYUDA': '#ff00ff',
            'ADVERTENCIA': '#ffaa00',
            'ERROR': '#ff0000'
        }
        tcolor = tag_colors.get(tag, '#ffff00')
        return (
            f'<span style="color: #c0c0c0;">[</span>'
            f'<span style="color: {tcolor}; font-weight: bold;">{tag}</span>'
            f'<span style="color: #c0c0c0;">{sep}{html.escape(rest)}</span>'
        )

    def _render_room_player(self, m):
        prompt_sym, players, sep, verb = m.groups()
        prompt_html = '<span style="color: #c0c0c0;">&gt; </span>' if prompt_sym else ''
        colored_players = self._colorize_player_entities(players)
        return f'{prompt_html}{colored_players}<span style="color: #c0c0c0;">{html.escape(sep)}{html.escape(verb)}.</span>'

    def _render_room_npc(self, m):
        prompt_sym, npc, sep, verb = m.groups()
        prompt_html = '<span style="color: #c0c0c0;">&gt; </span>' if prompt_sym else ''
        return f'{prompt_html}<span style="color: #c0c0c0;">{html.escape(npc)}{html.escape(sep)}{html.escape(verb)}.</span>'

    def _render_follower_player(self, m):
        prompt_sym, actor, verb = m.groups()
        prompt_html = '<span style="color: #c0c0c0;">&gt; </span>' if prompt_sym else ''
        actor_color = self.get_race_color(actor)
        return f'{prompt_html}<span style="color: {actor_color}; font-weight: bold;">{html.escape(actor)}</span> <span style="color: #c0c0c0;">{html.escape(verb)}.</span>'

    def _render_spell_completion(self, m):
        line = m.group(0)
        parts = []
        pos = 0
        for q_m in re.finditer(r"'[^']+'", line):
            start, end = q_m.span()
            if start > pos:
                parts.append(f'<span style="color: #c0c0c0;">{html.escape(line[pos:start])}</span>')
            parts.append(f'<span style="color: #00ffff;">{html.escape(q_m.group(0))}</span>')
            pos = end
        if pos < len(line):
            parts.append(f'<span style="color: #c0c0c0;">{html.escape(line[pos:])}</span>')
        return "".join(parts)

    def _render_enemy_maneuver(self, m):
        prompt_sym, alert_sym, actor, sep, verb, rest = m.groups()
        prompt_html = '<span style="color: #c0c0c0;">&gt; </span>' if prompt_sym else ''
        alert_html = f'<span style="color: #ff0000; font-weight: bold;">{html.escape(alert_sym)}</span>' if alert_sym else ''
        tag_m = self.race_tag_regex.search(actor)
        if tag_m:
            actor_color = self.get_race_color(actor)
        else:
            actor_color = "#ff4444"
        actor_html = f'<span style="color: {actor_color}; font-weight: bold;">{html.escape(actor)}</span>'
        action_html = f'<span style="color: #ff8080;">{html.escape(verb + (rest or ""))}</span>'
        return f'{prompt_html}{alert_html}{actor_html}{html.escape(sep)}{action_html}'

    def _render_player_combat(self, m):
        prompt_sym, hash_prefix, hash_body, star_prefix, verb, rest = m.groups()
        prompt_html = '<span style="color: #c0c0c0;">&gt; </span>' if prompt_sym else ''
        
        if hash_prefix:
            prefix_sym = hash_prefix
            body = hash_body or ""
        else:
            prefix_sym = star_prefix or ""
            body = (verb or "") + (rest or "")
            
        full_line = prefix_sym + body
        
        # Check if dodge, parry or miss
        if any(w in full_line.lower() for w in ['esquiva tu ataque', 'fallas tu ataque', 'bloquea tu', 'consigue parar', 'consigue esquivar']):
            return f'{prompt_html}<span style="color: #808080;">{html.escape(full_line)}</span>'
            
        # Highlight damage ranges/brackets like (290-599) or [123]
        parts = []
        pos = 0
        bracket_re = re.compile(r'(\()(\d+)(?:(-)(\d+))?(\))')
        for b_m in bracket_re.finditer(body):
            start, end = b_m.span()
            if start > pos:
                parts.append(f'<span style="color: #00ff00;">{html.escape(body[pos:start])}</span>')
            b1, d1, sep, d2, b2 = b_m.groups()
            parts.append(f'<span style="color: #ffff00;">{b1}</span><span style="color: #ff0000; font-weight: bold;">{d1}</span>')
            if sep:
                parts.append(f'<span style="color: #ffffff;">{sep}</span><span style="color: #ff0000; font-weight: bold;">{d2}</span>')
            parts.append(f'<span style="color: #ffff00;">{b2}</span>')
            pos = end
        if pos < len(body):
            parts.append(f'<span style="color: #00ff00;">{html.escape(body[pos:])}</span>')
            
        combat_html = "".join(parts)
        
        prefix_html = ""
        if prefix_sym:
            if '#' in prefix_sym:
                prefix_html = '<span style="color: #008000;">#</span>' + html.escape(prefix_sym[1:])
            elif '*' in prefix_sym:
                prefix_html = '<span style="color: #008000;">*</span>' + html.escape(prefix_sym[1:])
                
        return f'{prompt_html}{prefix_html}{combat_html}'

    def _marker_color(self, text):
        """Color of the leading `#` / `*` / `+` marker, or None when the line has no marker."""
        for rule in self.marker_rules:
            m = rule['_regex'].match(text)
            if not m:
                continue
            for cat in rule['_categories']:
                if cat['_regex'].search(m.group(2)):
                    return m.group(1), cat['color']
            return m.group(1), rule['color']
        return None

    @staticmethod
    def _apply_marker(line_html, ch, color):
        """Recolor the first visible character (the marker); the rest of the line is untouched."""
        h = re.sub(r'<span style="[^"]*"></span>', '', line_html)
        mark = f'<span style="color: {color};">{ch}</span>'
        m = re.match(r'<span style="([^"]*)">', h)
        if m and h[m.end():].startswith(ch):
            return mark + f'<span style="{m.group(1)}">' + h[m.end() + len(ch):]
        if h.startswith(ch):
            return mark + h[len(ch):]
        return line_html

    def _apply_template(self, m, template):
        res = template
        for i, val in enumerate(m.groups(), start=1):
            escaped_val = html.escape(val if val is not None else "")
            res = res.replace(f"${i}", escaped_val)
        return res

    # ------------------------------------------------------------------
    # Preprocess layer: data-driven sanitization (see "preprocess" in rules.json)
    # ------------------------------------------------------------------
    def _init_preprocess(self, cfg):
        self.pre_clients = []
        for c in cfg.get('clients', []):
            self.pre_clients.append({
                'id': c['id'],
                'label': c.get('label', c['id']),
                'signatures': [re.compile(p) for p in c.get('signatures', [])],
            })
        self.pre_rules = []
        for r in cfg.get('rules', []):
            comp = dict(r)
            for key in ('pattern', 'start', 'end', 'until', 'candidate', 'record', 'echo'):
                if key in r:
                    comp['_' + key] = re.compile(r[key])
            self.pre_rules.append(comp)

    def client_label(self, client_id):
        for c in self.pre_clients:
            if c['id'] == client_id:
                return c['label']
        return None

    def detect_client(self, text_or_lines):
        """Id of the client whose signatures match the most lines (ties: first declared), or None."""
        if isinstance(text_or_lines, str):
            lines = text_or_lines.replace('\r\n', '\n').split('\n')
        else:
            lines = text_or_lines
        best_id, best_hits = None, 0
        for c in self.pre_clients:
            hits = 0
            for line in lines:
                for sig in c['signatures']:
                    if sig.search(line):
                        hits += 1
                        break
            if hits > best_hits:
                best_id, best_hits = c['id'], hits
        return best_id

    @staticmethod
    def _expand_template(template, m):
        def sub(t):
            idx = int(t.group(1))
            if idx > m.re.groups:
                return ''
            g = m.group(idx)
            return g if g is not None else ''
        return re.sub(r'\$(\d)', sub, template)

    def preprocess_text(self, text, client=None):
        """Sanitize a raw log (login/credentials, client status blocks) before colorizing.

        client: explicit client id, or None to auto-detect. Rules with a "clients"
        list only run when the client is in that list; rules without it are
        client-agnostic. Sets self.detected_client. Returns the cleaned text.
        """
        lines = (text or '').replace('\r\n', '\n').split('\n')
        if client is None:
            client = self.detect_client(lines)
        self.detected_client = client
        rules = [r for r in self.pre_rules if not r.get('clients') or client in r['clients']]
        if not rules:
            return '\n'.join(lines)

        out = []
        changed = False
        last_keys = {}
        secrets = set()   # tokens removed as login echoes in this input
        last_login = None  # input index of the last line handled by a login rule
        run = None  # status-block run ending right before the current line: {'group', 'kept'}
        n = len(lines)
        i = 0
        while i < n:
            line = lines[i]
            handled = False
            for r in rules:
                kind = r['kind']
                if kind == 'rewrite':
                    m = r['_pattern'].search(line)
                    if m:
                        new_line = self._expand_template(r['replace'], m)
                        if new_line != line:
                            line = new_line
                            changed = True
                    continue
                if kind == 'drop_before':
                    if not r['_pattern'].search(line):
                        continue
                    found = []
                    k = len(out) - 1
                    if last_login is not None and i - last_login <= 2:
                        k = -1  # lines before were already handled by the login rule that just fired
                    while k >= 0 and len(found) < r.get('max_lines', 3):
                        if re.match(r'^[ \t]*$', out[k]):
                            k -= 1
                            continue
                        if not r['_candidate'].search(out[k]):
                            break
                        found.append(k)
                        k -= 1
                    if found:
                        for k in found:
                            secrets.add(re.sub(r'[ \t]+$', '', out[k]))
                        gone = set(found)
                        out = [x for idx, x in enumerate(out) if idx not in gone]
                        changed = True
                    if r.get('login'):
                        last_login = i
                    continue
                if kind == 'drop_secret':
                    if not (last_login is not None and i - last_login <= r.get('window', 6)
                            and re.sub(r'[ \t]+$', '', line) in secrets):
                        continue
                    i += 1
                    changed = True
                    run = None
                    handled = True
                    break
                if kind == 'drop_block':
                    if not r['_start'].search(line):
                        continue
                    limit = n - 1 if r.get('max_lines') is None else min(n - 1, i + r['max_lines'])
                    end_idx = None
                    for j in range(i + 1, limit + 1):
                        if r['_end'].search(lines[j]):
                            end_idx = j
                            break
                    if end_idx is None:
                        continue
                    i = end_idx + 1 if r.get('include_end') else end_idx
                elif kind == 'drop_after':
                    if not r['_pattern'].search(line):
                        continue
                    limit = min(n, i + 1 + r.get('max_lines', 8))
                    j = i + 1
                    while j < limit and not r['_until'].search(lines[j]):
                        # Stop at the first real server line so fragments keep their content.
                        if '_echo' in r and lines[j].strip() and not r['_echo'].search(lines[j]):
                            break
                        j += 1
                    if '_record' in r:
                        for k in range(i + 1, j):
                            if r['_record'].search(lines[k]):
                                secrets.add(re.sub(r'[ \t]+$', '', lines[k]))
                    if j < limit and r.get('include_until') and r['_until'].search(lines[j]):
                        j += 1
                    i = j
                elif kind == 'drop_closer':
                    if not (run is not None and run['group'] == r.get('group') and run['kept'] == 0
                            and r['_pattern'].search(line)):
                        continue
                    i += 1
                else:
                    m = r['_pattern'].search(line)
                    if not m:
                        continue
                    if kind == 'drop':
                        keep = False
                        if r.get('login'):
                            last_login = i
                    elif kind == 'dedupe_on_change':
                        if 'key' in r:
                            key = self._expand_template(r['key'], m)
                        elif 'key_group' in r:
                            key = m.group(r['key_group']) or ''
                        else:
                            key = line
                        key = re.sub(r'[ \t]+$', '', key)
                        scope = r.get('scope_id', r['id'])
                        keep = last_keys.get(scope) != key
                        last_keys[scope] = key
                    else:
                        continue
                    group = r.get('group')
                    if group:
                        if run is None or run['group'] != group:
                            run = {'group': group, 'kept': 0}
                        if keep:
                            run['kept'] += 1
                    else:
                        run = None
                    if keep:
                        out.append(line)
                    else:
                        changed = True
                    i += 1
                    handled = True
                    break
                # drop_block / drop_after / drop_closer: lines consumed
                if r.get('login'):
                    last_login = i - 1
                changed = True
                run = None
                handled = True
                break
            if handled:
                continue
            out.append(line)
            run = None
            i += 1

        if changed:
            collapsed = []
            for line in out:
                if re.match(r'^[ \t]*$', line) and (not collapsed or re.match(r'^[ \t]*$', collapsed[-1])):
                    continue
                collapsed.append(line)
            out = collapsed
        return '\n'.join(out)

    def colorize_text(self, plain_text, preprocess=True, client=None):
        if preprocess:
            plain_text = self.preprocess_text(plain_text, client)
        trimmed = (plain_text or "").replace('\r\n', '\n').rstrip('\n')
        normalized = re.sub(r'\n{3,}', '\n\n', trimmed)
        if not normalized:
            return MUDLET_HEADER + " </div></body>\n</html>"

        lines = normalized.split('\n')
        rendered_lines = [self.colorize_line(line) for line in lines]
        body_content = "\n".join(r + "<br>" for r in rendered_lines)

        return f"{MUDLET_HEADER}{body_content}\n </div></body>\n</html>"


def main(argv=None):
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="Colorize a Reinos de Leyenda text log into Mudlet-style HTML.")
    ap.add_argument("input", help="plain-text log (UTF-8 or windows-1252)")
    ap.add_argument("-o", "--output", help="output HTML file (default: stdout)")
    ap.add_argument("--client", help="force a client id (e.g. vipmud, mudlet) instead of auto-detection")
    ap.add_argument("--no-preprocess", action="store_true", help="skip login/status sanitization")
    args = ap.parse_args(argv)

    colorizer = RLColorizer()
    text = read_text_file(args.input)
    result = colorizer.colorize_text(text, preprocess=not args.no_preprocess, client=args.client)
    if args.output:
        Path(args.output).write_text(result, encoding="utf-8", newline="")
    else:
        sys.stdout.buffer.write(result.encode("utf-8"))
    if not args.no_preprocess:
        label = colorizer.client_label(colorizer.detected_client)
        print(f"Detected client: {label or 'unknown'}", file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
