# hermes-cited

Cited dentro de [Hermes Agent](https://github.com/NousResearch/hermes-agent): un plugin nativo de
Python que le da a Hermes las dos herramientas de solo lectura de
[Cited](https://github.com/RonnieGex/cited) como herramientas nativas, dos modos de conversación, un
verificador determinista de la respuesta final y una bitácora auditable encadenada por hash.

Built by Katalis. Apache-2.0.

- **Modo dot** (el inicial): respuestas normales; Cited se usa cuando ayuda.
- **Modo cited**: antes del turno se inyectan las reglas estrictas, y después un verificador
  determinista, sin IA, revisa cada número, unidad, precio y código de la respuesta contra los pasajes
  que Cited devolvió en ese mismo turno. La respuesta que pasa termina con `Verified by Cited` y sus
  fuentes; la que trae un valor que ningún pasaje contiene se reemplaza por una negativa que lo nombra.

## Requisitos

- Hermes Agent con la API de plugins nativos. Todo lo de aquí se verificó con la **v0.21.6+387
  (commit `dce1e9b`)**, Python 3.11.15 del venv de Hermes, en Windows.
- Un Cited cuyo `/api/mcp` acepte el encabezado `MCP-Protocol-Version` que Hermes manda desde
  `initialize`. Hermes manda `2025-11-25`; Cited necesita el arreglo de
  [RonnieGex/cited#21](https://github.com/RonnieGex/cited/pull/21) (rama
  `fix/mcp-initialize-version-header`). Sin él, la conexión falla con
  `the protocol version 2025-11-25 is not supported`.
- El `CITED_MCP_TOKEN` de esa instalación.

## Instalación en un paso

```bash
hermes plugins install RonnieGex/hermes-cited --enable
```

Desde un checkout local, que es lo que usa la puerta de este repositorio:

```bash
hermes plugins install "file:///C:/ruta/absoluta/a/hermes-cited" --enable --yes-deps
```

El comando clona el repositorio en `$HERMES_HOME/plugins/hermes-cited` y lo habilita. El plugin es
opt-in: queda apagado hasta que aparece en `plugins.enabled`.

## Configuración

Escribe estas dos variables en `$HERMES_HOME/.env` (el archivo que Hermes carga en el entorno del
proceso que corre el plugin):

| Variable | Obligatoria | Qué hace |
|---|---|---|
| `CITED_URL` | sí | La dirección de la instalación, como `https://cited.example.com`. El plugin llama a `<CITED_URL>/api/mcp`. Una URL que ya termina en `/api/mcp` se usa tal cual. |
| `CITED_MCP_TOKEN` | sí | El bearer token de esa instalación. Solo viaja en el encabezado `Authorization` de una petición a `CITED_URL`. |
| `CITED_TIMEOUT_MS` | no | Cuánto puede tardar una llamada a Cited, en milisegundos. 30000 por omisión. |
| `CITED_DEFAULT_MODE` | no | El modo con el que arranca una conversación, `dot` o `cited`. `dot` por omisión. |

Sin `CITED_URL` o sin `CITED_MCP_TOKEN`, las dos herramientas responden una frase que nombra la
variable que falta. Nunca lanzan una excepción dentro de Hermes y Hermes sigue funcionando.

## Las dos herramientas nativas

| Herramienta | Entrada | Salida |
|---|---|---|
| `cited_search` | `query` (obligatoria), `limit` (de 1 a 8, 5 por omisión) | Los pasajes que coinciden, cada uno con `n`, `document`, `heading`, `position` y `excerpt`, tal como los mandó Cited. |
| `cited_ask` | `question` (obligatoria), `sessionId` (opcional) | `status` (`answered` o `refused`), `answer` y las `citations` numeradas con sus extractos. |

Llaman a `POST <CITED_URL>/api/mcp` con el método JSON-RPC `tools/call` y
`Authorization: Bearer <CITED_MCP_TOKEN>`. Son nativas y no una configuración MCP porque así la
instalación queda en un paso y porque el plugin necesita ver cada resultado para verificar la
respuesta y escribir la bitácora.

## Los dos modos

- `/cited` prende el modo cited en esta conversación; `/dot` lo apaga. La clave es la sesión cuando la
  superficie la expone y el perfil cuando no. `CITED_DEFAULT_MODE` fija el modo inicial.
- En modo cited, `pre_llm_call` inyecta las reglas en el mensaje del usuario: llamar a Cited primero,
  responder solo con los pasajes de este turno, copiar cada valor exactamente, transmitir la negativa
  de Cited y nunca rellenar un hueco con la web ni con conocimiento propio.
- Al final del turno, `transform_llm_output` corre el verificador. Extrae números, unidades, precios y
  códigos del texto final y revisa cada uno contra lo que Cited devolvió en ese mismo turno, después
  de normalizar acentos, mayúsculas, separadores de miles y pares singular-plural en inglés y español.
  Nunca llama a un modelo y nunca lee la pregunta. Un turno en modo cited sin ningún resultado de
  Cited no puede pasar.
- La respuesta que pasa se conserva y termina con `Verified by Cited` y las fuentes que dio Cited. La
  que trae un valor que ningún pasaje contiene se reemplaza por una frase que nombra cada valor que no
  se pudo verificar. En modo dot no se reemplaza nada y el sello nunca aparece.

## La bitácora auditable

Cada respuesta agrega una entrada a `$HERMES_HOME/cited/audit.jsonl`, en los dos modos: la fecha UTC,
la plataforma, la sesión, el usuario cuando existe, el modo, la pregunta, las llamadas a herramientas
de Cited con sus argumentos, el SHA-256 de cada extracto devuelto, la respuesta final y el resultado
del verificador, más `prev_hash` y `hash`. La cadena es
`hash = sha256(prev_hash + canonical_json(entrada))`, así que una entrada alterada, quitada o
reordenada la rompe.

```bash
python -m hermes_cited.verify_log "$HERMES_HOME/cited/audit.jsonl"
# OK: 4 entries, the chain verifies.        (salida 0)
# BROKEN: entry 2 was altered: ...          (salida 1)
```

El token nunca se escribe en la bitácora, ni en un resultado de herramienta, ni en ningún archivo de
este repositorio.

## La skill `cited`

El plugin incluye una skill `cited` y la registra con `ctx.register_skill`, así que aparece entre las
skills disponibles del agente mientras el plugin está habilitado. Dice cuándo usar cada herramienta,
que la respuesta y sus citas se transmiten sin cambiar ningún dato, que la negativa de Cited se
transmite tal cual, y que en modo cited no se completa nada con conocimiento propio del modelo.

## La ruta MCP, sin instalar nada

A Cited también se llega como servidor MCP, sin ningún plugin. Es la ruta para cualquier cliente MCP;
en Hermes las dos herramientas aparecen como `mcp__cited__cited_search` y `mcp__cited__cited_ask`. La
skill es lo que hace que el agente busque en Cited antes que en la web, así que copia
`hermes_cited/skills/cited/SKILL.md` a `$HERMES_HOME/skills/cited/SKILL.md` también.

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

`${VAR}` se lee de `$HERMES_HOME/.env` o del entorno. Agrega `trust: untrusted` a esa entrada para
que las dos herramientas, que son de solo lectura, corran sin pedir aprobación. Verifícalo con
`hermes mcp test cited`, que debe conectar y listar las dos herramientas.

## Qué se probó (2026-10-09)

Todo lo de abajo se corrió el 2026-10-09 con Hermes Agent **v0.21.6+387 (`dce1e9b`)**, el modelo
DeepSeek (`--provider deepseek -m deepseek-flash`), un Cited compilado de la rama de
[RonnieGex/cited#21](https://github.com/RonnieGex/cited/pull/21) en `127.0.0.1:3246` con los cuatro
documentos de su `samples/`, y un `HERMES_HOME` temporal. El `%LOCALAPPDATA%\hermes` real nunca se
usó. No se afirma nada más.

| Qué | Resultado |
|---|---|
| La suite unitaria (`pytest`) | verde: el cliente contra un `/api/mcp` falso local, las dos herramientas, el verificador, la cadena, los modos, el registro y la skill empaquetada |
| `hermes mcp test cited` | conectó, `Tools discovered: 2` (`cited_search`, `cited_ask`) |
| `hermes plugins install "file:///…" --enable --yes-deps` | instalado en `$HERMES_HOME/plugins/hermes-cited` y habilitado |
| La pregunta del precio por la ruta MCP | el stream llama a `mcp__cited__cited_search` y responde **380 pesos** con la cita de `cafe-la-horquilla.md · Precios` |
| La pregunta del precio en modo cited | el stream llama a la `cited_search` nativa y a ninguna herramienta web, responde **380 pesos [1]** y el texto final termina con `Verified by Cited` y sus fuentes |
| "Is there a guarantee on repairs at the bike workshop?" | responde **90 days** de `bike-workshop-policies.md · Guarantee`, con sello |
| Una pregunta que las muestras no responden | se niega sin inventar un precio |
| La bitácora de esos turnos | una entrada por respuesta; `python -m hermes_cited.verify_log` dice `OK` y sale 0; alterar, quitar o reordenar una entrada lo hace salir 1 y nombrar la entrada |
| El modo dot | la respuesta queda intacta y sin sello, y la entrada se registra con el verificador marcado como no aplicado |
| El camino de la negativa | un caso unitario prueba que un número inventado se reemplaza por una negativa que lo nombra |
| La skill `cited` | registrada por el plugin y presente en el árbol instalado |

`scripts/gate.py`, corrido con el Python del venv de Hermes, afirma H0 a H8 e imprime
`GATE: GREEN`. Su salida y las transcripciones de las corridas de punta a punta están en `reports/`.

## Seguridad

- El token solo viaja en el encabezado `Authorization` de una petición a la `CITED_URL` configurada.
  Nunca se registra, nunca se devuelve en un resultado de herramienta, nunca se escribe en la bitácora
  y nunca se escribe en la evidencia.
- `401`, `403`, `404`, `405`, un tiempo agotado y una falla de red se convierten cada uno en una frase
  distinta que el modelo puede leer, y una respuesta de Cited que refleje el token se redacta antes de
  mostrarse.
- El plugin es de solo lectura contra Cited: nunca escribe un documento y nunca llama a un modelo de
  lenguaje por su cuenta. Solo `cited_ask` puede guardar un turno, y solo cuando quien llama pasa un
  `sessionId`.

## Licencia

Apache-2.0. Ver `LICENSE` y `NOTICE`. Versión en inglés: [README.md](README.md).
