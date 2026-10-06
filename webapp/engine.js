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
const DEFAULT_MUDLET_STYLE = "color: rgb(192,192,192); background: rgb(0,0,0); ";

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
        
        this.racesStr = "Hlag|Lag|Melf|Elf|S-e|Gob|Gno|Hum|Orc|S-o|Ena|Mdro|Drow|S-d|Hal|Hlf|Duer|Drg|Min|Mino|Gnl|Gnol|Kob|Org|Orgo|Drax|Ctd|Cent|Kuo|Ggt|S-g";
        this.raceTagRegex = new RegExp(`\\((?:${this.racesStr})\\)`, 'i');
        this.playerEntityPattern = `((?:\\b(?:un|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\\s+)?[*|\\-~/]*\\s*[A-Za-zÁÉÍÓÚáéíóúñÑ0-9\\x27_-]+(?:\\s+[|*\\-~/]+)?\\s*\\((?:${this.racesStr})\\)(?:es)?(?:\\s*[|*\\-~/]+)?)`;
        this.cardinalRegex = /\b(norte|sur|este|oeste|noreste|noroeste|sudeste|sudoeste|arriba|abajo|n|s|e|o|ne|no|se|so)\b/i;
        
        this.detectedClient = null;
        this._initPreprocess(this.config.preprocess || {});

        const sortedRules = [...this.config.rules].sort((a, b) => (a.priority || 100) - (b.priority || 100));
        this.compiledRules = sortedRules.map(r => ({
            ...r,
            _regex: toSharedRegex(r.pattern)
        }));
    }

    colorizeLine(line) {
        let rawText = line.replace(/\r?\n$/, '');
        rawText = rawText.replace(/&gt;/g, '>').replace(/&lt;/g, '<').replace(/&amp;/g, '&');

        if (!rawText.trim()) {
            return "";
        }

        let lineHtml = null;
        for (const rule of this.compiledRules) {
            const m = rule._regex.exec(rawText);
            if (!m) continue;

            const type = rule.type;

            // 1. Composite Prompt Handler
            if (type === 'composite_prompt_extended') {
                lineHtml = this._renderPromptExtended(m);
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
            // 12. Composite Follower Player
            else if (type === 'composite_follower_player') {
                lineHtml = this._renderFollowerPlayer(m);
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

        if (lineHtml === null) {
            const escaped = escapeHtml(rawText);
            const defaultFg = this.theme.default_fg || '#c0c0c0';
            lineHtml = `<span style="color: ${defaultFg};">${escaped}</span>`;
        }

        return normalizeLineToMudlet(lineHtml);
    }

    _renderPromptExtended(m) {
        const pvs = m[1];
        const pvsDelta = m[2];
        const pe = m[3];
        const peDelta = m[4];
        const extra = m[5];

        let out = '';
        if (pvs) {
            out += `<span style="color: #008000; font-weight: bold;">${escapeHtml(pvs)}</span>`;
        }

        if (pvsDelta) {
            const color = pvsDelta.startsWith('-') ? "#ff0000" : (pvsDelta.startsWith('+') ? "#00ff00" : "#008000");
            const prefixSpace = (pvs && !pvs.endsWith(' ')) ? ' ' : '';
            out += `${prefixSpace}<span style="color: #008000;">(</span><span style="color: ${color}; font-weight: bold;">${escapeHtml(pvsDelta)}</span><span style="color: #008000;">)</span>`;
        }

        if (pe) {
            out += `<span style="color: #008000;">${escapeHtml(pe)}</span>`;
        }

        if (peDelta) {
            const color = peDelta.startsWith('-') ? "#ff0000" : (peDelta.startsWith('+') ? "#00ff00" : "#008000");
            const prefixSpace = (pe && !pe.endsWith(' ')) ? ' ' : '';
            out += `${prefixSpace}<span style="color: #008000;">(</span><span style="color: ${color}; font-weight: bold;">${escapeHtml(peDelta)}</span><span style="color: #008000;">)</span>`;
        }

        if (extra) {
            out += `<span style="color: #008000;">${escapeHtml(extra)}</span>`;
        }

        return out;
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
        const promptHtml = promptSym ? '<span style="color: #c0c0c0;">&gt; </span>' : '';
        const tagM = this.raceTagRegex.exec(actor);
        const actorColor = tagM ? this.getRaceColor(actor) : "#c0c0c0";
        const actorHtml = tagM
            ? `<span style="color: ${actorColor}; font-weight: bold;">${escapeHtml(actor)}</span>`
            : `<span style="color: #c0c0c0;">${escapeHtml(actor)}</span>`;
        const verbHtml = `<span style="color: #ffffff;">${escapeHtml(verb)}</span>`;
        const destHtml = `<span style="color: #c0c0c0;">${escapeHtml(dest)}.</span>`;
        return `${promptHtml}${actorHtml} ${verbHtml} ${destHtml}`;
    }

    _renderFollowerPlayer(m) {
        const promptSym = m[1];
        const actor = m[2];
        const verb = m[3];
        const promptHtml = promptSym ? '<span style="color: #c0c0c0;">&gt; </span>' : '';
        const actorColor = this.getRaceColor(actor);
        return `${promptHtml}<span style="color: ${actorColor}; font-weight: bold;">${escapeHtml(actor)}</span> <span style="color: #c0c0c0;">${escapeHtml(verb)}.</span>`;
    }

    getRoomColor(roomTitle, fallback = null) {
        if (!roomTitle) return fallback || "#008000";
        let cleanTitle = roomTitle.replace(/\s*-\s*/g, ' - ').replace(/\s*:\s*/g, ': ').replace(/\s+/g, ' ').trim().toLowerCase();
        if (this.roomColors[cleanTitle]) {
            return this.roomColors[cleanTitle];
        }
        if (cleanTitle.includes(':')) {
            const zone = cleanTitle.split(':')[0].trim();
            if (this.roomColors[zone]) return this.roomColors[zone];
        }
        if (cleanTitle.includes(' - ')) {
            const zone = cleanTitle.split(' - ')[0].trim();
            if (this.roomColors[zone]) return this.roomColors[zone];
        }
        return fallback;
    }

    _renderRoomExits(m) {
        const promptSym = m[1];
        const roomTitle = m[2];
        const exits = m[3];
        const promptHtml = promptSym ? '<span style="color: #c0c0c0;">&gt; </span>' : '';
        const color = this.getRoomColor(roomTitle, "#008000");
        return `${promptHtml}<span style="color: ${color}; font-weight: bold;">${escapeHtml(roomTitle)}</span> <span style="color: #00ffff;">${escapeHtml(exits)}</span>`;
    }

    _renderRoomTitle(m) {
        const promptSym = m[1];
        const roomTitle = m[2];
        const color = this.getRoomColor(roomTitle, null);
        if (!color) return null;
        const promptHtml = promptSym ? '<span style="color: #c0c0c0;">&gt; </span>' : '';
        return `${promptHtml}<span style="color: ${color}; font-weight: bold;">${escapeHtml(roomTitle)}</span>`;
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
        const verb = m[4];
        const rest = m[5] || "";
        const promptHtml = promptSym ? '<span style="color: #c0c0c0;">&gt; </span>' : '';
        const alertHtml = alertSym ? '<span style="color: #ff0000; font-weight: bold;">!</span> ' : '';
        const tagM = this.raceTagRegex.exec(actor);
        const actorColor = tagM ? this.getRaceColor(actor) : "#ff4444";
        const actorHtml = `<span style="color: ${actorColor}; font-weight: bold;">${escapeHtml(actor)}</span>`;
        const actionHtml = `<span style="color: #ff8080;">${escapeHtml(verb + rest)}</span>`;
        return `${promptHtml}${alertHtml}${actorHtml} ${actionHtml}`;
    }

    _renderRoomPlayer(m) {
        const promptSym = m[1];
        const players = m[2];
        const verb = m[3];
        const promptHtml = promptSym ? '<span style="color: #c0c0c0;">&gt; </span>' : '';
        const coloredPlayers = this._colorizePlayerEntities(players);
        return `${promptHtml}${coloredPlayers}<span style="color: #c0c0c0;"> ${escapeHtml(verb)}.</span>`;
    }

    _renderRoomNpc(m) {
        const promptSym = m[1];
        const npc = m[2];
        const verb = m[3];
        const promptHtml = promptSym ? '<span style="color: #c0c0c0;">&gt; </span>' : '';
        return `${promptHtml}<span style="color: #c0c0c0;">${escapeHtml(npc)} ${escapeHtml(verb)}.</span>`;
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
                prefixHtml = '<span style="color: #008000;">#</span> ';
            } else if (prefixSym.includes('*')) {
                prefixHtml = '<span style="color: #008000;">*</span> ';
            }
        }

        return `${promptHtml}${prefixHtml}${combatHtml}`;
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
            for (const key of ['pattern', 'start', 'end', 'until', 'candidate', 'record']) {
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
                    while (j < limit && !r._until.test(lines[j])) j++;
                    if (r._record) {
                        for (let k = i + 1; k < j; k++) {
                            if (r._record.test(lines[k])) secrets.add(lines[k].replace(/[ \t]+$/, ''));
                        }
                    }
                    if (j < limit && r.include_until) j++;
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
        const renderedLines = lines.map(line => this.colorizeLine(line));
        const bodyContent = renderedLines.map(r => r + '<br>').join('\n');

        return `${MUDLET_HEADER}${bodyContent}\n </div></body>\n</html>`;
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { RLColorizerJS, escapeHtml };
}
