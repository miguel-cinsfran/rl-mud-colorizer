# RL Log Colorizer

Convierte un log de VIPMud o Mudlet de Reinos de Leyenda, sin colores, en HTML coloreado en el formato que acepta [Deathlogs](https://deathlogs.com/). Los colores son los que ve un jugador de Mudlet con la vista habitual del juego, así que quien juega con lector de pantalla puede subir sus logs con el mismo aspecto.

Página en vivo: https://miguel-cinsfran.github.io/rl-mud-colorizer/

## Cómo se usa la página

1. Pega el log en el cuadro de la izquierda o carga un archivo `.txt`. Se leen archivos en UTF-8 y en Windows-1252, que es lo que escribe VIPMud.
2. El resultado se actualiza mientras pegas. `Ctrl+Enter` lo fuerza.
3. Pulsa "Copiar para Deathlogs" y pega el contenido en el campo Log del formulario de envío.

Se copia el mismo HTML que exporta Mudlet, igual que el botón de descarga. Deathlogs convierte cada salto de línea en un `<br>` y conserva los que ya trae el log, así que queda una línea en blanco entre cada línea, que es como se lee más cómodo. La pestaña "HTML" muestra lo mismo que se copia.

## Privacidad

Todo se ejecuta en tu navegador y no se envía nada a ningún servidor.

El inicio de sesión (banner, usuario, clave y texto de bienvenida) se borra siempre antes de colorizar, incluso si pegas solo un fragmento del log. En el bloque de estado de VIPMud se quitan siempre `Pv`, `SL`, `PL` y `Jgd`, porque el juego ya muestra su propia línea `Pvs:` cuando cambia la vida. `Imágenes`, `Pieles`, `Astucia` e `Inercia` aparecen solo cuando cambian y nunca si valen 0. También se quitan las líneas en blanco. Los logs de Mudlet no pierden nada de esto.

Los mensajes privados también se quitan, salvo que lo desmarques: la casilla "Quitar mensajes privados (telepatías)" viene marcada y está antes del botón de colorizar. Al cambiarla, el resultado se recalcula y se anuncia cuántas líneas privadas se quitaron. Se borran:

- Lo que te dicen: `X te dice:`, `X te pregunta:` y `X te exclama:`, y las líneas sangradas que continúan el mensaje.
- El aviso `X contacta telepáticamente con ...`.
- Lo que dices: `Dices a X:`, `Preguntas a X:` y `Exclamas a X:`.
- El comando con el que lo escribiste. No se reconoce por la palabra (`t`, `tell`, `r` o un alias propio), sino por el mensaje: se busca, en las 15 líneas anteriores, la más reciente que termine con el mismo mensaje. Lo que haya entre medias se conserva.

También se quitan los mensajes de los PNJ que te hablan con `te dice:`. Un comando de telepatía sin texto, o con un mensaje que el juego mostró distinto, puede quedar en el log.

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

Sin `-o`, el HTML sale por la salida estándar. `--client vipmud` (o `mudlet`) fuerza el cliente en lugar de detectarlo, `--no-preprocess` omite la limpieza de inicio de sesión y bloque de estado, `--keep-private` conserva los mensajes privados, que por defecto se quitan, y `--deathlogs` genera una versión compacta, sin `<br>`, que Deathlogs muestra sin líneas en blanco.

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
