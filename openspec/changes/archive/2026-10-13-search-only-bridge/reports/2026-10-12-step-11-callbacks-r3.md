# Ronda 3 — B01: cada callback de `full` y su estado pertenecen al perfil registrado

Fecha: 2026-10-12, America/Mexico_City. Agente: DeepSeek. Rama: `feature/search-only-bridge`.
Contrato: D2, H19, H20, H21. Origen: `tasks/revision-bridge-r2.md`, hallazgo B01 (Blocker).
Entorno: toda corrida usa un `HERMES_HOME` temporal y alcances explícitos; la instalación personal
`%LOCALAPPDATA%\hermes` y el checkout `hermes-agent` son de sólo lectura; nunca se usan 3240/3241.

## Lo medido antes

```
.venv/Scripts/python -m pytest -q -p no:cacheprovider tests/test_profile_callbacks.py
# 7 failed in 0.26s (log externo tasks/bridge-r3-red.log)
```

Los siete casos reproducen B01: el modo por defecto sale del entorno raíz, el idioma de la composición y
de los comandos sale del entorno raíz, `cited_quote` devuelve el pasaje del perfil A con el perfil B activo,
el transformador prepara una escritura tras el cambio de perfil, la ruta de auditoría es la raíz y el estado
de modo de A se filtra a B por un `ctx.state` compartido.

Sonda independiente de Codex, sin cambios en el repositorio:

```
.venv/Scripts/python -m pytest -q -p no:cacheprovider ../tasks/test_bridge_r2_adversarial.py
# 4 failed, 17 passed in 5.86s (log externo tasks/bridge-r3-adversarial-before.log)
# FAILED test_full_default_comes_from_registration_profile
# FAILED test_full_quote_refuses_a_different_search_profile
# FAILED test_full_transform_cannot_write_after_scope_switch
# FAILED test_fake_cannot_write_a_path_rejected_by_the_isolation_guard
```

## Lo que cambió

| Archivo | Cambio |
| --- | --- |
| `hermes_cited/plugin.py` | `_CALL` (ContextVar) + `_profile_call` validan el alcance y leen sus ajustes antes de un efecto. `hermes_home`, `_secret` y `_language` resuelven por la llamada en curso. `_ProfileState` prefija `ctx.state` con el home canónico. `Turn.home`, `_owner` y el `home` explícito de cada callback ligan el turno a su perfil. `_profile_command` valida antes de cambiar el modo. `_transform_llm_output` usa el idioma del perfil. |
| `hermes_cited/modes.py` | `mode_command(state, mode, language=None)`: el idioma del perfil que registró el comando. |
| `tests/test_profile_callbacks.py` | Siete casos nuevos de B01. |

Las factorías conservan su firma compatible (`_pre_llm_call(state, registration=None)`,
`_quote_handler(state, registration=None)`, `_transform_llm_output(state, registration=None)`,
`_post_tool_call(registration=None)`): con un registro validan y aíslan; sin él (llamada directa de una
prueba) conservan la ruta de entorno de H0-H18. Producto pasa siempre el registro.

## Lo medido después

```
.venv/Scripts/python -m pytest -q -p no:cacheprovider tests/test_profile_callbacks.py
# 7 passed in 0.26s

.venv/Scripts/python -m pytest -q -p no:cacheprovider ../tasks/test_bridge_r2_adversarial.py
# 21 passed in 4.74s (log externo tasks/bridge-r3-adversarial-after.log)

.venv/Scripts/python -m pytest -q -p no:cacheprovider tests/test_plugin.py tests/test_modes.py `
  tests/test_host.py tests/test_adversarial.py tests/test_profile_scope.py tests/test_search_only_mode.py
# 173 passed in 84.29s (log externo tasks/bridge-r3-targeted.log)
```

## Reproducción con el `secret_scope` real de Hermes (pin `dce1e9b`)

```
.venv/Scripts/python ../tasks/bridge-r2-real-scope.py
```

Salida observada (redactada; log externo `tasks/bridge-r3-real-scope.log`):

- `pre_hook`: el contexto de modo cited del perfil A (antes: `null`, el turno tomaba dot de la raíz).
- `request_count`: 1, a `http://127.0.0.1:61823/api/mcp` del perfil A.
- `cross_profile_quote`: la oración fija de alcance («this Hermes profile has no readable secret scope»),
  sin el pasaje de A (antes devolvía literalmente `Only profile A owns this synthetic line.`).
- `captured_writes`: `[]` (antes preparaba `audit.append_entry` en la raíz con la salida sintética de B).

El transporte se captura en memoria y el append se intercepta, así que la sonda no escribe datos cruzados.
No se afirma una explotación en producción ni una corrida del dispatcher completo de Hermes.

## Sonda R1 (histórica)

```
.venv/Scripts/python -m pytest -q -p no:cacheprovider ../tasks/test_bridge_r1_adversarial.py
# 26 passed, 1 failed in 4.43s (log externo tasks/bridge-r3-adversarial-r1.log)
```

El único fallo es `test_tasks_do_not_claim_failed_contract_criteria_complete`, que exige que 1.2 y 2.1 sigan
sin marcar; esas dos tareas se cerraron en R2 y la aserción ya fallaba en HEAD. La sonda no se modificó.

## Estado

B01 queda cubierto por pruebas de repositorio (RED 7 → GREEN 7), por la sonda independiente de R2 (4 failed
→ 21 passed) y por la reproducción con el `secret_scope` real. La aprobación independiente de esta ronda y la
revisión de Fable están pendientes; este reporte no se autoevalúa.
