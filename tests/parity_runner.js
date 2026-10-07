// Helper for tests/test_parity.py: colorizes the given files with the JavaScript engine.
// Usage: node tests/parity_runner.js [--keep-private] <rules.json> <file> [<file> ...]
// Private messages (tells, telepathy) are removed unless --keep-private is given.
// Prints a JSON object { "<file>": { client, preprocessed, html, removed } }, where `removed` is
// the number of private lines the engine reports having removed.
const fs = require('fs');
const path = require('path');
const { RLColorizerJS } = require(path.join(__dirname, '..', 'webapp', 'engine.js'));

function decodeLogBytes(buf) {
    if (buf.length >= 3 && buf[0] === 0xef && buf[1] === 0xbb && buf[2] === 0xbf) {
        buf = buf.subarray(3);
    }
    try {
        return new TextDecoder('utf-8', { fatal: true }).decode(buf);
    } catch (e) {
        return new TextDecoder('windows-1252').decode(buf);
    }
}

const args = process.argv.slice(2);
const keepPrivate = args[0] === '--keep-private';
if (keepPrivate) args.shift();
const [rulesPath, ...files] = args;
const hidePrivate = !keepPrivate;
const rules = JSON.parse(fs.readFileSync(rulesPath, 'utf8'));
const colorizer = new RLColorizerJS(rules);
const result = {};
for (const file of files) {
    const text = decodeLogBytes(fs.readFileSync(file));
    const preprocessed = colorizer.preprocessText(text, null, hidePrivate);
    const client = colorizer.detectedClient;
    const html = colorizer.colorizeText(text, true, null, hidePrivate);
    result[file] = { client, preprocessed, html, removed: colorizer.privateRemoved };
}
process.stdout.write(JSON.stringify(result));
