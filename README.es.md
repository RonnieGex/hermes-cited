# hermes-cited

Cited en [Hermes Agent](https://github.com/NousResearch/hermes-agent): un plugin nativo de Python que le da
a Hermes las dos herramientas de solo lectura de [Cited](https://github.com/RonnieGex/cited) como
herramientas nativas, dos modos de conversación, un verificador extractivo de la respuesta final y una
bitácora auditable encadenada por hash con checkpoint autenticado.

Hecho por Katalis. Apache-2.0.

- **Modo dot** (el default): respuestas normales; Cited se usa cuando ayuda.
- **Modo cited**: antes del turno se inyectan las reglas estrictas y después un verificador determinista,
  sin IA, acepta un dato solo cuando la oración o el renglón completo que lo lleva aparece **textual**
  dentro de un extracto que Cited devolvió en ese mismo turno. Una respuesta que pasa termina con
  `Verified by Cited` y sus fuentes; una que reformula un valor con sus propias palabras —aunque el número
  sea el correcto— se reemplaza por una negativa que nombra el segmento que no pudo verificar.

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
| `CITED_AUDIT_KEY_PATH` | no | Dónde vive la llave HMAC del checkpoint de la bitácora. Por omisión `%APPDATA%\Katalis\hermes-cited\audit.key`. Nunca está dentro de `HERMES_HOME` y nunca es el bearer de Cited. |

Sin `CITED_URL` o `CITED_MCP_TOKEN` las dos herramientas responden una oración que nombra la variable
faltante. Nunca lanzan una excepción hacia Hermes y Hermes sigue funcionando.

## Las dos herramientas nativas

| Herramienta | Entrada | Salida |
|---|---|---|
| `cited_search` | `query` (obligatoria), `limit` (1 a 8, 5 por omisión) | Los pasajes que coinciden, cada uno con `n`, `document`, `heading`, `position` y `excerpt`, exactamente como los mandó Cited. |
| `cited_ask` | `question` (obligatoria), `sessionId` (opcional) | `status` (`answered` o `refused`), `answer` y las `citations` numeradas con sus extractos. |

Llaman a `POST <CITED_URL>/api/mcp` con el método JSON-RPC `tools/call` y
`Authorization: Bearer <CITED_MCP_TOKEN>`. Son nativas y no una configuración MCP porque así la instalación
es un paso y porque el plugin necesita ver cada resultado para verificar la respuesta y escribir la bitácora.

## Los dos modos

- `/cited` enciende el modo cited para esta conversación; `/dot` lo apaga. La clave es la sesión cuando la
  superficie expone una y el perfil cuando no. `CITED_DEFAULT_MODE` fija el modo inicial.
- En modo cited, `pre_llm_call` inyecta las reglas en el mensaje del usuario: llama primero a Cited, responde
  solo desde los extractos de este turno, copia cada dato entre `« »` exactamente como lo escribe el
  extracto, pasa la negativa tal cual y nunca rellena un hueco desde la web ni desde su conocimiento.
- Al final del turno `transform_llm_output` corre el verificador. Parte la respuesta en oraciones y
  renglones, separa el texto entrecomillado del libre y revisa cada segmento que lleve un dato:
  - un segmento con número, precio, unidad, fecha o código que **no** está entre `« »` se rechaza: el texto
    libre no puede llevar ningún dato;
  - un segmento entrecomillado se acepta solo cuando aparece textual —tras normalización Unicode NFKC, sin
    acentos, en minúsculas y con los espacios colapsados en ambos lados— dentro de un `excerpt` no vacío que
    Cited devolvió en ese mismo turno.
- La evidencia son solo `passages[].excerpt` y `citations[].excerpt`. La consulta, la respuesta generada por
  `cited_ask`, los encabezados, las posiciones, los conteos y el texto de transporte nunca son evidencia. Un
  turno con cero extractos no puede sellarse.
- Las marcas de cita como `[1]` se quitan antes de revisar el segmento y se validan aparte contra el mapa de
  citas del turno; una marca sin pasaje o cita correspondiente se rechaza.
- Un `status: refused` de `cited_ask` se convierte en una negativa explícita, nunca en un sello.
- Una respuesta que pasa se conserva y termina con `Verified by Cited` y las fuentes que Cited dio. El modo
  dot no reemplaza nada y nunca lleva el sello.
- Los totales y otros valores calculados quedan fuera de esta ronda: pertenecen a la misión de documentos,
  donde una herramienta los calcula por código y registra la procedencia.

## Entrega: qué queda verificado y qué puede verse

Hermes v0.21.6+387 entrega cada delta de texto a la pantalla, a la plataforma de mensajería y al TTS de
streaming **antes** de que `transform_llm_output` decida. Ningún hook de plugin puede retener esos deltas:
es una limitación del host, y este plugin la declara en lugar de esconderla.

| Superficie | Qué hace el plugin |
|---|---|
| Mensajería (Telegram, Slack, Discord y similares) | Lee la configuración efectiva de streaming y, si está encendido, retiene el sello y lo dice en la respuesta. Para recibir el sello, apaga el streaming en modo cited: `streaming.enabled: false`, o `display.platforms.<plataforma>.streaming: false`. |
| CLI | Conserva el sello. `--format stream-json` emite eventos `text`, así que **quien consuma ese formato debe mostrar solo el registro terminal `result`**; un consumidor que concatene `text`, razonamiento o comentarios vería el borrador. Con `display.streaming: false` el borrador desaparece por completo. |
| App de escritorio | Conserva el sello. La app cablea su propio stream SSE, que ninguna configuración de aquí alcanza: **puede verse el borrador mientras se escribe**. La respuesta final sí queda verificada y registrada. |

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
`display.platforms.<plataforma>.streaming`. Discord y Slack solo hacen streaming por edición cuando el
interruptor global está encendido y no hay clave por plataforma, así que escribe `false` explícito para una
garantía dura. `docs/upstream-proposal.md` (inglés) especifica el hook de política de entrega por turno que
Hermes necesitaría para cerrar este hueco en todas las superficies, incluida la ruta SSE, con archivo y
línea de cada punto. No se abrió ningún pull request ni issue aguas arriba.

## La bitácora

Cada respuesta agrega una entrada a `$HERMES_HOME/cited/audit.jsonl`, en ambos modos: la marca UTC, un `seq`
monotónico, la identidad del log, la plataforma, la sesión, el identificador de turno, el usuario cuando
existe, el modo, la pregunta, las llamadas a Cited con sus argumentos y el SHA-256 **y el texto** de cada
extracto devuelto, las fuentes, la respuesta final y el resultado del verificador, más `prev_hash` y
`hash`. La cadena es `hash = sha256(prev_hash + canonical_json(entry))`.

El append toma un lock exclusivo entre procesos sobre `<log>.lock` mientras lee y valida el final de la
cadena, calcula el hash, agrega y hace flush a disco. Un log cuyo final es inválido rechaza el append en
lugar de arrancar una cadena nueva. El esquema se valida antes de calcular el hash y otra vez al verificar.

Después de cada append el plugin reescribe un checkpoint autenticado con HMAC (`<log>.checkpoint`) con el
conteo de entradas, el hash final y la identidad del log. Su llave vive **fuera de `HERMES_HOME`**, por
omisión en `%APPDATA%\Katalis\hermes-cited\audit.key`, y nunca es el bearer de Cited. El verificador exige
el checkpoint:

- una entrada alterada, quitada o reordenada rompe la cadena;
- una entrada quitada del final, o un sufijo cortado, puede dejar la cadena internamente consistente, pero
  ya no coincide con el checkpoint;
- una cadena reescrita y con todos los hashes recalculados sin la llave no autentica;
- un checkpoint regresado a uno viejo mientras el log conserva sus entradas ya no coincide en conteo ni en
  hash final;
- un checkpoint ausente es un error, no un pase.

**Alcance exacto de la custodia:** se detecta un cambio de quien no tenga la llave. Si el log y su
checkpoint se regresan juntos por alguien con escritura en ambos, solo la custodia remota puede notarlo: eso
llega con Cited Ledger. La llave prueba autenticidad, no inmutabilidad remota.

Verifícala desde el plugin instalado, que es donde el módulo es importable:

```powershell
Push-Location (Join-Path $env:HERMES_HOME 'plugins/hermes-cited')
try {
    python -m hermes_cited.verify_log (Join-Path $env:HERMES_HOME 'cited/audit.jsonl')
} finally {
    Pop-Location
}
# OK: 4 entries, the chain and its checkpoint verify.   (salida 0)
# BROKEN: the log does not match its checkpoint: ...    (salida 1)
```

Usa explícitamente el Python de Hermes cuando `python` no sea ese intérprete. Correr el módulo desde otro
directorio falla con `ModuleNotFoundError: No module named 'hermes_cited'`: Hermes importa un plugin de
directorio como `hermes_plugins.<slug>` y nunca lo instala como paquete de nivel superior.

## La skill `cited`

El plugin incluye una skill `cited` y la registra con `ctx.register_skill`, así que aparece entre las skills
disponibles del agente mientras el plugin está habilitado. Dice cuándo usar cada herramienta, que la
respuesta y sus citas se transmiten sin cambiar un dato, que el modo cited exige copiar cada dato textual
entre `« »`, que una negativa de Cited se pasa tal cual y que en modo cited nada se completa con el
conocimiento del modelo. En la ruta solo-MCP existen las mismas dos herramientas, pero `/cited`, `/dot`, el
verificador y la bitácora no: no hay plugin que los corra.

## La ruta MCP, sin instalar nada

Cited también se alcanza como servidor MCP, sin plugin. Es la ruta para cualquier cliente MCP; en Hermes las
dos herramientas aparecen como `mcp__cited__cited_search` y `mcp__cited__cited_ask`. La skill es lo que hace
que el agente busque en Cited antes que en la web, así que copia
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
(`openspec/changes/hermes-plugin-r2/reports/`).

**El `%LOCALAPPDATA%\hermes` real no se escribió ni se usó como destino de ninguna corrida de esta ronda.**
La corrida aislada final y su puerta usan solo homes temporales. Una corrida histórica de la ronda 1,
al inicio de `mision-cited-hermes.md`, ejecutó `hermes mcp test cited` **sin** `HERMES_HOME` y leyó la
configuración real (una prueba de conexión de solo lectura contra el Cited vivo en el puerto 3240, que
falló). Ocurrió una vez, se conserva aquí en lugar de negarla y se reporta como RISK en
`tasks/entrega-cited-hermes-r2.md`. No se escribió ningún byte bajo el home real y ninguna corrida de la
ronda 2 tocó el puerto 3240.

| Qué | Resultado |
|---|---|
| La suite unitaria (`pytest`) | verde: el cliente y su rechazo de redirecciones, las dos herramientas, el verificador extractivo, la cadena con su checkpoint y su lock entre procesos, los modos, la política de entrega y la skill empaquetada, más un caso adversarial por hallazgo de la revisión |
| `hermes mcp test cited` | conectó, `Tools discovered: 2` (`cited_search`, `cited_ask`) |
| `hermes plugins install "file:///…" --enable --yes-deps` | instalado en `$HERMES_HOME/plugins/hermes-cited` y habilitado |
| El loader real | el plugin instalado carga con el gestor de plugins de Hermes y registra sus tres hooks |
| La pregunta de precio en la ruta MCP | el stream llama a `mcp__cited__cited_search` y responde **380 pesos** con la cita de `cafe-la-horquilla.md · Precios` |
| La pregunta de precio en modo cited | el stream llama a la `cited_search` nativa, ninguna otra herramienta antes, responde el valor con su cita, y el registro final `result` termina con `Verified by Cited` y sus fuentes |
| "Is there a guarantee on repairs at the bike workshop?" | responde **90 days** desde `bike-workshop-policies.md · Guarantee`, sellado |
| Una pregunta que los samples no responden | se niega sin dar ningún dato |
| La bitácora de esos turnos | una entrada por turno, conteo exacto, `python -m hermes_cited.verify_log` desde el plugin instalado dice `OK` y sale 0; quitar una entrada, cortar un sufijo, reescribir y recalcular, o regresar el checkpoint la hacen salir 1 |
| Modo dot | la respuesta queda intacta, sin sello, y la entrada se registra con el verificador marcado como no aplicado |
| La ruta del verificador | casos adversariales prueban que un valor reformulado, un sujeto intercambiado, un dato en texto libre y un eco de la consulta se rechazan |
| La política de entrega | con `streaming.enabled: true`, una respuesta cited en `telegram` retiene el sello y lo dice; con streaming apagado se sella |
| La skill `cited` | registrada por el plugin y presente en el árbol instalado, con la regla de cita textual y la nota de que los comandos son del plugin |

No se probó en esta ronda: un bot real de Telegram/Slack/Discord (la política de entrega se prueba en
proceso contra el mismo resolutor de configuración), una TUI interactiva, macOS o Linux, ni la instalación
contra la URL pública de GitHub.

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
- La llave del checkpoint se crea en el primer uso, vive fuera de `HERMES_HOME` y nunca es el bearer de
  Cited.

## Licencia

Apache-2.0. Ver `LICENSE` y `NOTICE`. Versión en inglés: [README.md](README.md).
