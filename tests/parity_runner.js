// Helper for tests/test_parity.py: colorizes the given files with the JavaScript engine.
// Usage: node tests/parity_runner.js <rules.json> <file> [<file> ...]
// Prints a JSON object { "<file>": { client, preprocessed, html } }.
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

const [rulesPath, ...files] = process.argv.slice(2);
const rules = JSON.parse(fs.readFileSync(rulesPath, 'utf8'));
const colorizer = new RLColorizerJS(rules);
const result = {};
for (const file of files) {
    const text = decodeLogBytes(fs.readFileSync(file));
    const preprocessed = colorizer.preprocessText(text);
    const client = colorizer.detectedClient;
    result[file] = { client, preprocessed, html: colorizer.colorizeText(text) };
}
process.stdout.write(JSON.stringify(result));
