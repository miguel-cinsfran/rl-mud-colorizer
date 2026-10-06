# Reinos de Leyenda (RL) - MUD Log Colorizer

Colorizador de logs de combate y rol para **[Reinos de Leyenda (RL)](https://reinosdeleyenda.com/)**, diseñado específicamente para que jugadores que juegan en **modo accesibilidad (sin colores / lectores de pantalla)** puedan convertir sus logs en bruto a formato HTML con la paleta de colores visual oficial del cliente Mudlet para subirlos directamente a **[Deathlogs](https://deathlogs.com/)**.

---

## 🌐 Probar en vivo (GitHub Pages)

👉 **[Abrir RL Log Colorizer en vivo](https://miguel-cinsfran.github.io/rl-mud-colorizer/)**

---

## ✨ Características Principales

* **Formato 1:1 Nativo para Deathlogs:**
  * Genera el bloque HTML estándar de Mudlet (`<font color="#cccccc" size="2"><div>...<br /></div></font>`).
  * Sin saltos de línea `\n` redundantes para evitar el problema de doble interlineado dentro del `<PRE>` de Deathlogs.
  * Botón de copiado directo con un solo clic listo para pegar en el formulario de envío.
* **100% Paridad entre Python y JavaScript:**
  * Motor dual: [`engine.py`](engine.py) y [`webapp/engine.js`](webapp/engine.js) ejecutan exactamente la misma lógica y producen resultados carácter a carácter idénticos.
* **Soporte de logs de VIPMud (y Mudlet):**
  * Detecta el cliente automáticamente y limpia lo que no es salida del juego: el inicio de sesión (banner, **usuario y clave**, MOTD) se elimina siempre y el bloque de estado repetido (`Pv:`, `SL:`, `PL:`, `Jgd:`, `Imágenes:`, `Pieles:` y el `> ` de cierre) se reduce a los valores que cambian.
  * Los archivos subidos o arrastrados a la web se leen como UTF-8 y, si no lo son, como Windows-1252 (VIPMud).
* **Colores Oficiales por Raza de Jugador:**
  * Identificación precisa de jugadores mediante sufijos de raza (`(Elf)`, `(Melf)`, `(Orc)`, `(Mdro)`, `(Gob)`, etc.).
  * No colorea NPCs genéricos como si fueran jugadores.
* **Catálogo de Habitaciones (Rooms):**
  * Más de 280 habitaciones catalogadas con su color exacto minado a partir de logs reales de jugadores videntes (zonas urbanas en plata, bosques en verde, templos en blanco, caminos de agua en cian, mesetas en oliva, etc.).
  * Habitaciones no catalogadas usan el verde por defecto (`#008000`).
* **Soporte Completo de Combate y Magia:**
  * Ataques propios en verde brillante (`#00ff00`) con números de daño resaltados.
  * Maniobras y preparación de enemigos en fucsia/rojo.
  * Esquivas, paradas y bloqueos en gris tenue (`#808080`).
  * Cánticos y finalización de hechizos en cian (`#00ffff`).

---

## 🎨 Leyenda Oficial de Razas

| Raza / Etiqueta | Color | Código Hex |
| :--- | :--- | :--- |
| **Elfo / Semi-Elfo** (`Elf`, `Melf`, `S-e`) | Verde | `#008000` |
| **Enano** (`Ena`, `Enano`) | Oliva | `#808000` |
| **Kobold** (`Kob`) | Granate / Rojo oscuro | `#800000` |
| **Drow / Semi-Drow** (`Mdro`, `Drow`, `S-d`) | Gris | `#808080` |
| **Duergar** (`Duer`, `Drg`) | Púrpura | `#800080` |
| **Goblin** (`Gob`) | Verde lima | `#00ff00` |
| **Gnomo** (`Gno`) | Cian | `#00ffff` |
| **Humano** (`Hum`) | Amarillo | `#ffff00` |
| **Gnoll** (`Gnl`, `Gnol`) | Rojo brillante | `#ff0000` |
| **Halfling** (`Hal`, `Hlf`) | Magenta | `#ff00ff` |
| **Lagarto / Hombre-Lagarto** (`Lag`, `Hlag`) | Azul | `#0000ff` |
| **Minotauro** (`Min`, `Mino`) | Plata | `#c0c0c0` |
| **Orco / Semi-Orco** (`Orc`, `S-o`) | Blanco | `#ffffff` |
| **Ogro-Mago / Ogro** (`Org`, `Orgo`) | Cian oscuro / Teal | `#008080` |

---

## 🚀 Uso Rápido

### Opción 1: Aplicación Web (Navegador)
1. Entra a la web en **[GitHub Pages](https://miguel-cinsfran.github.io/rl-mud-colorizer/)**.
2. Pega tu log en el panel izquierdo (o arrastra un archivo `.txt`).
3. Haz clic en **Copiar para Deathlogs**.
4. Pega el contenido directamente en el formulario de subida de [Deathlogs.com](https://deathlogs.com/).

### Opción 2: Línea de comandos (Python)

```bash
# Colorizar un log (UTF-8 o Windows-1252) y guardar el HTML
python engine.py tu_log.txt -o log_colorizado.html

# Sin -o escribe el HTML por la salida estándar.
# --client fuerza el cliente (vipmud, mudlet); --no-preprocess omite la limpieza
python engine.py tu_log.txt --client vipmud -o log_colorizado.html
```

---

## 🧹 Preprocesado (VIPMud / Mudlet)

Antes de colorizar, el texto pasa por una capa **guiada por datos**: la sección `preprocess` de [`build_rules.py`](build_rules.py), compilada a `rules.json` y `webapp/rules.js`, de modo que Python y JavaScript comparten exactamente las mismas reglas.

* **Detección de cliente:** gana el cliente cuyas firmas (`signatures`) coinciden con más líneas; si ninguna coincide solo se aplican las reglas sin `clients`.
  * `vipmud`: el prompt `Pv:N\N Pe:N\N Xp:N` (con barra invertida), `Jgd:` y `LPmud version:`.
  * `mudlet`: el prompt `Pv: N Pe: N` / `Pvs: N Pe: N` (sin barras).
  * `SL:`, `PL:`, `Pieles:` e `Imágenes:` también aparecen en logs de Mudlet con prompt personalizado, por eso **no** disparan la detección (los logs de Mudlet se conservan intactos).
* **Tipos de regla** (se evalúan en orden; todos aceptan un `clients: [...]` opcional):

| `kind` | Campos | Qué hace |
| :--- | :--- | :--- |
| `drop` | `pattern` | Elimina la línea. |
| `drop_block` | `start`, `end`, `include_end`, `max_lines` | Elimina desde `start` hasta `end`; solo actúa si encuentra `end` (un fragmento cortado nunca se traga). |
| `drop_after` | `pattern`, `until`, `include_until`, `max_lines` | Elimina la línea y las siguientes hasta una línea del servidor (`until`): lo escrito tras un prompt (usuario/clave). |
| `dedupe_on_change` | `pattern`, `scope_id`, `key_group` o `key` | Conserva la línea solo si su clave cambia respecto a la última conservada del mismo `scope_id` (por defecto, la línea entera). |
| `rewrite` | `pattern`, `replace` | Reescribe la línea (`$1`..`$9`); las reglas siguientes ven el resultado. |
| `drop_closer` | `group`, `pattern` | Elimina el prompt `> ` que cierra un bloque de estado (`group`) que no conservó ninguna línea. |
| `drop_before` | `pattern`, `candidate`, `max_lines` | Al coincidir `pattern`, elimina hasta `max_lines` líneas anteriores que cumplan `candidate` (usuario/clave escritos por adelantado, antes de su prompt). |
| `drop_secret` | `window` | Defensa extra: elimina una línea igual a un token ya eliminado como eco de login, solo dentro de `window` líneas tras una regla de login. |

* Los patrones usan solo el subconjunto de regex idéntico en Python `re` y JavaScript (sin lookbehind, sin `\Z`, sin flags en línea) y se aplican con *search*: ancla con `^`.
* El estado de `dedupe_on_change` empieza vacío en cada entrada, así que pegar un fragmento (sin banner, o a mitad de un bloque de estado) funciona igual.

---

## 🛠️ Estructura del Proyecto

```text
├── engine.py              # Motor principal en Python (+ CLI: python engine.py log.txt)
├── build_rules.py         # Compilador de reglas (colorizado + preprocess) a JSON y JS
├── mine_rooms.py          # Extractor de habitaciones desde logs videntes
├── rooms.json             # Catálogo de 280+ rooms y sus colores
├── rules.json             # Reglas compiladas
├── run_all_tests.py       # Atajo para ejecutar toda la suite
├── tests/                 # Suite unittest (fixtures cortos, preprocesado, paridad Python/JS)
├── webapp/                # Aplicación Web estática
│   ├── index.html         # Interfaz de usuario
│   ├── style.css          # Estilos MUD terminal
│   ├── app.js             # Controlador de eventos y UI
│   ├── engine.js          # Motor JavaScript (espejo de engine.py)
│   └── rules.js           # Reglas compiladas para el navegador
└── .github/workflows/
    └── deploy.yml         # Despliegue automático a GitHub Pages
```

---

## 🧪 Pruebas y Validación de Paridad

```bash
python -m unittest discover -s tests -v
```

Incluye pruebas de cada tipo de regla de preprocesado, de la detección de cliente, fixtures cortos de VIPMud/Mudlet (con credenciales falsas) y la **paridad exacta Python == JavaScript** (`tests/test_parity.py`; requiere `node` en el PATH, si no está se omite con un aviso).

---

## 📏 Evaluación contra logs coloreados de referencia

Para medir automáticamente la exactitud de los colores se comparan nuestras salidas con logs reales coloreados por Mudlet (Deathlogs, jugadores Naghig y Kunkh).

```bash
python tools/fetch_reference_logs.py          # descarga a cache_reference/ (ignorado por git, con pausa de 1 s entre peticiones)
python tools/evaluate.py --top 40 --json resultado.json
```

El evaluador alinea cada línea por índice y verifica que el texto visible sea idéntico; las líneas cuyo texto difiere se cuentan aparte y no se puntúan. Informa de la exactitud por carácter (sin espacios), el porcentaje de líneas exactas, las confusiones de color más frecuentes (esperado -> obtenido) y las formas de línea que más fallan, con un ejemplo en texto plano apto para lectores de pantalla (`[#c0c0c0]Sendero [#808080][so,se]`). Los logs descargados nunca se versionan.

---

## 🤝 Fork y Contribuciones

Si eres un jugador de RL o desarrollador y quieres agregar nuevas reglas, colores de rooms o habilidades:

1. Haz un **Fork** de este repositorio.
2. Si agregas o modificas reglas en `build_rules.py` o habitaciones en `rooms.json`, ejecuta:
   ```bash
   python build_rules.py
   python -m unittest discover -s tests
   ```
3. Envía tu **Pull Request**.

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.
