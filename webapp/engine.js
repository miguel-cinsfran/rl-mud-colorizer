/**
 * Reinos de Leyenda (RL) Colorizer Engine - JavaScript Edition (v5)
 * Mirrors engine.py with 100% fidelity.
 */

function escapeHtml(str) {
    if (!str) return '';
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#x27;');
}

// Python's `\w` is Unicode-aware (matches "é", "ñ"...); JavaScript's is ASCII-only.
// Rules are authored once for both engines, so `\w` is expanded to an explicit
// Latin-script class (ASCII + Latin-1 + Latin Extended-A/B) to keep parity.
const PY_WORD_CHARS = 'A-Za-z0-9_ªµºÀ-ÖØ-öø-ɏ';

function toSharedRegex(pattern) {
    let out = '';
    let inClass = false;
    for (let i = 0; i < pattern.length; i++) {
        const ch = pattern[i];
        if (ch === '\\') {
            const next = pattern[i + 1];
            if (next === 'w') {
                out += inClass ? PY_WORD_CHARS : '[' + PY_WORD_CHARS + ']';
            } else {
                out += ch + (next === undefined ? '' : next);
            }
            i++;
        } else {
            if (ch === '[') inClass = true;
            else if (ch === ']') inClass = false;
            out += ch;
        }
    }
    return new RegExp(out);
}

const MUDLET_HEADER = `<!DOCTYPE HTML PUBLIC '-//W3C//DTD HTML 4.01//EN' 'http://www.w3.org/TR/html4/strict.dtd'>
<html>
 <head>
  <meta http-equiv='content-type' content='text/html; charset=utf-8'>  <meta name='generator' content='Mudlet MUD Client version: 4.19.1'>
  <title>Mudlet, main console extract from Reinos de Leyenda profile</title>
  <style type='text/css'>
   <!-- body { font-family: 'Bitstream Vera Sans Mono', 'Courier New', 'Monospace', 'Courier'; font-size: 100%; line-height: 1.125em; white-space: nowrap; color:rgb(255,255,255); background-color:rgb(0,0,0);}
        span { white-space: pre-wrap; } -->
  </style>
  </head>
  <body><div>`;

const MUDLET_FOOTER = ` </div></body>\n</html>`;
const PROMPT_PREFIX_RE = /^([>\]](?:[ \t]+|$))(.*)$/;
const DEFAULT_MUDLET_STYLE ="color: rgb(192,192,192); background: rgb(0,0,0); ";
// Room titles this close to the body silver (#c0c0c0) are rendered white (mirrors engine.py).
const SILVER_TITLE_DISTANCE = 30;

