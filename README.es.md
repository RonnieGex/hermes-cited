# hermes-cited

Cited en [Hermes Agent](https://github.com/NousResearch/hermes-agent): un plugin nativo de Python que le da
a Hermes las herramientas de solo lectura de [Cited](https://github.com/RonnieGex/cited) como herramientas
nativas, dos modos de conversación y un modo cited cuya respuesta **la escribe el plugin** a partir de los
renglones exactos que eligió el modelo, con una bitácora auditable encadenada por hash y bajo custodia.

Hecho por Katalis. Apache-2.0.

- **Modo dot** (el default): respuestas normales; Cited se usa cuando ayuda y la respuesta no se toca.
- **Modo cited**: el modelo solo *elige*. Busca en Cited y luego llama a `cited_quote` con los renglones
  numerados que el usuario debe leer. El plugin descarta la prosa del modelo por completo y compone esos
  renglones **byte por byte**, cada uno con su documento, su sección y su marca `[n]`, y agrega el sello
  `Verified by Cited`. Cuando no hay nada que elegir, la respuesta es la negativa fija
  `No está en los documentos.`

## Requisitos

- Hermes Agent con la API nativa de plugins. Todo se verificó en **v0.21.6+387 (commit `dce1e9b`)**, Python
  3.11.15 del venv de Hermes, en Windows.
- Una instalación de Cited cuyo `/api/mcp` acepte el encabezado `MCP-Protocol-Version` que Hermes manda
  desde `initialize`. Hermes manda `2025-11-25`; Cited necesita
  [RonnieGex/cited#21](https://github.com/RonnieGex/cited/pull/21), fusionado en `main` como `ef11f88`. Sin
  eso la conexión falla con `the protocol version 2025-11-25 is not supported`. La puerta de este
  repositorio compila su Cited de prueba desde `origin/main`, que ya trae esa fusión.
- El `CITED_MCP_TOKEN` de esa instalación.

## Instalación en un paso

```bash
hermes plugins install RonnieGex/hermes-cited --enable
```

Desde un checkout local, que es lo que usa la puerta de este repositorio:

```bash
hermes plugins install "file:///C:/ruta/absoluta/a/hermes-cited" --enable --yes-deps
```

El comando clona el repositorio en `$HERMES_HOME/plugins/hermes-cited` y lo habilita. El plugin es opt-in:
queda apagado hasta que aparece en `plugins.enabled`.

## Configuración

Escribe estas variables en `$HERMES_HOME/.env` (el archivo que Hermes carga en el entorno del proceso que
corre el plugin):

| Variable | Obligatoria | Qué hace |
|---|---|---|
| `CITED_URL` | sí | La dirección de la instalación, como `https://cited.example.com`. El plugin llama a `<CITED_URL>/api/mcp`. Una URL que ya termina en `/api/mcp` se usa tal cual. |
| `CITED_MCP_TOKEN` | sí | El token bearer de esa instalación. Viaja solo en el encabezado `Authorization` de una petición a `CITED_URL`. |
| `CITED_TIMEOUT_MS` | no | Cuánto puede tardar una llamada a Cited, en milisegundos. `30000` por omisión. |
| `CITED_DEFAULT_MODE` | no | El modo con el que arranca una conversación, `dot` o `cited`. `dot` por omisión. |
| `CITED_LANGUAGE` | no | El idioma del render de cited, `es` o `en`. `es` por omisión. Los renglones citados siempre son los bytes del documento. |
| `CITED_AUDIT_KEY_PATH` | no | Dónde viven la llave HMAC del checkpoint y su high-water mark. Por omisión `%APPDATA%\Katalis\hermes-cited\audit.key`. Nunca está dentro de `HERMES_HOME` y nunca es el bearer de Cited. |

Sin `CITED_URL` o `CITED_MCP_TOKEN` las herramientas de búsqueda responden una oración que nombra la
variable faltante. Nunca lanzan una excepción hacia Hermes y Hermes sigue funcionando.

## Las tres herramientas nativas

| Herramienta | Entrada | Salida |
|---|---|---|
| `cited_search` | `query` (obligatoria), `limit` (1 a 8, 5 por omisión) | Los pasajes que coinciden, cada uno con `n`, `document`, `heading`, `position`, `excerpt` y sus `lines` numerados. |
| `cited_ask` | `question` (obligatoria), `sessionId` (opcional) | `status` (`answered` o `refused`), `answer` y las `citations` numeradas, cada una con sus `lines`. |
| `cited_quote` | `passage` (la `n` de un pasaje o cita de este turno), `lines` (sus números de renglón, en orden) | El texto exacto de esos renglones, y el plugin registra la elección para la respuesta. |

Llaman a `POST <CITED_URL>/api/mcp` con el método JSON-RPC `tools/call` y
`Authorization: Bearer <CITED_MCP_TOKEN>`. Son nativas y no una configuración MCP porque así la instalación
es un paso y porque el plugin necesita ver cada resultado para componer la respuesta y escribir la bitácora.

## Los dos modos

- `/cited` enciende el modo cited para esta conversación; `/dot` lo apaga. La clave es la sesión cuando la
  superficie expone una y el perfil cuando no. `CITED_DEFAULT_MODE` fija el modo inicial.
- En modo cited, `pre_llm_call` inyecta las reglas: llama primero a Cited, elige los renglones con
  `cited_quote` y no escribas la respuesta. El texto del modelo se descarta por completo. Un render real,
  de `cited_quote` con `{"passage": 1, "lines": [4]}` contra `cafe-la-horquilla.md · Precios`, es:

  ```
  Según tus documentos:

  - Afinacion de bicicleta: 380 pesos. [1]
  Fuente: cafe-la-horquilla.md - Precios

  Verified by Cited
  ```

- Cada pasaje o cita se parte en renglones de forma determinista (por salto de línea; un párrafo sin saltos
  es un renglón) y se numera desde 1. Cada bloque mostrado es *idéntico* a un renglón completo de un extracto
  del turno: no hay normalización Unicode, ni subcadenas, ni listas de palabras, porque el plugin escribió el
  bloque desde el extracto mismo. Un valor, un sujeto o un sello que escriba el modelo nunca llegan a la
  respuesta.
- Cuando no hay nada que mostrar —el modelo no llamó a `cited_quote`, Cited se negó o el turno no tuvo
  extractos— la respuesta es la negativa fija `No está en los documentos.` (en inglés,
  `It is not in the documents.`). Nunca lleva el sello.
- El sello `Verified by Cited` solo lo agrega el plugin, solo después de persistir el texto exacto que se
  entrega y solo si la política de entrega lo permite. La marca `[1]`, la fuente y el sello los genera el
  plugin; el modelo no escribe ninguno.
- El modo dot entrega el texto del modelo tal cual. Si el modelo escribe ahí el sello reservado, se quita.
- Los totales y otros valores calculados quedan fuera de esta ronda: pertenecen a la misión de documentos,
  donde una herramienta los calcula por código y registra la procedencia.

## Entrega: qué queda verificado y qué puede verse

Hermes v0.21.6+387 entrega cada delta de texto a la pantalla, a la plataforma de mensajería y al TTS de
streaming **antes** de que `transform_llm_output` decida. Ningún hook de plugin puede retener esos deltas:
es una limitación del host, y este plugin la declara en lugar de esconderla. Resuelve el streaming efectivo
con la clase real del host, `gateway.config.StreamingConfig`, así que `mode`, `enabled`, `transport` y el
override por plataforma significan lo que Hermes significa con ellos.

| Superficie | Qué hace el plugin |
|---|---|
| Mensajería (Telegram, Slack, Discord, WeCom, Feishu, DingTalk, QQ y similares) y cualquier plataforma que el plugin no conozca | Lee la configuración efectiva de streaming y, si está encendido, retiene el sello y lo dice en la respuesta. Para recibir el sello, apaga el streaming en modo cited: `streaming.enabled: false`, o `display.platforms.<plataforma>.streaming: false`. |
| CLI | La única excepción explícita, y solo con `display.streaming: false`. Con el streaming del CLI encendido, el sello se retiene igual que en cualquier otra superficie. Cuando está apagado, `--format stream-json` igual emite eventos `text`, así que **quien consuma ese formato debe mostrar solo el registro terminal `result`**; un consumidor que concatene `text`, razonamiento o comentarios vería el borrador. |
| App de escritorio | Retiene el sello. La app cablea su propio stream SSE, que ninguna configuración de aquí alcanza: **puede verse el borrador mientras se escribe**. El texto igual se copia de los documentos del turno y queda registrado. |

La configuración exacta del gateway:

```yaml
streaming:
  enabled: false                 # interruptor maestro; `transport: off` también apaga
display:
  platforms:
    telegram:
      streaming: false           # solo estrecha; nunca enciende streaming por sí sola
```

`display.streaming` es solo del CLI; el gateway resuelve primero
`display.platforms.<plataforma>.streaming`. `docs/upstream-proposal.md` (inglés) especifica el hook de
política de entrega por turno que Hermes necesitaría para cerrar este hueco en todas las superficies,
incluida la ruta SSE, con archivo y línea de cada punto. No se abrió ningún pull request ni issue aguas
arriba.

## La bitácora

Cada respuesta agrega una entrada a `$HERMES_HOME/cited/audit.jsonl`, en ambos modos: la marca UTC, un `seq`
monotónico, la identidad del log, la plataforma, la sesión, el identificador de turno, el usuario cuando
existe, el modo, la pregunta, las llamadas a Cited con sus argumentos y el SHA-256 **y el texto** de cada
extracto devuelto, **los renglones que eligió el modelo**, las fuentes, la respuesta final y el resultado
del verificador, más `prev_hash` y `hash`. La cadena es
`hash = sha256(prev_hash + canonical_json(entry))`.

El append toma un lock exclusivo entre procesos sobre `<log>.lock` y, **antes de escribir un byte**, lee
toda la cadena, valida cada esquema, `seq`, enlace y hash, autentica el checkpoint contra la llave y cruza el
resultado con un high-water mark por identidad que vive junto a la llave, fuera de `HERMES_HOME`. Cualquier
discrepancia rechaza el append y deja el log y el checkpoint intactos; el append nunca reinicia desde
génesis. El génesis solo se permite para una identidad nueva registrada en la custodia, nunca porque un
archivo desapareció.

El append es una transacción recuperable. Registra una fila pendiente autenticada con MAC en la custodia,
agrega la fila, escribe el checkpoint y actualiza la custodia. Si un paso posterior falla, la fila se revierte,
de modo que la fila registrada es la respuesta que realmente se entregó; si la reversión misma no puede
correr, el registro pendiente autentica la conclusión en el siguiente append. La llave se crea **antes de la
primera fila** y nunca al leer: si se pierde, se falla cerrado y se exige recuperación explícita.
`CITED_AUDIT_KEY_PATH` dentro de `HERMES_HOME` se rechaza.

Después de cada append el plugin reescribe un checkpoint autenticado con HMAC (`<log>.checkpoint`) con el
conteo de entradas, el hash final y la identidad del log. Su llave vive **fuera de `HERMES_HOME`**, por
omisión en `%APPDATA%\Katalis\hermes-cited\audit.key`, y nunca es el bearer de Cited. El verificador exige el
checkpoint y el high-water mark:

- una entrada alterada, quitada o reordenada rompe la cadena;
- una entrada quitada del final, o un sufijo cortado, puede dejar la cadena internamente consistente, pero
  ya no coincide con el checkpoint;
- una cadena reescrita y con todos los hashes recalculados sin la llave no autentica;
- un checkpoint regresado a uno viejo mientras el log conserva sus entradas ya no coincide en conteo ni en
  hash final;
- un log y su checkpoint regresados **juntos** quedan por debajo del high-water mark que vive con la llave;
- un checkpoint ausente, una llave ausente y una cadena no registrada son errores, no un pase.

**Alcance exacto de la custodia:** se detecta un cambio de quien no tenga la carpeta de la llave. Si el log,
su checkpoint y el high-water mark se regresan juntos por alguien con escritura también en esa carpeta, solo
la custodia remota puede notarlo: eso llega con Cited Ledger. La llave prueba autenticidad, no inmutabilidad
remota.

Verifícala desde el plugin instalado, que es donde el módulo es importable:

```powershell
Push-Location (Join-Path $env:HERMES_HOME 'plugins/hermes-cited')
try {
    python -m hermes_cited.verify_log (Join-Path $env:HERMES_HOME 'cited/audit.jsonl')
} finally {
    Pop-Location
}
# OK: 4 entries, the chain and its checkpoint verify.   (salida 0)
# BROKEN: the log is below its high-water mark: ...     (salida 1)
```

Usa explícitamente el Python de Hermes cuando `python` no sea ese intérprete. Correr el módulo desde otro
directorio falla con `ModuleNotFoundError: No module named 'hermes_cited'`: Hermes importa un plugin de
directorio como `hermes_plugins.<slug>` y nunca lo instala como paquete de nivel superior.

## La skill `cited`

El plugin incluye una skill `cited` y la registra con `ctx.register_skill`, así que aparece entre las skills
disponibles del agente mientras el plugin está habilitado. Dice cuándo usar cada herramienta, que el plugin
escribe la respuesta cited y que el modelo solo elige renglones con `cited_quote`, que una negativa de Cited
se pasa tal cual y que en modo cited nada se completa con el conocimiento del modelo. En la ruta solo-MCP
existen las dos herramientas de búsqueda, pero `/cited`, `/dot`, `cited_quote`, el render y la bitácora no:
no hay plugin que los corra.

## La ruta MCP, sin instalar nada

Cited también se alcanza como servidor MCP, sin plugin. Es la ruta para cualquier cliente MCP; en Hermes las
dos herramientas de búsqueda aparecen como `mcp__cited__cited_search` y `mcp__cited__cited_ask`. La skill es
lo que hace que el agente busque en Cited antes que en la web, así que copia
`hermes_cited/skills/cited/SKILL.md` a `$HERMES_HOME/skills/cited/SKILL.md`.

`hermes mcp add cited --url <CITED_URL>/api/mcp --auth header` pide el token, lo guarda en
`$HERMES_HOME/.env` como `MCP_CITED_API_KEY` y escribe esto en `$HERMES_HOME/config.yaml`:

```yaml
mcp_servers:
  cited:
    url: http://127.0.0.1:3246/api/mcp
    headers:
      Authorization: Bearer ${MCP_CITED_API_KEY}
    enabled: true
```

`${VAR}` se lee de `$HERMES_HOME/.env` o del entorno. Agrega `trust: untrusted` a esa entrada para que las
dos herramientas, que son de solo lectura, corran sin aprobación. Verifícala con `hermes mcp test cited`,
que debe conectar y listar las dos herramientas.

## Qué se probó (2026-10-10)

Todo lo de abajo se corrió el 2026-10-10 con Hermes Agent **v0.21.6+387 (`dce1e9b`)**, el modelo DeepSeek
(`--provider deepseek -m deepseek-flash`), un Cited compilado desde `origin/main` (`ef11f88`, el PR #21 ya
fusionado) en su propio worktree temporal y servido en `127.0.0.1:3246` con los cuatro documentos de su
`samples/`, y un `HERMES_HOME` temporal. `scripts/gate.py`, corrido con el Python del venv de Hermes,
afirma las propiedades e imprime `GATE: GREEN`; su salida y las transcripciones están dentro del cambio
(`openspec/changes/hermes-plugin-r3/reports/`).

**El `%LOCALAPPDATA%\hermes` real no se escribió ni se usó como destino de ninguna corrida de esta ronda.**
La corrida aislada final y su puerta usan solo homes temporales. Una corrida histórica de la ronda 1,
al inicio de `mision-cited-hermes.md`, ejecutó `hermes mcp test cited` **sin** `HERMES_HOME` y leyó la
configuración real (una prueba de conexión de solo lectura contra el Cited vivo en el puerto 3240, que
falló). Ocurrió una vez, se conserva aquí en lugar de negarla y se reporta como RISK en
`tasks/entrega-cited-hermes-r2.md`. No se escribió ningún byte bajo el home real y ninguna corrida de la
ronda 2 ni de la ronda 3 tocó el puerto 3240.

| Qué | Resultado |
|---|---|
| La suite unitaria (`pytest`) | verde: el cliente y su rechazo de redirecciones, las tres herramientas, el verificador por construcción, el render escrito por el plugin, la custodia del log con su high-water mark y su transacción, el resolutor de entrega del host, los modos y la skill empaquetada, más un caso adversarial por hallazgo de ambas revisiones |
| `hermes mcp test cited` | conectó, `Tools discovered: 2` (`cited_search`, `cited_ask`) |
| `hermes plugins install "file:///…" --enable --yes-deps` | instalado en `$HERMES_HOME/plugins/hermes-cited` y habilitado |
| El loader real | el plugin instalado carga con el gestor de plugins de Hermes y registra sus tres hooks |
| La pregunta de precio en la ruta MCP | el stream llama a `mcp__cited__cited_search` y responde **380 pesos** con la cita de `cafe-la-horquilla.md · Precios` |
| La pregunta de precio en modo cited | el stream llama a la `cited_search` nativa y luego a `cited_quote`; la respuesta entregada es el render del plugin, con `Fuente: cafe-la-horquilla.md - Precios`, la marca `[1]` y el sello |
| "Is there a guarantee on repairs at the bike workshop?" | el render lleva **90 days** desde `bike-workshop-policies.md · Guarantee`, sellado |
| Una pregunta que los samples no responden | exactamente `No está en los documentos.`, sin dato y sin sello |
| La bitácora de esos turnos | una entrada por turno, conteo exacto, `python -m hermes_cited.verify_log` desde el plugin instalado dice `OK` y sale 0; alterar una entrada, cortar un sufijo, reescribir y recalcular, regresar el checkpoint, regresar log y checkpoint juntos, o arrancar sin la llave la hacen salir 1 |
| Modo dot | se entrega el texto del modelo, se quita cualquier sello reservado y la entrada se registra con el verificador marcado como no aplicado |
| El contrato cited | casos adversariales prueban que un valor cambiado, un sujeto movido, una subcadena, la prosa libre y un sello falsificado nunca llegan a la respuesta entregada |
| La política de entrega | con `streaming.enabled: true` o `mode: edit`, una respuesta cited en `telegram`, `wecom`, `feishu`, `dingtalk`, `qqbot` o una plataforma desconocida retiene el sello y lo dice; el CLI con `display.streaming: false` sella, el CLI con streaming encendido y el escritorio lo retienen |
| La skill `cited` | registrada por el plugin y presente en el árbol instalado, con la regla de `cited_quote` y la nota de que los comandos son del plugin |

No se probó en esta ronda: un bot real de Telegram/Slack/Discord/WeCom (la política de entrega se prueba en
proceso y contra la clase real `StreamingConfig` del host), una TUI interactiva, macOS o Linux, ni la
instalación contra la URL pública de GitHub.

## Seguridad

- El token viaja solo en el encabezado `Authorization` de una petición a `CITED_URL`. Un `3xx` se rechaza
  antes de cualquier segunda petición, así que una redirección nunca puede llevar el bearer a otro origen.
- Antes de construir cualquier resultado visible, en éxito y en error, el cliente rechaza una respuesta que
  refleje el token en cualquier cadena; la respuesta se descarta y nada de ella se muestra ni se registra.
- Antes de calcular el hash y agregar, cada campo de la entrada de la bitácora se redacta recursivamente,
  incluidos la pregunta, los argumentos, los extractos, la respuesta y los errores.
- `401`, `403`, `404`, `405`, un timeout y una falla de red se convierten cada uno en una oración distinta
  que el modelo puede leer. El plugin nunca escribe un secreto en un log, un resultado de herramienta, el
  archivo de bitácora ni la evidencia.
- El plugin es de solo lectura contra Cited: nunca escribe un documento y nunca llama a un modelo por su
  cuenta. Solo `cited_ask` puede guardar un turno, y solo cuando quien llama pasa un `sessionId`.
- La llave del checkpoint y el high-water mark viven fuera de `HERMES_HOME`; la llave se crea antes de la
  primera fila, nunca al leer, y nunca es el bearer de Cited. Una ruta de llave dentro de `HERMES_HOME` se
  rechaza.

## Licencia

Apache-2.0. Ver `LICENSE` y `NOTICE`. Versión en inglés: [README.md](README.md).
