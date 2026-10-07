# RL Log Colorizer

Convierte un log de VIPMud o Mudlet de Reinos de Leyenda, sin colores, en HTML coloreado en el formato que acepta [Deathlogs](https://deathlogs.com/). Los colores son los que ve un jugador de Mudlet con la vista habitual del juego, así que quien juega con lector de pantalla puede subir sus logs con el mismo aspecto.

Página en vivo: https://miguel-cinsfran.github.io/rl-mud-colorizer/

## Cómo se usa la página

1. Pega el log en el cuadro de la izquierda o carga un archivo `.txt`. Se leen archivos en UTF-8 y en Windows-1252, que es lo que escribe VIPMud.
2. El resultado se actualiza mientras pegas. `Ctrl+Enter` lo fuerza.
3. Pulsa "Copiar para Deathlogs" y pega el contenido en el campo Log del formulario de envío.

Lo que se copia lleva cada línea en su propia línea de texto, sin `<br>`: Deathlogs convierte cada salto de línea en un `<br>`, y si el log ya los trae, queda una línea en blanco entre cada línea. El botón de descarga guarda el `.html` con el formato exacto que exporta Mudlet, para abrirlo en el navegador. La pestaña "HTML" muestra lo mismo que se copia.

## Privacidad

Todo se ejecuta en tu navegador y no se envía nada a ningún servidor.

El inicio de sesión (banner, usuario, clave y texto de bienvenida) se borra siempre antes de colorizar, incluso si pegas solo un fragmento del log. En el bloque de estado de VIPMud se quitan siempre `Pv`, `SL`, `PL` y `Jgd`, porque el juego ya muestra su propia línea `Pvs:` cuando cambia la vida. `Imágenes`, `Pieles`, `Astucia` e `Inercia` aparecen solo cuando cambian y nunca si valen 0. También se quitan las líneas en blanco. Los logs de Mudlet no pierden nada de esto.

## Colores de los títulos de sala

Cada título de sala toma su color de la primera fuente que lo conozca:

1. El color del terreno en el mapa de Mudlet, por nombre exacto de sala y después por zona.
2. El catálogo de salas (`rooms.json`).
3. Blanco, si ninguna de las dos lo conoce.

Los colores demasiado oscuros sobre fondo negro se aclaran hasta llegar a un contraste de 4,5. Las salas que en el mapa quedaron con terreno blanco se tratan como sin dato, para que decida el catálogo.

Cuando tengas una exportación nueva del mapa en JSON, regenera los colores y las reglas:

```
python tools/extract_map_colors.py ruta/al/map_export.json
python build_rules.py
```

El primer comando escribe `room_map_colors.json` y el segundo recompila `rules.json` y `webapp/rules.js`.

## Línea de comandos

```
python engine.py log.txt -o salida.html
```

Sin `-o`, el HTML sale por la salida estándar. `--client vipmud` (o `mudlet`) fuerza el cliente en lugar de detectarlo, `--no-preprocess` omite la limpieza de inicio de sesión y bloque de estado, y `--deathlogs` genera la versión para pegar en Deathlogs en lugar del formato de Mudlet.

## Para quien quiera contribuir

Las reglas de color y de limpieza están en `build_rules.py`. Después de cambiarlas, o de tocar `rooms.json`, ejecuta:

```
python build_rules.py
python -m unittest discover -s tests
```

El motor existe dos veces, `engine.py` y `webapp/engine.js`, y ambos deben dar exactamente la misma salida. `tests/test_parity.py` lo comprueba con `node`; si `node` no está instalado, esa prueba se omite.

Hay tres garantías con pruebas propias: ninguna línea que antes tenía color puede quedarse sin él, el texto visible nunca cambia, y el borrado de credenciales se verifica quitando cada regla de login por turnos para confirmar que alguna prueba falla.

Para medir la exactitud contra logs reales coloreados por Mudlet:

```
python tools/fetch_reference_logs.py
python tools/evaluate.py
```

El primer comando descarga los logs a `cache_reference/`, que git ignora. El segundo compara línea por línea, solo cuando el texto visible coincide, e informa del porcentaje de caracteres y líneas con el color correcto y de las confusiones más frecuentes.

## Créditos y licencia

La versión original y el trabajo de colores vienen de Franco M. Paniagua (FrancoMPaniagua), jugador de Mudlet. Licencia MIT, en el archivo [LICENSE](LICENSE).