function hexToRgb(hexStr) {
    let h = hexStr.trim().replace(/^#/, '');
    if (h.length === 3) {
        return [
            parseInt(h[0] + h[0], 16),
            parseInt(h[1] + h[1], 16),
            parseInt(h[2] + h[2], 16)
        ];
    }
    if (h.length === 6) {
        return [
            parseInt(h.slice(0, 2), 16),
            parseInt(h.slice(2, 4), 16),
            parseInt(h.slice(4, 6), 16)
        ];
    }
    return [192, 192, 192];
}

function parseColorToRgb(val) {
    if (!val) return null;
    val = val.trim();
    if (val.startsWith('#')) return hexToRgb(val);
    const m = /^rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$/i.exec(val);
    if (m) {
        return [parseInt(m[1], 10), parseInt(m[2], 10), parseInt(m[3], 10)];
    }
    const named = {
        white: [255, 255, 255],
        silver: [192, 192, 192],
        gray: [128, 128, 128],
        green: [0, 128, 0],
        red: [255, 0, 0],
        yellow: [255, 255, 0],
        blue: [8, 0, 255],
        cyan: [0, 255, 255],
        magenta: [255, 0, 255],
        black: [0, 0, 0]
    };
    return named[val.toLowerCase()] || [192, 192, 192];
}

function styleToMudlet(styleStr) {
    const colorM = /color:\s*([^;"]+)/i.exec(styleStr);
    const bgM = /background(?:-color)?:\s*([^;"]+)/i.exec(styleStr);

    let fgRgb = [192, 192, 192];
    if (colorM) {
        const parsed = parseColorToRgb(colorM[1]);
        if (parsed) fgRgb = parsed;
    }

    let bgRgb = [0, 0, 0];
    if (bgM) {
        const parsed = parseColorToRgb(bgM[1]);
        if (parsed) bgRgb = parsed;
    }

    if (styleStr.toLowerCase().includes('underline')) {
        return `color: rgb(${fgRgb[0]},${fgRgb[1]},${fgRgb[2]}); background: rgb(${bgRgb[0]},${bgRgb[1]},${bgRgb[2]});  text-decoration: underline`;
    }
    return `color: rgb(${fgRgb[0]},${fgRgb[1]},${fgRgb[2]}); background: rgb(${bgRgb[0]},${bgRgb[1]},${bgRgb[2]}); `;
}

function normalizeLineToMudlet(lineHtml) {
    if (!lineHtml) return '';

    const converted = lineHtml.replace(/style="([^"]*)"/g, (match, s) => `style="${styleToMudlet(s)}"`);

    const tokens = [];
    let pos = 0;
    const spanPattern = /<span\s+style="([^"]*)">(.*?)<\/span>/g;
    let m;
    while ((m = spanPattern.exec(converted)) !== null) {
        const start = m.index;
        const end = spanPattern.lastIndex;
        if (start > pos) {
            const bare = converted.slice(pos, start);
            if (bare) tokens.push([DEFAULT_MUDLET_STYLE, bare]);
        }
        tokens.push([m[1], m[2]]);
        pos = end;
    }

    if (pos < converted.length) {
        const bare = converted.slice(pos);
        if (bare) tokens.push([DEFAULT_MUDLET_STYLE, bare]);
    }

    const merged = [];
    for (const [sAttr, content] of tokens) {
        if (!content) continue;
        if (merged.length > 0 && merged[merged.length - 1][0] === sAttr) {
            merged[merged.length - 1][1] += content;
        } else {
            merged.push([sAttr, content]);
        }
    }

    return merged.map(([s, c]) => `<span style="${s}">${c}</span>`).join('');
}

class RLColorizerJS {
    constructor(config) {
        this.config = config || (typeof window !== 'undefined' ? window.COLORIZER_RULES : null);
        if (!this.config) {
            throw new Error("No configuration rules provided for RLColorizerJS.");
        }
        this.theme = this.config.theme || {
            bg: "#000000",
            default_fg: "#c0c0c0",
            font_family: "'Bitstream Vera Sans Mono', 'Courier New', monospace"
        };
        this.colors = this.config.colors || {};
        this.raceColors = this.config.race_colors || {};
        this.roomColors = this.config.room_colors || {};
        const mapColors = this.config.room_map_colors || {};
        this.roomMapNames = mapColors.names || {};
        this.roomMapZones = mapColors.zones || {};
        this.roomFallbackColor = this.config.room_fallback_color || '#ffffff';
        
        this.racesStr = "Hlag|Lag|Melf|Elf|S-e|Gob|Gno|Hum|Orc|S-o|Ena|Mdro|Drow|S-d|Hal|Hlf|Duer|Drg|Min|Mino|Gnl|Gnol|Kob|Org|Orgo|Drax|Ctd|Cent|Kuo|Ggt|S-g";
        this.raceTagRegex = new RegExp(`\\((?:${this.racesStr})\\)`, 'i');
        this.playerEntityPattern = `((?:\\b(?:un|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\\s+)?[*|\\-~/]*\\s*[A-Za-zÁÉÍÓÚáéíóúñÑ0-9\\x27_-]+(?:\\s+[|*\\-~/]+)?\\s*\\((?:${this.racesStr})\\)(?:es)?(?:\\s*[|*\\-~/]+)?)`;
        this.cardinalRegex = /\b(norte|sur|este|oeste|noreste|noroeste|sudeste|sudoeste|arriba|abajo|n|s|e|o|ne|no|se|so)\b/i;
        
        this.detectedClient = null;
        this._context = null; // block context set by a `sets_context` rule (e.g. group status list)
        this._initPreprocess(this.config.preprocess || {});

        const sortedRules = [...this.config.rules].sort((a, b) => (a.priority || 100) - (b.priority || 100));
        const compiled = sortedRules.map(r => ({
            ...r,
            _regex: toSharedRegex(r.pattern),
            _categories: (r.categories || []).map(c => ({ ...c, _regex: toSharedRegex(c.pattern) }))
        }));
        this.markerRules = compiled.filter(r => r.type === 'composite_marker');
        this.compiledRules = compiled.filter(r => r.type !== 'composite_marker');
    }

    colorizeLine(line) {
        let rawText = line.replace(/\r?\n$/, '');
        rawText = rawText.replace(/&gt;/g, '>').replace(/&lt;/g, '<').replace(/&amp;/g, '&');

        if (!rawText.trim()) {
            this._context = null;
            return "";
        }

        // A leading prompt symbol ("> " / "] ") is split off verbatim; rules see the rest.
        let prompt = "";
        const pm = PROMPT_PREFIX_RE.exec(rawText);
        if (pm) {
            prompt = pm[1];
            rawText = pm[2];
        }
        const promptHtml = prompt ? `<span style="color: #c0c0c0;">${escapeHtml(prompt)}</span>` : '';
        if (prompt && !rawText) {
            return normalizeLineToMudlet(promptHtml);
        }

        let lineHtml = null;
        let usedRule = null;
        for (const rule of this.compiledRules) {
            if (rule.prompt_only && !prompt) continue;
            if (rule.requires_context && rule.requires_context !== this._context) continue;
            const m = rule._regex.exec(rawText);
            if (!m) continue;
            usedRule = rule;

            const type = rule.type;

            // 1. Composite Prompt Handler
            if (type === 'composite_prompt_extended') {
                lineHtml = this._renderPromptExtended(m);
                break;
            }
            else if (type === 'composite_health_tier') {
                lineHtml = this._renderHealthTier(rule, m);
                break;
            }
            else if (type === 'composite_prompt_vitals') {
                lineHtml = this._renderPromptVitals(m);
                break;
            }
            // 2. Composite HP Delta Handler
            else if (type === 'composite_hp_delta') {
                const prefix = m[1];
                const delta = m[2];
                const dColor = delta.startsWith('-') ? "#ff0000" : "#00ff00";
                lineHtml = `<span style="color: #008000;">${escapeHtml(prefix)}</span><span style="color: ${dColor}; font-weight: bold;">${escapeHtml(delta)}</span>`;
                break;
            }
            // 3. Composite Movement Handler
            else if (type === 'composite_movement') {
                lineHtml = this._renderMovement(m);
                break;
            }
            // 4. Composite Tirada Handler
            else if (type === 'composite_tirada') {
                lineHtml = this._renderTirada(m);
                break;
            }
            // 5. Composite Info Handler
            else if (type === 'composite_info') {
                lineHtml = this._renderInfo(m);
                break;
            }
            // 6. Composite Spell Completion
            else if (type === 'composite_spell_completion') {
                lineHtml = this._renderSpellCompletion(m);
                break;
            }
            // 7. Composite Magic Missiles
            else if (type === 'composite_magic_missiles') {
                const promptSym = m[1];
                const prefixSym = m[2];
                const rest = m[3];
                const promptHtml = promptSym ? '<span style="color: #c0c0c0;">&gt; </span>' : '';
                const pHtml = prefixSym ? '<span style="color: #0000ff;">#</span> ' : '';
                lineHtml = `${promptHtml}${pHtml}<span style="color: #8cc4ff;">${escapeHtml(rest)}</span>`;
                break;
            }
            // 8. Composite Enemy Maneuver
            else if (type === 'composite_enemy_maneuver') {
                lineHtml = this._renderEnemyManeuver(m);
                break;
            }
            // 9. Composite Player Combat
            else if (type === 'composite_player_combat') {
                lineHtml = this._renderPlayerCombat(m);
                break;
            }
            // 12. Composite Follower Player
            else if (type === 'composite_follower_player') {
                lineHtml = this._renderFollowerPlayer(m);
                break;
            }
            // 10. Composite Room Player
            else if (type === 'composite_room_player') {
                lineHtml = this._renderRoomPlayer(m);
                break;
            }
            // 11. Composite Room NPC
            else if (type === 'composite_room_npc') {
                lineHtml = this._renderRoomNpc(m);
                break;
            }
            // 13. Composite Room Exits
            else if (type === 'composite_room_exits') {
                const res = this._renderRoomExits(m);
                if (res !== null) {
                    lineHtml = res;
                    break;
                }
            }
            // 14. Composite Room Title
            else if (type === 'composite_room_title') {
                const res = this._renderRoomTitle(m);
                if (res !== null) {
                    lineHtml = res;
                    break;
                }
            }
            // 15. Direct Regex Replacement
            else if (rule.replace) {
                lineHtml = this._applyTemplate(m, rule.replace);
                break;
            }
        }

        // Block context: a `sets_context` rule opens it, a `requires_context` rule keeps it,
        // anything else (or a blank line) closes it.
        if (lineHtml === null || usedRule === null) this._context = null;
        else if (usedRule.sets_context) this._context = usedRule.sets_context;
        else if (!usedRule.requires_context) this._context = null;

        if (lineHtml === null) {
            const escaped = escapeHtml(rawText);
            const defaultFg = this.theme.default_fg || '#c0c0c0';
            lineHtml = `<span style="color: ${defaultFg};">${escaped}</span>`;
        }

        const marker = this._markerColor(rawText);
        if (marker) lineHtml = this._applyMarker(lineHtml, marker[0], marker[1]);
        return normalizeLineToMudlet(promptHtml + lineHtml);
    }

    // ` (+12)` after a stat: only the signed number is colored; a zero delta stays default.
    // Tiered health: groups in `tier_groups` take the tier color of the % in `tier_source`.
    _renderHealthTier(rule, m) {
        const pct = parseInt(/-?\d+/.exec(m[rule.tier_source])[0], 10);
        const color = rule.tiers.find(t => pct >= t.min).color;
        const defaultFg = this.theme.default_fg || '#c0c0c0';
        let out = '';
        for (let i = 1; i < m.length; i++) {
            const text = m[i] || '';
            if (!text) continue;
            const c = rule.tier_groups.includes(i) ? color : defaultFg;
            out += `<span style="color: ${c};">${escapeHtml(text)}</span>`;
        }
        return out;
    }

    _promptDeltaHtml(ws, delta) {
        const color = delta.startsWith('-') ? "#ff0000" : (delta.startsWith('+') ? "#00ff00" : null);
        let number = escapeHtml(delta);
        if (color && delta.replace(/^[+-]+/, '').replace(/^0+|0+$/g, '').trim()) {
            number = `<span style="color: ${color};">${number}</span>`;
        }
        return `${escapeHtml(ws)}(` + number + ')';
    }

    _renderPromptExtended(m) {
        const [lead, pvs, pvsWs, pvsDelta, pe, peWs, peDelta, extra] = [1, 2, 3, 4, 5, 6, 7, 8].map(i => m[i] || '');
        let out = escapeHtml(lead);
        out += `<span style="color: #008000;">${escapeHtml(pvs)}</span>`;
        if (pvsDelta) out += this._promptDeltaHtml(pvsWs, pvsDelta);
        if (pe) out += `<span style="color: #008000;">${escapeHtml(pe)}</span>`;
        if (peDelta) out += this._promptDeltaHtml(peWs, peDelta);
        if (extra) out += `<span style="color: #008000;">${escapeHtml(extra)}</span>`;
        return out;
    }

    // `Pvs: 4381(4381)  Pe: 550(980)  Fe: 67(220) ...`: numbers colored by health, Fe white.
    _renderPromptVitals(m) {
        const [lead, label, cur, mid, mx, rest, fe, tail] = [1, 2, 3, 4, 5, 6, 7, 8].map(i => m[i] || '');
        const ratio = parseInt(mx, 10) ? parseInt(cur, 10) / parseInt(mx, 10) : 1;
        const color = ratio < 0.3 ? "#ff0000" : "#00ff00";
        return (
            `${escapeHtml(lead)}${escapeHtml(label)}` +
            `<span style="color: ${color};">${escapeHtml(cur)}</span>${escapeHtml(mid)}` +
            `<span style="color: ${color};">${escapeHtml(mx)}</span>${escapeHtml(rest)}` +
            `<span style="color: #ffffff;">${escapeHtml(fe)}</span>${escapeHtml(tail)}`
        );
    }

    getRaceColor(text) {
        if (!text) return "#ffff00";
        const m = this.raceTagRegex.exec(text);
        if (m) {
            const rawTag = m[0].slice(1, -1).toLowerCase();
            return this.raceColors[rawTag] || "#ffff00";
        }
        return "#ffff00";
    }

    _colorizePlayerEntities(text) {
        const regex = new RegExp(this.playerEntityPattern, 'gi');
        let parts = [];
        let lastEnd = 0;
        let match;
        while ((match = regex.exec(text)) !== null) {
            const start = match.index;
            const end = regex.lastIndex;
            if (start > lastEnd) {
                parts.push(escapeHtml(text.slice(lastEnd, start)));
            }
            const rawMatched = match[1];
            const token = rawMatched.trim();
            const leadingWs = rawMatched.slice(0, rawMatched.length - rawMatched.trimStart().length);
            const trailingWs = rawMatched.slice(rawMatched.trimEnd().length);
            const color = this.getRaceColor(token);
            parts.push(escapeHtml(leadingWs) + `<span style="color: ${color};">${escapeHtml(token)}</span>` + escapeHtml(trailingWs));
            lastEnd = end;
            if (regex.lastIndex === match.index) regex.lastIndex++;
        }
        if (lastEnd < text.length) {
            parts.push(escapeHtml(text.slice(lastEnd)));
        }
        return parts.join('');
    }

    _renderMovement(m) {
        const promptSym = m[1];
        const actor = m[2];
        const verb = m[3];
        const dest = m[4];
        const period = m[5];
        const promptHtml = promptSym ? '<span style="color: #c0c0c0;">&gt; </span>' : '';
        const tagM = this.raceTagRegex.exec(actor);
        const actorColor = tagM ? this.getRaceColor(actor) : "#c0c0c0";
        const actorHtml = tagM
            ? `<span style="color: ${actorColor}; font-weight: bold;">${escapeHtml(actor)}</span>`
            : `<span style="color: #c0c0c0;">${escapeHtml(actor)}</span>`;
        const verbHtml = `<span style="color: #ffffff;">${escapeHtml(verb)}</span>`;
        const destHtml = `<span style="color: #c0c0c0;">${escapeHtml(dest + period)}</span>`;
        return `${promptHtml}${actorHtml} ${verbHtml} ${destHtml}`;
    }

    // {color, n}: color for the first n characters of the title, or null when unknown.
    // Order: Mudlet map (exact name, then zone), then the room catalog (exact, then zone).
    // An exact match colors the whole title; a zone match colors only the zone
    // prefix, up to the ":" or the first "-" (the reference leaves the rest default).
    getRoomColor(roomTitle) {
        if (!roomTitle) return null;
        const cleanTitle = roomTitle.replace(/\s*-\s*/g, ' - ').replace(/\s*:\s*/g, ': ').replace(/\s+/g, ' ').trim().toLowerCase();
        const has = (t, k) => Object.prototype.hasOwnProperty.call(t, k);
        for (const [names, zones] of [[this.roomMapNames, this.roomMapZones], [this.roomColors, this.roomColors]]) {
            if (has(names, cleanTitle)) return { color: names[cleanTitle], n: roomTitle.length };
            if (cleanTitle.includes(':')) {
                const zone = cleanTitle.split(':')[0].trim();
                if (has(zones, zone)) return { color: zones[zone], n: roomTitle.indexOf(':') + 1 };
            }
            if (cleanTitle.includes(' - ')) {
                const zone = cleanTitle.split(' - ')[0].trim();
                if (has(zones, zone)) return { color: zones[zone], n: roomTitle.slice(0, roomTitle.indexOf('-')).trimEnd().length };
            }
        }
        return null;
    }

    _nearSilver(color) {
        const [r, g, b] = hexToRgb(color);
        return Math.sqrt((r - 192) ** 2 + (g - 192) ** 2 + (b - 192) ** 2) < SILVER_TITLE_DISTANCE;
    }

    // Bold title: known color on the matched prefix, fallback color when unknown.
    _roomTitleHtml(roomTitle) {
        const found = this.getRoomColor(roomTitle);
        if (!found) return `<span style="color: ${this.roomFallbackColor}; font-weight: bold;">${escapeHtml(roomTitle)}</span>`;
        const color = this._nearSilver(found.color) ? '#ffffff' : found.color;
        return `<span style="color: ${color}; font-weight: bold;">${escapeHtml(roomTitle.slice(0, found.n))}</span>${escapeHtml(roomTitle.slice(found.n))}`;
    }

    _renderRoomExits(m) {
        const roomTitle = m[2];
        const sep = m[3];
        const exits = m[4];
        const titleHtml = this._roomTitleHtml(roomTitle);
        return `${titleHtml}${escapeHtml(sep)}<span style="color: #00ffff;">${escapeHtml(exits)}</span>`;
    }

    _renderRoomTitle(m) {
        const roomTitle = m[2];
        if (!this.getRoomColor(roomTitle)) return null;
        return this._roomTitleHtml(roomTitle);
    }

    _renderTirada(m) {
        const b1 = m[1];
        const tag = m[2];
        const body = m[3];
        const result = m[4];
        const b2 = m[5];
        const resColor = (result.includes('Éxito') || result.includes('Exito')) ? "#00ff00" : "#ff0000";

        return (
            `<span style="color: #c0c0c0;">[</span>` +
            `<span style="color: #ffff00; font-weight: bold;">${escapeHtml(tag)}</span>` +
            `<span style="color: #c0c0c0;">${escapeHtml(body)}</span>` +
            `<span style="color: ${resColor}; font-weight: bold;">${escapeHtml(result)}</span>` +
            `<span style="color: #c0c0c0;">${escapeHtml(b2)}</span>`
        );
    }

    _renderInfo(m) {
        const b1 = m[1];
        const tag = m[2];
        const sep = m[3];
        const rest = m[4];
        const tagColors = {
            'INFO': '#ffff00',
            'AYUDA': '#ff00ff',
            'ADVERTENCIA': '#ffaa00',
            'ERROR': '#ff0000'
        };
        const tcolor = tagColors[tag] || '#ffff00';

        return (
            `<span style="color: #c0c0c0;">[</span>` +
            `<span style="color: ${tcolor}; font-weight: bold;">${escapeHtml(tag)}</span>` +
            `<span style="color: #c0c0c0;">${escapeHtml(sep)}${escapeHtml(rest)}</span>`
        );
    }

    _renderRoomPlayer(m) {
        const promptSym = m[1];
        const players = m[2];
        const sep = m[3];
        const verb = m[4];
        const promptHtml = promptSym ? '<span style="color: #c0c0c0;">&gt; </span>' : '';
        const coloredPlayers = this._colorizePlayerEntities(players);
        return `${promptHtml}${coloredPlayers}<span style="color: #c0c0c0;">${escapeHtml(sep)}${escapeHtml(verb)}.</span>`;
    }

    _renderRoomNpc(m) {
        const promptSym = m[1];
        const npc = m[2];
        const sep = m[3];
        const verb = m[4];
        const promptHtml = promptSym ? '<span style="color: #c0c0c0;">&gt; </span>' : '';
        return `${promptHtml}<span style="color: #c0c0c0;">${escapeHtml(npc)}${escapeHtml(sep)}${escapeHtml(verb)}.</span>`;
    }

    _renderFollowerPlayer(m) {
        const promptSym = m[1];
        const actor = m[2];
        const verb = m[3];
        const promptHtml = promptSym ? '<span style="color: #c0c0c0;">&gt; </span>' : '';
        const actorColor = this.getRaceColor(actor);
        return `${promptHtml}<span style="color: ${actorColor}; font-weight: bold;">${escapeHtml(actor)}</span> <span style="color: #c0c0c0;">${escapeHtml(verb)}.</span>`;
    }

    _renderSpellCompletion(m) {
        const line = m[0];
        const parts = [];
        let pos = 0;
        const qRegex = /'[^']+'/g;
        let qM;
        while ((qM = qRegex.exec(line)) !== null) {
            const start = qM.index;
            const end = qRegex.lastIndex;
            if (start > pos) {
                parts.push(`<span style="color: #c0c0c0;">${escapeHtml(line.slice(pos, start))}</span>`);
            }
            parts.push(`<span style="color: #00ffff;">${escapeHtml(qM[0])}</span>`);
            pos = end;
        }
        if (pos < line.length) {
            parts.push(`<span style="color: #c0c0c0;">${escapeHtml(line.slice(pos))}</span>`);
        }
        return parts.join('');
    }

    _renderEnemyManeuver(m) {
        const promptSym = m[1];
        const alertSym = m[2];
        const actor = m[3];
        const sep = m[4];
        const verb = m[5];
        const rest = m[6] || "";
        const promptHtml = promptSym ? '<span style="color: #c0c0c0;">&gt; </span>' : '';
        const alertHtml = alertSym ? `<span style="color: #ff0000; font-weight: bold;">${escapeHtml(alertSym)}</span>` : '';
        const tagM = this.raceTagRegex.exec(actor);
        const actorColor = tagM ? this.getRaceColor(actor) : "#ff4444";
        const actorHtml = `<span style="color: ${actorColor}; font-weight: bold;">${escapeHtml(actor)}</span>`;
        const actionHtml = `<span style="color: #ff8080;">${escapeHtml(verb + rest)}</span>`;
        return `${promptHtml}${alertHtml}${actorHtml}${escapeHtml(sep)}${actionHtml}`;
    }

    _renderPlayerCombat(m) {
        const promptSym = m[1];
        const hashPrefix = m[2];
        const hashBody = m[3];
        const starPrefix = m[4];
        const verb = m[5];
        const rest = m[6];

        const promptHtml = promptSym ? '<span style="color: #c0c0c0;">&gt; </span>' : '';

        let prefixSym = "";
        let body = "";
        if (hashPrefix) {
            prefixSym = hashPrefix;
            body = hashBody || "";
        } else {
            prefixSym = starPrefix || "";
            body = (verb || "") + (rest || "");
        }

        const fullLine = prefixSym + body;

        const lower = fullLine.toLowerCase();
        if (lower.includes('esquiva tu ataque') ||
            lower.includes('fallas tu ataque') ||
            lower.includes('bloquea tu') ||
            lower.includes('consigue parar') ||
            lower.includes('consigue esquivar')) {
            return `${promptHtml}<span style="color: #808080;">${escapeHtml(fullLine)}</span>`;
        }

        const parts = [];
        let pos = 0;
        const bracketRe = /(\()(\d+)(?:(-)(\d+))?(\))/g;
        let bM;
        while ((bM = bracketRe.exec(body)) !== null) {
            const start = bM.index;
            const end = bracketRe.lastIndex;
            if (start > pos) {
                parts.push(`<span style="color: #00ff00;">${escapeHtml(body.slice(pos, start))}</span>`);
            }
            const b1 = bM[1];
            const d1 = bM[2];
            const sep = bM[3];
            const d2 = bM[4];
            const b2 = bM[5];
            parts.push(`<span style="color: #ffff00;">${b1}</span><span style="color: #ff0000; font-weight: bold;">${d1}</span>`);
            if (sep) {
                parts.push(`<span style="color: #ffffff;">${sep}</span><span style="color: #ff0000; font-weight: bold;">${d2}</span>`);
            }
            parts.push(`<span style="color: #ffff00;">${b2}</span>`);
            pos = end;
        }
        if (pos < body.length) {
            parts.push(`<span style="color: #00ff00;">${escapeHtml(body.slice(pos))}</span>`);
        }

        const combatHtml = parts.join('');

        let prefixHtml = "";
        if (prefixSym) {
            if (prefixSym.includes('#')) {
                prefixHtml = '<span style="color: #008000;">#</span>' + escapeHtml(prefixSym.slice(1));
            } else if (prefixSym.includes('*')) {
                prefixHtml = '<span style="color: #008000;">*</span>' + escapeHtml(prefixSym.slice(1));
            }
        }

        return `${promptHtml}${prefixHtml}${combatHtml}`;
    }

    // Color of the leading `#` / `*` / `+` marker, or null when the line has no marker.
    _markerColor(text) {
        for (const rule of this.markerRules) {
            const m = rule._regex.exec(text);
            if (!m) continue;
            for (const cat of rule._categories) {
                if (cat._regex.test(m[2])) return [m[1], cat.color];
            }
            return [m[1], rule.color];
        }
        return null;
    }

    // Recolor the first visible character (the marker); the rest of the line is untouched.
    _applyMarker(lineHtml, ch, color) {
        const h = lineHtml.replace(/<span style="[^"]*"><\/span>/g, '');
        const mark = `<span style="color: ${color};">${ch}</span>`;
        const m = /^<span style="([^"]*)">/.exec(h);
        if (m && h.slice(m[0].length).startsWith(ch)) {
            return mark + `<span style="${m[1]}">` + h.slice(m[0].length + ch.length);
        }
        if (h.startsWith(ch)) return mark + h.slice(ch.length);
        return lineHtml;
    }

    _applyTemplate(m, template) {
        let res = template;
        for (let i = 1; i < m.length; i++) {
            const escapedVal = escapeHtml(m[i] || '');
            res = res.replaceAll(`$${i}`, escapedVal);
        }
        return res;
    }

    // ------------------------------------------------------------------
    // Preprocess layer: data-driven sanitization (mirrors engine.py)
    // ------------------------------------------------------------------
    _initPreprocess(cfg) {
        this.preClients = (cfg.clients || []).map(c => ({
            id: c.id,
            label: c.label || c.id,
            signatures: (c.signatures || []).map(p => toSharedRegex(p))
        }));
        this.preRules = (cfg.rules || []).map(r => {
            const comp = { ...r };
            for (const key of ['pattern', 'start', 'end', 'until', 'candidate', 'record', 'echo', 'keep_before']) {
                if (key in r) comp['_' + key] = toSharedRegex(r[key]);
            }
            return comp;
        });
    }

    clientLabel(clientId) {
        const c = this.preClients.find(x => x.id === clientId);
        return c ? c.label : null;
    }

    detectClient(textOrLines) {
        const lines = typeof textOrLines === 'string'
            ? textOrLines.replace(/\r\n/g, '\n').split('\n')
            : textOrLines;
        let bestId = null;
        let bestHits = 0;
        for (const c of this.preClients) {
            let hits = 0;
            for (const line of lines) {
                if (c.signatures.some(sig => sig.test(line))) hits++;
            }
            if (hits > bestHits) {
                bestId = c.id;
                bestHits = hits;
            }
        }
        return bestId;
    }

    _expandTemplate(template, m) {
        return template.replace(/\$(\d)/g, (_, d) => {
            const idx = parseInt(d, 10);
            const g = idx < m.length ? m[idx] : undefined;
            return g === undefined || g === null ? '' : g;
        });
    }

    _squeezeBlank(lines, rule) {
        // Drop blank lines, keeping one only where the source had blanks right before a
        // line matching `keep_before` (a new prompt/turn). Leading/trailing blanks go.
        const out = [];
        let pending = false;
        for (const line of lines) {
            if (/^[ 	]*$/.test(line)) {
                pending = true;
                continue;
            }
            if (pending && out.length > 0 && rule._keep_before.test(line)) out.push('');
            pending = false;
            out.push(line);
        }
        return out;
    }

    preprocessText(text, client = null) {
        const lines = (text || '').replace(/\r\n/g, '\n').split('\n');
        if (client === null || client === undefined) {
            client = this.detectClient(lines);
        }
        this.detectedClient = client;
        const rules = this.preRules.filter(r => !r.clients || !r.clients.length || r.clients.includes(client));
        if (rules.length === 0) {
            return lines.join('\n');
        }

        let out = [];
        let changed = false;
        const lastKeys = {};
        const secrets = new Set(); // tokens removed as login echoes in this input
        let lastLogin = null;      // input index of the last line handled by a login rule
        let run = null; // status-block run ending right before the current line: {group, kept}
        const n = lines.length;
        let i = 0;
        while (i < n) {
            let line = lines[i];
            let handled = false;
            for (const r of rules) {
                const kind = r.kind;
                if (kind === 'squeeze_blank') continue; // post-pass over the finished output
                if (kind === 'rewrite') {
                    const m = r._pattern.exec(line);
                    if (m) {
                        const newLine = this._expandTemplate(r.replace, m);
                        if (newLine !== line) {
                            line = newLine;
                            changed = true;
                        }
                    }
                    continue;
                }
                if (kind === 'drop_before') {
                    if (!r._pattern.test(line)) continue;
                    const found = [];
                    let k = out.length - 1;
                    if (lastLogin !== null && i - lastLogin <= 2) k = -1; // already handled by the login rule that just fired
                    const maxBack = (r.max_lines === undefined || r.max_lines === null) ? 3 : r.max_lines;
                    while (k >= 0 && found.length < maxBack) {
                        if (/^[ \t]*$/.test(out[k])) { k--; continue; }
                        if (!r._candidate.test(out[k])) break;
                        found.push(k);
                        k--;
                    }
                    if (found.length > 0) {
                        for (const idx of found) secrets.add(out[idx].replace(/[ \t]+$/, ''));
                        const gone = new Set(found);
                        out = out.filter((_, idx) => !gone.has(idx));
                        changed = true;
                    }
                    if (r.login) lastLogin = i;
                    continue;
                }
                if (kind === 'drop_secret') {
                    const win = (r.window === undefined || r.window === null) ? 6 : r.window;
                    if (!(lastLogin !== null && i - lastLogin <= win && secrets.has(line.replace(/[ \t]+$/, '')))) continue;
                    i += 1;
                    changed = true;
                    run = null;
                    handled = true;
                    break;
                }
                if (kind === 'drop_block') {
                    if (!r._start.test(line)) continue;
                    const limit = (r.max_lines === undefined || r.max_lines === null)
                        ? n - 1 : Math.min(n - 1, i + r.max_lines);
                    let endIdx = null;
                    for (let j = i + 1; j <= limit; j++) {
                        if (r._end.test(lines[j])) { endIdx = j; break; }
                    }
                    if (endIdx === null) continue;
                    i = r.include_end ? endIdx + 1 : endIdx;
                } else if (kind === 'drop_after') {
                    if (!r._pattern.test(line)) continue;
                    const maxLines = (r.max_lines === undefined || r.max_lines === null) ? 8 : r.max_lines;
                    const limit = Math.min(n, i + 1 + maxLines);
                    let j = i + 1;
                    while (j < limit && !r._until.test(lines[j])) {
                        // Stop at the first real server line so fragments keep their content.
                        if (r._echo && lines[j].trim() && !r._echo.test(lines[j])) break;
                        j++;
                    }
                    if (r._record) {
                        for (let k = i + 1; k < j; k++) {
                            if (r._record.test(lines[k])) secrets.add(lines[k].replace(/[ \t]+$/, ''));
                        }
                    }
                    if (j < limit && r.include_until && r._until.test(lines[j])) j++;
                    i = j;
                } else if (kind === 'drop_closer') {
                    if (!(run !== null && run.group === r.group && run.kept === 0 && r._pattern.test(line))) continue;
                    i += 1;
                } else {
                    const m = r._pattern.exec(line);
                    if (!m) continue;
                    let keep;
                    if (kind === 'drop') {
                        keep = false;
                        if (r.login) lastLogin = i;
                    } else if (kind === 'dedupe_on_change') {
                        let key;
                        if ('key' in r) key = this._expandTemplate(r.key, m);
                        else if ('key_group' in r) key = m[r.key_group] || '';
                        else key = line;
                        key = key.replace(/[ \t]+$/, '');
                        const scope = ('scope_id' in r) ? r.scope_id : r.id;
                        keep = lastKeys[scope] !== key;
                        lastKeys[scope] = key;
                    } else {
                        continue;
                    }
                    const group = r.group;
                    if (group) {
                        if (run === null || run.group !== group) run = { group, kept: 0 };
                        if (keep) run.kept += 1;
                    } else {
                        run = null;
                    }
                    if (keep) out.push(line);
                    else changed = true;
                    i += 1;
                    handled = true;
                    break;
                }
                // drop_block / drop_after / drop_closer: lines consumed
                if (r.login) lastLogin = i - 1;
                changed = true;
                run = null;
                handled = true;
                break;
            }
            if (handled) continue;
            out.push(line);
            run = null;
            i += 1;
        }

        for (const r of rules) {
            if (r.kind === 'squeeze_blank') {
                out = this._squeezeBlank(out, r);
                changed = true;
            }
        }
        let result = out;
        if (changed) {
            result = [];
            for (const line of out) {
                if (/^[ \t]*$/.test(line) && (result.length === 0 || /^[ \t]*$/.test(result[result.length - 1]))) continue;
                result.push(line);
            }
        }
        return result.join('\n');
    }

    colorizeText(plainText, preprocess = true, client = null) {
        if (preprocess) {
            plainText = this.preprocessText(plainText, client);
        }
        const trimmed = (plainText || '').replace(/\r\n/g, '\n').replace(/\n+$/, '');
        const normalized = trimmed.replace(/\n{3,}/g, '\n\n');
        if (!normalized) {
            return MUDLET_HEADER + ' </div></body>\n</html>';
        }

        const lines = normalized.split('\n');
        this._context = null;
        const renderedLines = lines.map(line => this.colorizeLine(line));
        // Same as Mudlet's copy-as-HTML (TBuffer::bufferToHtml): every line ends in "<br>\n".
        const bodyContent = renderedLines.map(r => r + '<br>\n').join('');

        return `${MUDLET_HEADER}${bodyContent} </div></body>\n</html>`;
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { RLColorizerJS, escapeHtml };
}
