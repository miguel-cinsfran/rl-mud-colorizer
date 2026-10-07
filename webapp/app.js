/**
 * Application Controller for Reinos de Leyenda MUD Log Colorizer
 */

document.addEventListener('DOMContentLoaded', () => {
    // Check rules
    if (!window.COLORIZER_RULES) {
        console.error("Rules not loaded. Make sure rules.js is included.");
        showToast("Error: No se pudieron cargar las reglas de color.", true);
        return;
    }

    const colorizer = new RLColorizerJS(window.COLORIZER_RULES);

    // DOM Elements
    const inputTextarea = document.getElementById('input-text');
    const previewContainer = document.getElementById('preview-container');
    const rawHtmlTextarea = document.getElementById('raw-html-text');
    
    const btnColorize = document.getElementById('btn-colorize');
    const btnCopy = document.getElementById('btn-copy');
    const btnDownload = document.getElementById('btn-download');
    const btnExample = document.getElementById('btn-example');
    const btnClear = document.getElementById('btn-clear');
    const fileInput = document.getElementById('file-input');
    const btnUpload = document.getElementById('btn-upload');

    const tabPreview = document.getElementById('tab-preview');
    const tabHtml = document.getElementById('tab-html');

    // Stats Elements
    const statInputLines = document.getElementById('stat-input-lines');
    const statInputChars = document.getElementById('stat-input-chars');
    const statOutputLines = document.getElementById('stat-output-lines');
    const statOutputTags = document.getElementById('stat-output-tags');

    const statClient = document.getElementById('stat-client');

    const toast = document.getElementById('toast');
    const inputPanel = document.getElementById('input-panel');

    let currentHtmlOutput = '';
    let lastAnnouncedClient = null;
    let suppressClientAnnounce = false;

    // Decode a file's bytes: strict UTF-8 first (Mudlet), Windows-1252 fallback (VIPMud).
    function decodeLogBuffer(buffer) {
        let bytes = new Uint8Array(buffer);
        if (bytes.length >= 3 && bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf) {
            bytes = bytes.subarray(3);
        }
        try {
            return { text: new TextDecoder('utf-8', { fatal: true }).decode(bytes), encoding: 'UTF-8' };
        } catch (e) {
            return { text: new TextDecoder('windows-1252').decode(bytes), encoding: 'Windows-1252' };
        }
    }

    function clientLabelText(clientId) {
        return (clientId && colorizer.clientLabel(clientId)) || null;
    }

    function readLogFile(file) {
        const reader = new FileReader();
        reader.onload = (evt) => {
            const { text, encoding } = decodeLogBuffer(evt.target.result);
            inputTextarea.value = text;
            suppressClientAnnounce = true; // the file announcement below already reports the client
            processLog();
            suppressClientAnnounce = false;
            const label = clientLabelText(colorizer.detectedClient);
            lastAnnouncedClient = colorizer.detectedClient;
            announce(
                `Archivo "${file.name}" cargado con éxito (codificación ${encoding}). ` +
                (label ? `Cliente detectado: ${label}.` : 'Cliente no reconocido, se aplican solo las reglas generales.')
            );
        };
        reader.onerror = () => announce(`No se pudo leer el archivo "${file.name}".`, true);
        reader.readAsArrayBuffer(file);
    }

    // Sample RL Demo Log
    const SAMPLE_LOG = `> ojear
Árbol: Entre las ramas
Sowy (Melf) está aquí.
Zeh (Mdro) está aquí.
Cuerpo de Jabali.

> formular vigor natural
Reúnes las fuerzas del animal de tu interior para formular el hechizo 'Vigor natural'.
Pronuncias el cántico: 'natura vigoris fortis'
Terminas tu hechizo 'Vigor natural' y te sientes lleno de una energía inagotable.

Pvs: 3200/3200 Pe: 450/450
Gurlen se va --> S <--.

! Sowy se prepara para ejecutar tajar sobre ti.
> ! Sowy se prepara para ejecutar golpecertero sobre ti.

* ¡Descubres a Gurlen intentando apuñalarte! Consigues esquivar la maniobra por los pelos.
* Gurlen te intenta perforar en una pierna, pero logras esquivar su ataque.

> # Perforas con increíble potencia a Sowy.
# Sowy consigue esquivar tu ataque.
# ¡Descargas una furia de golpes contra Zeh, pero éste consigue protegerse mágicamente de tres!
# Enfermas con poca intensidad a Zeh.

[Obtienes 205 puntos de experiencia]
Pvs: 3050/3200 (-150) Pe: 410/450 (-40)

# ¡El cielo ruge cuando invocas un relámpago que cae sobre Zeh!
# 10 misiles mágicos surgen de tus dedos e impactan infaliblemente sobre Sowy.

[Obtienes el logro 'La resistencia es futil' (pk)]
[Obtienes 18500 puntos de experiencia]
[Obtienes 35 puntos de gloria]
[Grorgh orbita al Limbo]
Propinas el golpe mortal a Sowy.
`;

    // Process & Colorize Log
    function processLog() {
        const text = inputTextarea.value;
        updateInputStats(text);

        if (!text.trim()) {
            previewContainer.innerHTML = '<span class="preview-empty">El log colorizado se mostrará aquí.</span>';
            rawHtmlTextarea.value = '';
            currentHtmlOutput = '';
            updateOutputStats(0, 0);
            statClient.textContent = 'ninguno';
            return;
        }

        const htmlResult = colorizer.colorizeText(text);
        currentHtmlOutput = htmlResult;

        // Client detection (VIPMud / Mudlet): show it, and announce it when it changes
        const clientId = colorizer.detectedClient;
        const clientLabel = clientLabelText(clientId);
        statClient.textContent = clientLabel || 'No reconocido';
        if (clientId !== lastAnnouncedClient) {
            lastAnnouncedClient = clientId;
            if (clientLabel && !suppressClientAnnounce) {
                announce(`Cliente detectado: ${clientLabel}.`);
            }
        }

        // Extract inner terminal content for the visual preview container to avoid global body style bleed
        const startTag = '<body><div>';
        const endTag = '</div></body>';
        const startIdx = htmlResult.indexOf(startTag);
        const endIdx = htmlResult.lastIndexOf(endTag);
        // The output ends each line in "<br>\n" like Mudlet; the preview uses pre-wrap, where that
        // newline would add a blank line, so it is dropped here (preview only, not the copied HTML).
        const previewHtml = ((startIdx !== -1 && endIdx !== -1)
            ? htmlResult.slice(startIdx + startTag.length, endIdx)
            : htmlResult).replace(/<br\s*\/?>\n/g, '<br>');

        previewContainer.innerHTML = previewHtml;
        rawHtmlTextarea.value = htmlResult;

        // Count output stats
        const lineCount = (htmlResult.match(/<span/g) || []).length;
        const totalTags = (htmlResult.match(/<\/span>/g) || []).length;
        updateOutputStats(lineCount, totalTags);
    }

    function updateInputStats(text) {
        if (!text) {
            statInputLines.textContent = '0';
            statInputChars.textContent = '0';
            return;
        }
        const lines = text.split(/\r?\n/).length;
        const chars = text.length;
        statInputLines.textContent = lines.toLocaleString();
        statInputChars.textContent = chars.toLocaleString();
    }

    function updateOutputStats(styledLines, tagsCount) {
        statOutputLines.textContent = styledLines.toLocaleString();
        statOutputTags.textContent = tagsCount.toLocaleString();
    }

    const statusAnnouncer = document.getElementById('status-announcer');

    function announce(message, isError = false) {
        if (statusAnnouncer) {
            statusAnnouncer.textContent = '';
            setTimeout(() => {
                statusAnnouncer.textContent = message;
            }, 50);
        }
        showToast(message, isError);
    }

    function showToast(message, isError = false) {
        toast.textContent = message;
        toast.classList.toggle('error', isError);
        toast.classList.add('show');
        setTimeout(() => {
            toast.classList.remove('show');
        }, 3200);
    }

    // Copy to Clipboard
    async function copyToClipboard() {
        if (!currentHtmlOutput) {
            announce("Primero ingresa y coloriza un log.", true);
            return;
        }

        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(currentHtmlOutput);
            } else {
                // Fallback for older browsers
                rawHtmlTextarea.style.display = 'block';
                rawHtmlTextarea.select();
                document.execCommand('copy');
                if (tabPreview.classList.contains('active')) {
                    rawHtmlTextarea.style.display = 'none';
                }
            }
            announce("¡HTML de Mudlet copiado al portapapeles! Listo para pegar en el formulario de Deathlogs.");
        } catch (err) {
            console.error("Clipboard error:", err);
            announce("Error al copiar al portapapeles.", true);
        }
    }

    // Download HTML File
    function downloadHtmlFile() {
        if (!currentHtmlOutput) {
            announce("Primero ingresa y coloriza un log.", true);
            return;
        }

        const blob = new Blob([currentHtmlOutput], { type: 'text/html;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        const timestamp = new Date().toISOString().slice(0, 10);
        a.href = url;
        a.download = `rl_deathlog_${timestamp}.html`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        announce("Archivo HTML de Mudlet descargado con éxito.");
    }

    // Switch between the preview and the raw HTML (plain toggle buttons, state in aria-pressed)
    function selectTab(targetTab) {
        const showPreview = targetTab === 'preview';
        tabPreview.classList.toggle('active', showPreview);
        tabPreview.setAttribute('aria-pressed', String(showPreview));
        tabHtml.classList.toggle('active', !showPreview);
        tabHtml.setAttribute('aria-pressed', String(!showPreview));
        previewContainer.style.display = showPreview ? 'block' : 'none';
        rawHtmlTextarea.style.display = showPreview ? 'none' : 'block';
        announce(showPreview ? "Vista previa seleccionada." : "Vista de código HTML seleccionada.");
    }

    tabPreview.addEventListener('click', () => selectTab('preview'));
    tabHtml.addEventListener('click', () => selectTab('html'));

    // Event Listeners
    btnColorize.addEventListener('click', () => {
        processLog();
        const lines = (currentHtmlOutput.match(/<span/g) || []).length;
        announce(`Log colorizado con éxito. ${lines} líneas preparadas para Deathlogs.`);
    });

    btnCopy.addEventListener('click', copyToClipboard);

    btnDownload.addEventListener('click', downloadHtmlFile);

    btnExample.addEventListener('click', () => {
        inputTextarea.value = SAMPLE_LOG;
        processLog();
        announce("Log de ejemplo cargado y colorizado con éxito.");
    });

    btnClear.addEventListener('click', () => {
        inputTextarea.value = '';
        processLog();
        announce("Editor limpiado.");
        inputTextarea.focus();
    });

    // Keyboard shortcut: Ctrl + Enter to colorize
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            processLog();
        }
    });

    // Real-time stats & debounce colorize for smooth UX
    let debounceTimer;
    inputTextarea.addEventListener('input', () => {
        updateInputStats(inputTextarea.value);
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            processLog();
        }, 300);
    });

    // File Upload Handler
    btnUpload.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) return;

        readLogFile(file);
    });

    // Drag and Drop support
    ['dragenter', 'dragover'].forEach(name => {
        inputPanel.addEventListener(name, (e) => {
            e.preventDefault();
            e.stopPropagation();
            inputPanel.classList.add('drag-over');
        });
    });

    ['dragleave', 'drop'].forEach(name => {
        inputPanel.addEventListener(name, (e) => {
            e.preventDefault();
            e.stopPropagation();
            inputPanel.classList.remove('drag-over');
        });
    });

    inputPanel.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const file = dt.files[0];
        if (file) {
            readLogFile(file);
        }
    });

    // Initial load: show sample
    inputTextarea.value = SAMPLE_LOG;
    processLog();
});
