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

Los mensajes privados también se quitan, salvo que lo desmarques: la casilla "Quitar mensajes privados (telepatías)" viene marcada y está antes del botón de colorizar. Al cambiarla, el resultado se recalcula y se anuncia cuántas líneas privadas se quitaron. Se borran:

- Lo que te dicen: `X te dice:`, `X te pregunta:` y `X te exclama:`, y las líneas sangradas que continúan el mensaje.
- El aviso `X contacta telepáticamente con ...`.
- Lo que dices: `Dices a X:`, `Preguntas a X:` y `Exclamas a X:`.
- El comando con el que lo escribiste. No se reconoce por la palabra (`t`, `tell`, `r` o un alias propio), sino por el mensaje: se busca, en las 15 líneas anteriores, la más reciente que termine con el mismo mensaje. Lo que haya entre medias se conserva.

También se quitan los mensajes de los PNJ que te hablan con `te dice:`. Un comando de telepatía sin texto, o con un mensaje que el juego mostró distinto, puede quedar en el log.

## Colores de los títulos de sala

Cada título de sala toma su color de la primera fuente que lo conozca:

1. Los logs de referencia de Mudlet (ver la sección siguiente a la de ítems). Ahí se ve el color que manda el juego, que a veces cambia dentro del mismo título: en "Campos de Cultivo", "Campos de" sale en gris y "Cultivo" en amarillo.
2. El color del terreno en el mapa de Mudlet, por nombre exacto de sala y después por zona.
3. El catálogo de salas (`rooms.json`).
4. Blanco, si ninguna fuente lo conoce.

Un título que sale gris de punta a punta se pinta blanco, para que se distinga del texto. Las salas de una zona gris, como Anduar, llevan la zona en blanco y el resto en gris. Los colores demasiado oscuros sobre fondo negro se aclaran hasta llegar a un contraste de 4,5. Las salas que en el mapa quedaron con terreno blanco se tratan como sin dato.

Cuando tengas una exportación nueva del mapa en JSON, o más logs de referencia, regenera los colores y las reglas:

```
python tools/extract_map_colors.py ruta/al/map_export.json
python tools/extract_reference_rooms.py
python build_rules.py
```

El primer comando escribe `room_map_colors.json`, el segundo `room_reference_colors.json` a partir de los logs de referencia y el tercero recompila `rules.json` y `webapp/rules.js`.

## Colores de los ítems

Los nombres de ítems conocidos se pintan con los colores del juego, letra por letra si hace falta ("Capucha" en gris y "Tenebrosa" en violeta), en cualquier línea que no tenga ya otro color: inventario, empuñar, quitarse cosas o lo que otro saca de su bolsa. Un nombre partido en dos líneas por el ancho del juego queda sin color.

Los datos salen de la API pública de la [Armería de RL](https://armeria.reinosdeleyenda.es), que guarda los códigos de color de cada ítem. Esos códigos se pasan a los tonos que muestra Mudlet, comprobados contra los logs de referencia. Si esos logs muestran un ítem con otros colores de forma constante, mandan los logs. No se colorean los nombres de una sola palabra, como "Agua" o "Perla", porque son palabras de uso común; sí los que van pegados, como "RobaAlmas". Para actualizarlo:

```
python tools/build_item_colors.py
python build_rules.py
```

El primer comando baja el catálogo entero (unas 40 consultas, con una pausa entre cada una), guarda una copia en `cache_armeria/`, que git ignora, y escribe `item_colors.json`. Con `--desde cache_armeria/items.json` se rehace sin volver a bajarlo.

## Logs de referencia

Son logs de RL que otros jugadores subieron a Deathlogs desde Mudlet. Mudlet guarda cada tramo de texto con su color exacto, así que muestran cómo se ve el juego de verdad. Sirven para tres cosas: sacar los colores de las salas, corregir los de los ítems y medir cuánto se parece nuestra salida a la de Mudlet.

```
python tools/fetch_reference_logs.py --recientes 200
python tools/evaluate.py --players Naghig Kunkh recientes
```

El primer comando baja los logs de Naghig y Kunkh y los últimos 200 de RL a `cache_reference/`, que git ignora. Espera un segundo entre pedido y pedido y no vuelve a bajar lo que ya tiene. `python tools/fetch_reference_logs.py --help` explica las opciones.

Quedan fuera tres tipos de logs:

- Los de zMUD y otros clientes, porque sus colores no son los de Mudlet. Se distinguen por cómo está hecho el HTML: Mudlet marca cada tramo de color con `<span style="color: rgb(...)">`, y zMUD con etiquetas `<font color=...>`. Un log cuenta como de Mudlet cuando tiene más de diez veces más tramos `<span>` con color que etiquetas `<font>` (la página de Deathlogs ya trae un `<font>` propio).
- Los que se subieron con esta herramienta. En Deathlogs quedan iguales que los de Mudlet, así que no hay forma de reconocerlos por el contenido. Sus números se anotan en `OWN_UPLOADS`, dentro del script, y hay que agregar cada log nuevo que se suba.
- Los de otros juegos o números que no existen.

Los descartados se anotan en `cache_reference/recientes/descartados.txt` para no volver a pedirlos.

Hay además jugadores que cambiaron el color base de Mudlet, por ejemplo a verde, y su log sale casi entero de ese color. Esos logs se bajan pero no se usan ni para sacar colores ni para medir: se reconocen porque más de la mitad del texto tiene un mismo color que no es el gris normal.

El evaluador compara línea por línea, solo cuando el texto visible coincide, e informa del porcentaje de caracteres y líneas con el color correcto y de las confusiones más frecuentes. Muchas de esas confusiones son a propósito: hay líneas que aquí llevan color para leerse mejor y en Mudlet salen grises.

## Línea de comandos

```
python engine.py log.txt -o salida.html
```

Sin `-o`, el HTML sale por la salida estándar. `--client vipmud` (o `mudlet`) fuerza el cliente en lugar de detectarlo, `--no-preprocess` omite la limpieza de inicio de sesión y bloque de estado, `--keep-private` conserva los mensajes privados, que por defecto se quitan, y `--deathlogs` genera la versión para pegar en Deathlogs en lugar del formato de Mudlet.

## Para quien quiera contribuir

Las reglas de color y de limpieza están en `build_rules.py`. Después de cambiarlas, o de tocar `rooms.json`, ejecuta:

```
python build_rules.py
python -m unittest discover -s tests
```

El motor existe dos veces, `engine.py` y `webapp/engine.js`, y ambos deben dar exactamente la misma salida. `tests/test_parity.py` lo comprueba con `node`; si `node` no está instalado, esa prueba se omite.

Hay tres garantías con pruebas propias: ninguna línea que antes tenía color puede quedarse sin él, el texto visible nunca cambia, y el borrado de credenciales se verifica quitando cada regla de login por turnos para confirmar que alguna prueba falla.

## Créditos y licencia

La versión original y el trabajo de colores vienen de Franco M. Paniagua (FrancoMPaniagua), jugador de Mudlet. Licencia MIT, en el archivo [LICENSE](LICENSE).
