# hermes-cited

Cited en [Hermes Agent](https://github.com/NousResearch/hermes-agent): un plugin nativo de Python que le da
a Hermes las herramientas de solo lectura de [Cited](https://github.com/RonnieGex/cited) como herramientas
nativas, dos modos de conversación y un modo cited cuya respuesta **la escribe el plugin** a partir de los
renglones exactos que eligió el modelo, junto a un registro local de consistencia encadenado por hash de la
composición del plugin.

Hecho por Katalis. Apache-2.0.

- **Modo dot** (el default): respuestas normales; Cited se usa cuando ayuda. Nada en modo dot está
  verificado, diga lo que diga el texto: esta versión del plugin no escribe ningún sello, así que la frase
  `Verified by Cited` en una respuesta nunca viene del plugin, y el texto del modelo se entrega intacto.
- **Modo cited**: el modelo solo *elige*. Busca en Cited y luego llama a `cited_quote` con el identificador
  del pasaje y los renglones numerados que el usuario debe leer. El plugin descarta la prosa del modelo por
  completo y compone esos renglones **byte por byte**, cada uno con su documento, su sección y su marca
  `[n]`. El sello `Verified by Cited` se retiene — no se emite — mientras el host no exponga un contrato de
  entrega acreditable, y la respuesta lleva la nota fija que lo dice (D11). Cuando no hay nada que elegir, la
  respuesta es la negativa fija `No está en los documentos.`

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
| `CITED_URL` | sí | El origen de la instalación, como `https://cited.example.com`. Full llama a `<CITED_URL>/api/mcp`; search llama a `<CITED_URL>/api/chassis/mcp` y exige un origen sin ruta. |
| `CITED_BRIDGE_TOOLS` | no | `full` o `search`. `full` cuando falta o está vacía. Cualquier otro valor rechaza el registro. |
| `CITED_MCP_TOKEN` | en `full` | El bearer de la superficie MCP. Viaja solo en el encabezado `Authorization` de una petición a `<CITED_URL>/api/mcp`, y en modo `search` nunca se lee. |
| `CITED_SEARCH_TOKEN` | en `search` | El bearer de solo búsqueda. Viaja solo a `<CITED_URL>/api/chassis/mcp`. |
| `CITED_TIMEOUT_MS` | no | Cuánto puede tardar una llamada a Cited, en milisegundos. `30000` por omisión; search acepta un entero de 1 a 120000. |
| `CITED_DEFAULT_MODE` | no | El modo con el que arranca una conversación, `dot` o `cited`. `dot` por omisión. |
| `CITED_LANGUAGE` | no | El idioma del render de cited, `es` o `en`. `es` por omisión. Los renglones citados siempre son los bytes del documento. |

Sin `CITED_URL` o sin el token del modo elegido las herramientas responden una oración que nombra la
variable faltante. Nunca lanzan una excepción hacia Hermes y Hermes sigue funcionando.

## El interruptor de modo: `full` y `search`

`CITED_BRIDGE_TOOLS` elige la superficie que registra el plugin. Es un interruptor **cerrado**: ausente o
vacía elige `full`, el valor `search` elige el puente de solo búsqueda, y cualquier otro valor rechaza el
registro antes de instalar un solo callback. El modo es inmutable para ese registro.

| Valor | Superficie registrada | Endpoint | Bearer |
|---|---|---|---|
| `full` (omisión) | `cited_search`, `cited_ask`, `cited_quote`, los comandos `/cited` y `/dot`, los tres hooks y la skill `cited` | `POST <CITED_URL>/api/mcp` | `CITED_MCP_TOKEN` |
| `search` | exactamente una herramienta, `cited_search`, y ningún comando, hook, skill ni escritor de auditoría | `POST <CITED_URL>/api/chassis/mcp` | `CITED_SEARCH_TOKEN` |

En modo `search` el plugin lee la configuración del perfil activo de Hermes a través de
`agent.secret_scope`, exige el mapeo y el home de ese perfil en el registro y en cada llamada, y toma el
valor por omisión documentado cuando falta una clave: nunca cae al entorno del proceso. Un scope ausente,
con home cambiado o ilegible responde una oración redactada y no envía ninguna petición, y el modo de un
registro no cambia sin volver a registrar ese perfil. La ruta de búsqueda nunca pide `CITED_MCP_TOKEN`, ni
siquiera para comprobarlo o redactarlo.

El mismo límite aplica a `full`: cada callback registrado y su estado de turno pertenecen al perfil que los
registró, y el modo por omisión, el idioma, el token seleccionado y la ruta de auditoría de un turno vienen de
ese perfil, nunca de la raíz del proceso. Una llamada en otro home o con un modo cambiado se rechaza antes de
cualquier efecto, así que ninguna evidencia, modo o bitácora de un perfil se sirve desde otro. Los turnos vivos
se indexan por el home de ese perfil junto con los identificadores de sesión y de turno, así que dos perfiles
que reciben los mismos identificadores conservan dos turnos independientes y un callback ajeno rechazado no
limpia nada. El modo persistido de la conversación usa la clave plana `mode.profile` del propio host, que el
host particiona por home del perfil, de modo que un modo escrito por una versión anterior se honra sin
migración. Un diagnóstico de fallo se redacta con el secreto del perfil cuyo callback falló, nunca con el del
entorno raíz.

### El wire de búsqueda, versión 1

La herramienta de búsqueda habla el wire v1 cerrado de
`openspec/changes/search-only-bridge/wire-contract.md`: solo `POST /api/chassis/mcp` con
`Content-Type: application/json` y `Authorization: Bearer <CITED_SEARCH_TOKEN>`, cuerpo máximo de 16 KiB,
`tools/list` y `tools/call` autenticados. `CITED_URL` debe ser un origen http/https explícito, sin userinfo,
sin ruta (ni una barra final), sin query y sin fragmento. Todo 3xx se rechaza sin una segunda petición, así
que el bearer nunca viaja a otro destino. El `id` de la respuesta debe coincidir con el de la petición, los
pasajes deben cumplir el esquema fijado (`n` secuencial, `document`, `heading`, `position`, `excerpt`) y el
bloque de contenido debe recomponerse a partir de ellos; cualquier otra cosa es una oración redactada, nunca
un cuerpo crudo, una excepción, un encabezado ni una credencial. La herramienta devuelve la **cadena** JSON
`{"cited_tool":"cited_search","query":…,"text":…,"passages":[… con lines …]}`, nunca el sobre RPC ni un `pid`.

El modo search **no escribe nada** bajo `HERMES_HOME`: ninguna entrada de auditoría, ningún archivo de
bloqueo, ninguna caché. Una prueba aislada toma el inventario ordenado y el SHA-256 de cada archivo regular
del home antes del registro y después de una llamada exitosa y de una llamada fallida, y ambos inventarios
son idénticos.

### Instalar el puente fijado en un perfil

En el pin de Hermes `dce1e9b37581dd62e480a9064dc04a709c2940d3` el comando por perfil es:

```bash
env HERMES_HOME=<root> <chassis>/.venv/bin/hermes --profile <name> \
  plugins install file://<release>/hermes-cited.git --ref <full-sha> --enable --yes-deps
```

El perfil ya existe en `<root>/profiles/<name>`, y `--profile default` elige la raíz. Una instalación
pública nombra la URL del repositorio y pasa el commit en un `--ref` aparte, nunca como `repo@sha`, y el
espejo local es de solo lectura para el chasis. El artefacto de release son exactamente los bytes de
`git archive --format=tar <sha-de-fusión-archivada>` sin prefijo ni gzip; en Windows captura los bytes con
la opción binaria `--output` de Git, no con una redirección de texto. El lock registra el SHA completo, el
SHA-256 y el tamaño en bytes, y se escribe en un commit consumidor posterior, nunca con un hash
autorreferente.

El instalador Linux desechable aprovisiona los runtimes administrados que `plugins install` del host fijado
necesita (ese pin: CPython `3.14.7+20260901` y uv `0.12.3`, con su SHA-256 registrado) **antes** de cerrar la
red. Durante la corrida la red permanece cerrada, un intento de descarga falla la prueba en lugar de omitirla,
y el inventario completo del home del perfil tras el setup se compara con su línea base, no solo la ausencia
de `cited/`.

## Las tres herramientas nativas

| Herramienta | Entrada | Salida |
|---|---|---|
| `cited_search` | `query` (obligatoria), `limit` (1 a 8, 5 por omisión) | Los pasajes que coinciden, cada uno con `pid`, `n`, `document`, `heading`, `position`, `excerpt` y sus `lines` numerados. |
| `cited_ask` | `question` (obligatoria), `sessionId` (opcional) | `status` (`answered` o `refused`), `answer` y las `citations` numeradas, cada una con `pid` y sus `lines` numerados. |
| `cited_quote` | `passage` (el `pid` de un pasaje o cita de este turno, como `P1`, o su número `n` mientras ese número no sea ambiguo), `lines` (sus números de renglón, en orden) | El texto exacto de esos renglones, y el plugin registra la elección para la respuesta. |

`cited_search` y `cited_ask` son las dos herramientas que llaman a `POST <CITED_URL>/api/mcp` con el método
JSON-RPC `tools/call` y `Authorization: Bearer <CITED_MCP_TOKEN>`; la red, el token y el proceso de Cited
viven solo ahí. `cited_quote` es una selección local del plugin: no hace ninguna petición HTTP y nunca sale
de los extractos de su propio turno. Las tres son nativas y no una configuración MCP porque así la
instalación es un paso y porque el plugin necesita ver cada resultado para componer la respuesta y escribir
el registro.

## Un identificador por pasaje

Cada pasaje y cada cita que devuelve una herramienta de cited en un turno recibe su propio identificador
`pid`: `P1`, `P2`, y así en el orden en que los devolvieron las llamadas. `cited_quote` toma ese `pid`, no
el número `n`, porque dos búsquedas del mismo turno pueden devolver las dos un pasaje 1 y entonces los
números chocan. El turno guarda el mapeo del `pid` a la llamada, al `n` original del resultado de Cited, al
documento, a la sección y a la posición. La marca `[n]` del render, la elección del modelo y el renglón del
registro son la misma referencia. Un `passage` numérico se acepta solo mientras identifique exactamente un
pasaje del turno; cuando es ambiguo, la elección se rechaza y el error pide el `pid`. Un bloque elegido o un
metadato que traiga la frase `Verified by Cited` es dato como cualquier otro: esta versión no escribe ningún
sello, así que la frase nunca viene del plugin (D12).

## Los dos modos

- `/cited` enciende el modo cited para esta conversación; `/dot` lo apaga. La clave es la sesión cuando la
  superficie expone una y el perfil cuando no. `CITED_DEFAULT_MODE` fija el modo inicial. La confirmación de
  `/cited` declara el alcance de la promesa: el **mensaje final** que compone el plugin, no los borradores que
  una superficie pueda mostrar mientras se escribe la respuesta ni los avisos que el host agregue después.
  También declara la condición del sello: **la marca no se emite hoy**, porque el host no expone un contrato
  de entrega acreditable (D11), así que la respuesta lleva la nota fija que dice que el sello se retiene. La
  confirmación de `/dot` dice que nada en modo dot está verificado, diga lo que diga el texto: esta versión
  no escribe ningún sello, así que la frase nunca viene del plugin, y el texto del modelo se entrega
  intacto.
- En modo cited, `pre_llm_call` inyecta las reglas: llama primero a Cited, elige los renglones con
  `cited_quote` y no escribas la respuesta. El texto del modelo se descarta por completo. Un render real,
  de `cited_quote` con `{"passage": "P1", "lines": [4]}` contra `cafe-la-horquilla.md · Precios`, es:

  ```
  Según tus documentos:

  - Afinacion de bicicleta: 380 pesos. [1]
  Fuente: cafe-la-horquilla.md - Precios

  Note on delivery: the host does not expose a per-turn delivery policy that accredits the effective
  receivers and the guarantee that the terminal message is the plugin's composition, so the plugin cannot
  prove what was delivered. The verified seal is withheld here because something else may have been visible
  before this answer was verified. The text above is still copied from the documents of this turn.
  ```

  Con `CITED_LANGUAGE=en` la plantilla de entrada es `From your documents:` y la negativa
  `It is not in the documents.`; los renglones citados nunca cambian de idioma.

- Cada pasaje o cita se parte en renglones de forma determinista (por salto de línea; un párrafo sin saltos
  es un renglón) y se numera desde 1. Cada bloque mostrado es *idéntico* a un renglón completo de un extracto
  del turno: no hay normalización Unicode, ni subcadenas, ni listas de palabras, porque el plugin escribió el
  bloque desde el extracto mismo. Un valor, un sujeto o un sello que escriba el modelo nunca llegan a la
  respuesta.
- Cuando no hay nada que mostrar, es decir, el modelo no llamó a `cited_quote`, hay un `status: refused` en
  cualquier punto del turno, o el turno no tuvo extractos, la respuesta es la negativa fija
  `No está en los documentos.` (en inglés, `It is not in the documents.`). Nunca lleva el sello.
- El sello `Verified by Cited` solo lo agregaría el plugin, solo después de persistir el texto exacto que se
  entrega y solo si la política de entrega lo permite **y** el host acredita la entrega del turno (D11).
  Mientras el host no lo haga, la marca no se emite en ninguna ruta y la respuesta lo dice con la nota fija.
  La marca `[1]` y la fuente las genera el plugin; el modelo no escribe ninguna.
- El modo dot entrega el texto del modelo **intacto**. Nada en modo dot está verificado, diga lo que diga el
  texto: esta versión del plugin no escribe ningún sello, así que la frase `Verified by Cited` en una
  respuesta dot nunca viene del plugin (D12). Un turno dot que traiga la frase es un texto que escribió el
  modelo, y la fila registra exactamente el texto que se entrega.
- Los totales y otros valores calculados quedan fuera de esta ronda: pertenecen a la misión de documentos,
  donde una herramienta los calcula por código y registra la procedencia.

## Entrega: una instantánea al inicio del turno

Hermes v0.21.6+387 entrega cada delta de texto a la pantalla, a la plataforma de mensajería, al comentario
intermedio y al TTS de streaming **antes** de que `transform_llm_output` decida. Ningún hook de plugin puede
retener esos deltas: es una limitación del host, y este plugin la declara en lugar de esconderla. Para un turno
cited que llega al hook, la composición del plugin es el render documental, la negativa fija o la negativa
operativa; el host puede agregar texto después. No es una promesa sobre lo que un borrador pudo mostrar en
pantalla mientras se escribía la respuesta.

El plugin decide el sello a partir de una **instantánea tomada al inicio del turno cited** y la congela en
el turno, así que un cambio de configuración durante el turno no puede cambiar una decisión ya tomada. La
instantánea resuelve el streaming efectivo con la clase real del host, `gateway.config.StreamingConfig`, así
que `mode`, `enabled`, `transport` y el override por plataforma significan lo que Hermes significa con
ellos, y cubre cada superficie del host que entrega texto o voz:

| Superficie | El sello |
|---|---|
| Toda superficie | **Retenido.** El host de esta versión no expone ninguna política por turno de los receptores efectivos ni garantía de que el mensaje terminal sea la composición del plugin, así que el punto único de capacidad (`delivery.accredited_delivery()`) responde "no acreditado" y la marca no se emite (D11). Una versión futura del host que ofrezca ambas mitades vuelve a encender el sello, y solo una prueba del host real lo demuestra. |
| `api_server` (la ruta SSE de la app de escritorio) | La superficie legible nunca queda limpia: esa superficie arma su propio stream, que ninguna configuración de aquí alcanza. |
| `desktop` | La superficie legible nunca queda limpia, por la misma razón: la app cablea su propio stream SSE. |
| Plataforma de mensajería (Telegram, Slack, Discord, WeCom, Feishu, DingTalk, QQ y similares) | La superficie legible no queda limpia cuando el `streaming` efectivo está encendido para esa plataforma. |
| Comentario intermedio del asistente (`display.interim_assistant_messages`) | No queda limpia cuando los mensajes intermedios están encendidos para la plataforma del turno. |
| TTS de streaming (`tts.auto_tts`) | No queda limpia cuando `tts.auto_tts` está encendido: la voz es una entrega que el turno no puede recuperar. |
| Una plataforma que el plugin no puede resolver | No queda limpia: no puede probar que nada más haya sido visible. |
| Una configuración que no se puede leer, o un `FailedConfigRead` | No queda limpia, por la misma razón. |
| CLI | No queda limpia con `display.streaming: true` o con el comentario intermedio encendido. Con ambos apagados la superficie legible queda limpia, y el sello igual se retiene porque el host no está acreditado. `--format stream-json` igual emite eventos `text`, así que **quien consuma ese formato debe mostrar solo el registro terminal `result`**; un consumidor que concatene `text`, razonamiento o comentarios vería el borrador. |

Una superficie de solo entrada (`local`, un webhook) nunca entrega un borrador a un usuario, así que su
superficie legible queda limpia salvo que aplique otra razón. Cuando el sello se retiene, la respuesta lleva
una nota fija que nombra la superficie y qué apagar, o la acreditación que falta.

La configuración exacta del gateway:

```yaml
streaming:
  enabled: false                 # interruptor maestro; `transport: off` también apaga
display:
  streaming: false               # solo del CLI
  interim_assistant_messages: false
  platforms:
    telegram:
      streaming: false           # solo estrecha; nunca enciende streaming por sí sola
      interim_assistant_messages: false
tts:
  auto_tts: false
```

`display.streaming` es solo del CLI; el gateway resuelve primero
`display.platforms.<plataforma>.streaming`. El plugin otorgaría el sello solo cuando la instantánea muestre de
forma afirmativa que nada más pudo haber sido visible **y** el host acredite la entrega del turno; mientras
el host no lo haga, la marca se retiene en toda ruta. `docs/upstream-proposal.md` (inglés) especifica las dos
mitades de ese contrato: el hook de política de entrega por turno y la frontera de composición terminal, con
archivo y línea de cada punto que toca. No se abrió ningún pull request ni issue aguas arriba.

## El registro de consistencia

Cada composición del plugin cuyo append tiene éxito agrega un renglón, un objeto JSON, a
`$HERMES_HOME/cited/audit.jsonl`, en ambos
modos: la marca UTC, un `seq` monotónico, la identidad del log, la plataforma, la sesión, el identificador
de turno, el usuario cuando existe, el modo, la pregunta, las llamadas a Cited con sus argumentos y el
SHA-256 **y el texto** de cada extracto devuelto, el `pid` y el número original de cada renglón elegido con
su documento, su sección y su posición, el texto compuesto, la transcripción que el plugin habría devuelto
sin el sello, la instantánea de entrega con su decisión, el resultado del verificador y la
`composition_note` fija que dice qué es la fila, más `prev_hash` y `hash`. La cadena es
`hash = sha256(prev_hash + canonical_json(entry sin hash))`. Una negativa por fallo de persistencia no escribe
ningún renglón, así que el registro es la composición del plugin cuando el append tiene éxito y nunca una
afirmación sobre el mensaje terminal.

**La fila registra la composición del plugin.** El host puede mostrar borradores mientras se genera la
respuesta y agregar avisos propios al final (el pie de mutaciones, una explicación de salida anormal), así que
la fila **no** es constancia del mensaje terminal. La `composition_note` dice exactamente eso dentro de la
entrada.

El append toma un lock exclusivo entre procesos sobre `<log>.lock` y, **antes de escribir un byte**, lee
toda la cadena y valida cada esquema, `seq`, enlace y hash. Cualquier discrepancia rechaza el append y deja
el archivo intacto: un append nunca reinicia la cadena desde génesis. Cuando el append falla, la respuesta
cited es la negativa operativa fija sin sello, porque una respuesta rechazada no es una respuesta
entregada.

El registro sirve para revisar y reproducir cada respuesta. **No** es a prueba de manipulación frente a
quien controla la PC: alguien que reescribe el archivo y recalcula la cadena, o que corta un sufijo completo,
produce un archivo que queda con consistencia interna. Ese es el alcance exacto de su `consistencia
interna`, y es lo que revisa el verificador. Para el registro no se escribe ni se lee ninguna llave ni
ningún archivo fuera de `HERMES_HOME`. La auditoría con custodia es una propiedad del lado del servidor, y
llega con Cited Ledger.

Verifícalo desde el plugin instalado, que es donde el módulo es importable:

```powershell
Push-Location (Join-Path $env:HERMES_HOME 'plugins/hermes-cited')
try {
    python -m hermes_cited.verify_log (Join-Path $env:HERMES_HOME 'cited/audit.jsonl')
} finally {
    Pop-Location
}
# OK: 4 entries, the chain is internally consistent (this is not a custody check; see the README).  (salida 0)
# BROKEN: entry 3 was altered: its hash does not match its content.                                 (salida 1)
```

Usa explícitamente el Python de Hermes cuando `python` no sea ese intérprete. Correr el módulo desde otro
directorio falla con `ModuleNotFoundError: No module named 'hermes_cited'`: Hermes importa un plugin de
directorio como `hermes_plugins.<slug>` y nunca lo instala como paquete de nivel superior.

## La frontera de un turno cited

Para un turno cited que llega al hook, la composición del plugin es el render documental, la negativa fija o la
negativa operativa; el host puede agregar texto después. Las tres composiciones posibles son:

1. el render de los renglones textuales que eligió el modelo, con la marca y la fuente, y la nota fija que
   dice que el sello se retiene: la marca misma no se emite mientras el host no acredite la entrega;
2. la negativa fija localizada `No está en los documentos.` (en inglés, `It is not in the documents.`),
   cuando no hay nada que mostrar, cuando Cited se negó, o cuando ningún bloque elegido pasa la revisión por
   construcción;
3. la negativa operativa fija localizada con un código de incidente, sin sello y sin interpolar ningún
   detalle del error.

El host todavía puede agregar su propio texto después del hook, como el footer de las mutaciones de archivo
que fallaron (`agent/turn_finalizer.py:645-647`); donde lo hace, el mensaje terminal puede diferir de esa
composición y el plugin no reclama esta frontera para esas rutas. El tercer contrato de
`docs/upstream-proposal.md` pide la frontera de composición que cerraría ese hueco.

Una sola frontera alrededor de todo el transformador convierte cualquier excepción de leer la configuración,
resolver, renderizar, componer o persistir en la tercera respuesta. El código de incidente se genera sin
lanzar nunca: si la dependencia de entropía falla, se usa un código de reserva constante, así que la salida de
emergencia no depende de entropía, disco, configuración ni logger. El diagnóstico se redacta del bearer y
va solo al logger y a `stderr`, nunca a la respuesta. El estado del turno se suelta en un `finally`, así que
la falla de un turno no puede filtrarse al siguiente. El modo dot conserva su propio contrato y nunca
responde con una negativa, porque en modo dot el plugin nunca prometió el texto: tampoco lo reescribe, así
que una falla de su paso directo devuelve `None` y deja el texto en su lugar.

## Incompatibilidades del host

- **Una respuesta vacía del modelo nunca llega al hook.** `agent/turn_finalizer.py:501` del host fijado
  regresa antes de invocar `transform_llm_output` cuando el texto del modelo es falso. Un turno cited cuya
  respuesta del modelo es vacía se entrega vacío: el plugin no compone nada y el registro no recibe ningún
  renglón para ese turno, porque nada se compuso y nada entregó el plugin. El plugin no presenta eso como
  cubierto.
- **El host puede entregar un borrador antes del veredicto.** Los deltas de las superficies de arriba
  llegan al usuario antes de que corra `transform_llm_output`, y ningún hook de plugin puede retenerlos. El
  plugin no puede ver los receptores efectivos del turno, así que retiene la marca en toda ruta.
- **El host puede agregar texto después del veredicto.** El finalizador real aplica `transform_llm_output`,
  persiste el renglón y solo después agrega su propio texto, como el footer de las mutaciones de archivo que
  fallaron (`agent/turn_finalizer.py:645-647`). El mensaje final puede entonces diferir del render que
  compuso el plugin y del renglón que guardó el registro. El plugin no reclama el render de C1 para una ruta
  del host que pueda agregar texto.

El contrato que este plugin le pide a Hermes son tres contratos: la **retención síncrona de la entrega** — una
política de entrega resuelta una vez por turno que retenga texto, razonamiento, comentario intermedio, voz y la
ruta SSE hasta el veredicto —, **un paso final de composición incluso cuando el texto del modelo es vacío**,
ejecutado una vez por turno cited antes de persistir y entregar, y **una frontera de composición después de los
footers del host**, para que la composición del plugin corra después de todos los footers o explicaciones que
agregue el host y antes de la entrega terminal y el mensaje entregado sea el texto que guarda el registro.
`docs/upstream-proposal.md` trae el archivo y la línea de cada punto que cambiaría.

## La skill `cited`

El plugin incluye una skill `cited` y la registra con `ctx.register_skill`, así que aparece entre las skills
disponibles del agente mientras el plugin está habilitado. Dice cuándo usar cada herramienta, que el plugin
escribe la respuesta cited y que el modelo solo elige renglones con `cited_quote`, que una negativa de Cited
se pasa tal cual y que en modo cited nada se completa con el conocimiento del modelo. En la ruta solo-MCP
existen las dos herramientas de búsqueda, pero `/cited`, `/dot`, `cited_quote`, el render y el registro no:
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
afirma las propiedades e imprime `GATE: GREEN`; su salida y las transcripciones están dentro de los cambios
(`openspec/changes/archive/2026-10-10-hermes-plugin-r3/reports/` y `openspec/changes/archive/2026-10-10-hermes-plugin-r4/reports/`).

La ronda 4 (2026-10-10) retiró la custodia local del registro, así que lo que queda es el registro de
consistencia encadenado que se describe arriba, sin llave y sin ningún archivo fuera de `HERMES_HOME`.
También tomó la decisión de entrega con una instantánea al inicio del turno, agregó `api_server`, el
comentario intermedio y el TTS de streaming a las superficies que retienen el sello, le dio a cada pasaje su
`pid` y puso una sola frontera alrededor de todo el transformador cited.

La ronda 8 (2026-10-10, D12) retiró la protección de la marca reservada. Con D11 el plugin no emite sello en
ninguna ruta, así que no existe un sello auténtico que alguien pueda falsificar, y cada lector escrito a mano
del Markdown del host abría una evasión nueva o borraba texto legítimo. El modo dot ahora entrega el texto
del modelo intacto y registra exactamente esa cadena, un renglón documental que traiga la frase es dato como
cualquier otro, y la documentación dice en llano que nada en modo dot está verificado. La activación del
sello, cuando el host ofrezca un contrato de entrega acreditable, exige volver a proteger la marca reservada
con la semántica de render del host, comprobada contra su consumidor (`docs/upstream-proposal.md`).

**El `%LOCALAPPDATA%\hermes` real no se escribió ni se usó como destino de ninguna corrida de esta ronda.**
La corrida aislada final y su puerta usan solo homes temporales. Una corrida histórica de la ronda 1,
al inicio de `mision-cited-hermes.md`, ejecutó `hermes mcp test cited` **sin** `HERMES_HOME` y leyó la
configuración real (una prueba de conexión de solo lectura contra el Cited vivo en el puerto 3240, que
falló). Ocurrió una vez, se conserva aquí en lugar de negarla y se reporta como RISK en
`tasks/entrega-cited-hermes-r2.md`. No se escribió ningún byte bajo el home real y ninguna corrida de la
ronda 2 ni de la ronda 3 tocó el puerto 3240.

| Qué | Resultado |
|---|---|
| La suite unitaria (`pytest`) | verde: el cliente y su rechazo de redirecciones, las tres herramientas y el `pid` por turno, el verificador por construcción, el render escrito por el plugin, el registro de consistencia encadenado y su lock entre procesos, la frontera con sus tres respuestas posibles, la instantánea de entrega de cada superficie, los modos y la skill empaquetada, más un caso adversarial por hallazgo de las revisiones |
| `hermes mcp test cited` | conectó, `Tools discovered: 2` (`cited_search`, `cited_ask`) |
| `hermes plugins install "file:///…" --enable --yes-deps` | instalado en `$HERMES_HOME/plugins/hermes-cited` y habilitado |
| `hermes plugins install RonnieGex/hermes-cited --enable`, desde GitHub | clonado en `eb02713` y habilitado; en modo cited la pregunta de precio llamó a `cited_search` y luego a `cited_quote` y entregó el render del renglón con `Fuente: cafe-la-horquilla.md - Precios` y `[1]`, como muestra la [evidencia](docs/evidence/github-install-2026-10-10.md) |
| El loader real | el plugin instalado carga con el gestor de plugins de Hermes y registra sus tres hooks |
| La pregunta de precio en la ruta MCP | el stream llama a `mcp__cited__cited_search` y responde **380 pesos** con la cita de `cafe-la-horquilla.md · Precios` |
| La pregunta de precio en modo cited | el stream llama a la `cited_search` nativa y luego a `cited_quote`; la respuesta entregada es el render del plugin, con `Fuente: cafe-la-horquilla.md - Precios` y la marca `[1]`, y el sello retenido porque el host no acredita la entrega, como muestra la [transcripción](openspec/changes/archive/2026-10-10-hermes-plugin-r4/reports/2026-10-10-step-5-e2e.md) |
| `What guarantee on repairs does bike-workshop-policies.md state?` | el render lleva **90 days** desde `bike-workshop-policies.md · Guarantee`, con el sello retenido en la misma [transcripción](openspec/changes/archive/2026-10-10-hermes-plugin-r4/reports/2026-10-10-step-5-e2e.md) |
| Una pregunta que los samples no responden | exactamente `No está en los documentos.`, sin dato y sin sello |
| El registro de consistencia de esos turnos | una entrada por turno con el conteo exacto; `python -m hermes_cited.verify_log` desde el plugin instalado reporta la consistencia interna de la cadena y sale 0; alterar una entrada, quitar una de en medio, reordenarla o introducir un hueco lo hace salir 1, mientras que un corte de sufijo completo o un archivo reescrito con todos los hashes recalculados queda con consistencia interna, que es el límite documentado de la revisión |
| Modo dot | el texto del modelo se entrega intacto y la entrada se registra con el verificador marcado como no aplicado; la fila registra exactamente el texto que se entrega, y un renglón documental que traiga la frase `Verified by Cited` es dato, porque esta versión no escribe ningún sello (D12) |
| El contrato cited | en modo cited, casos adversariales prueban que un valor cambiado, un sujeto movido, una subcadena, la prosa libre y un sello falsificado nunca llegan a la respuesta entregada; el modo dot entrega el texto del modelo tal cual (D12) |
| La frontera | una falla al leer la configuración, resolver, renderizar o persistir entrega la negativa operativa fija con un código de incidente, incluso cuando falla la dependencia de entropía de ese código, que entonces usa el código de reserva constante, y la composición del plugin de un turno cited es una de las tres |
| La política de entrega (fixtures, aparte de la corrida de arriba) | `api_server`, `desktop`, una plataforma desconocida y una configuración ilegible marcan la superficie legible como no limpia; también lo hacen `streaming` encendido para una plataforma de mensajería, `interim_assistant_messages` encendido y `tts.auto_tts` encendido; en un fixture sintético de CLI quieto la superficie legible queda limpia y el sello igual se retiene porque el host no está acreditado, y un cambio de la configuración después de que arrancó el turno no cambia su decisión |
| La respuesta vacía | el finalizador real regresa sin invocar el hook, y el plugin reporta eso como una incompatibilidad del host en lugar de cubrirla |
| La skill `cited` | registrada por el plugin y presente en el árbol instalado, con la regla de `cited_quote` y la nota de que los comandos son del plugin |

No se probó en esta ronda: un bot real de Telegram/Slack/Discord/WeCom (la política de entrega se prueba en
proceso y contra la clase real `StreamingConfig` del host), una TUI interactiva, macOS o Linux, ni la
instalación contra la URL pública de GitHub.

## Seguridad

- El token viaja solo en el encabezado `Authorization` de una petición a `CITED_URL`. Un `3xx` se rechaza
  antes de cualquier segunda petición, así que una redirección nunca puede llevar el bearer a otro origen.
- Antes de construir cualquier resultado visible, en éxito y en error, el cliente rechaza una respuesta que
  refleje el token en cualquier cadena; la respuesta se descarta y nada de ella se muestra ni se registra.
- Antes de calcular el hash y agregar, cada campo de la entrada del registro se redacta recursivamente,
  incluidos la pregunta, los argumentos, los extractos, la respuesta y los errores.
- `401`, `403`, `404`, `405`, un timeout y una falla de red se convierten cada uno en una oración distinta
  que el modelo puede leer. El plugin nunca escribe un secreto en un log, un resultado de herramienta, el
  archivo del registro ni la evidencia.
- El plugin es de solo lectura contra Cited: nunca escribe un documento y nunca llama a un modelo por su
  cuenta. Solo `cited_ask` puede guardar un turno, y solo cuando quien llama pasa un `sessionId`.
- El registro de consistencia es un archivo local solo para revisar y reproducir. No es custodia y no es a
  prueba de manipulación: quien controla la máquina puede reescribirlo y recalcular la cadena. Para él no se
  crea ni se lee ninguna llave, y no se escribe ningún archivo fuera de `HERMES_HOME`.

## Licencia

Apache-2.0. Ver `LICENSE` y `NOTICE`. Versión en inglés: [README.md](README.md).

<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/brand/katalis-flame-192.png"><img src="docs/brand/katalis-flame-ink-192.png" alt="Katalis" height="48"></picture> <a href="https://katalis.dev">Hecho por Katalis</a></p>
