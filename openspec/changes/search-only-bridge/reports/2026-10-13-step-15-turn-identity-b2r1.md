# Bridge2 round 2 — D6/H14: capacidad de turnos por dueño y precedencia de identidad

Fecha: 2026-10-13, America/Mexico_City. Agente: DeepSeek. Rama: `feature/search-only-bridge`.
Contrato: design D6, H14 preservado por H22. Origen: `tasks/revision-bridge2-r1.md` (M01-B2R1, M02-B2R1)
y `tasks/revision-bridge-r3.md` (M01-R3, 13.2). Entorno: toda corrida usa un `HERMES_HOME` temporal y el
alcance real `agent.secret_scope` del host pin `dce1e9b37581dd62e480a9064dc04a709c2940d3`; la instalación
personal y el checkout `hermes-agent` son de sólo lectura; nunca se usan 3240/3241; el guard de 1.1 sigue
vigente. Las sondas externas se portaron al repositorio sin editarlas en `tasks/`.

Commits de esta ronda: `6b86df2` (regresiones RED portadas), `3811a9f` (corrección D6/H14), `64e05d8`
(contexto vivo y manuales).

## 13.2 — D6 (M01-R3 + M01-B2R1): la capacidad se expulsa por dueño

`_turn_of` conservaba una cota **global**: al llegar a `_MAX_TURNS`, eliminaba las primeras claves de toda
`_TURNS`. La revisión bridge2 abrió los 64 turnos de un segundo perfil validado y el turno pendiente del
dueño desapareció. La corrección añade `_evict_oldest_locked(owner)`, que expulsa sólo la clave más antigua
**del mismo dueño** `(home, session, turn)`; la cota sigue existiendo, pero por espacio de claves.

## 13.2 — H14 (M02-B2R1): una identidad explícita sin turno se rechaza

`_resolve_active_turn` caía en `if len(turns) == 1: return turns[0]` después de no resolver la identidad
explícita, así que `turn_id=already-finished` citaba el único turno vivo. La corrección distingue tres casos:
sin identidad (un solo turno abierto se usa; dos o más se rechazan como ambiguos), identidad explícita
(`turn_id` o `task_id`) que resuelve exactamente un turno, e identidad explícita que no resuelve ninguno,
que se rechaza con una frase de identidad no vinculada y nunca cita otro turno.

## RED

Regresiones portadas en `tests/test_round4_amendments.py` (D6/H14, host real):

```
.venv/Scripts/python -m pytest -q -p no:cacheprovider tests/test_round4_amendments.py -k "busy_foreign or stale_turn"
# 2 failed, 7 deselected in 1.45s
# FAILED test_busy_foreign_profile_does_not_evict_owners_pending_turn
# FAILED test_explicit_stale_turn_cannot_quote_the_only_different_live_turn
```

Sondas externas de Codex, antes de la corrección (sólo lectura, portadas después):

```
.venv/Scripts/python -m pytest -q -s -p no:cacheprovider ../tasks/test_bridge2_codex_r1.py
# 2 failed, 10 passed in 4.74s
# owner_after_foreign_pressure=Cited has no turn to quote from. ...
# stale_identity_result=Independent review evidence.
```

La sonda de evidencia documental queda RED por diseño; se cierra con los reportes de esta ronda:

```
.venv/Scripts/python -m pytest -q -p no:cacheprovider tests/test_bridge2_amendments.py -k reopened_rounds
# 1 failed, 15 deselected in 0.27s  (11.1 must be closed with the measured report of this round)
```

## GREEN

```
.venv/Scripts/python -m pytest -q -p no:cacheprovider tests/test_round4_amendments.py
# 9 passed in 2.49s

.venv/Scripts/python -m pytest -q -s -p no:cacheprovider ../tasks/test_bridge2_codex_r1.py
# 12 passed in 3.60s

.venv/Scripts/python -m pytest -q -p no:cacheprovider tests/test_bridge2_amendments.py tests/regressions/test_r3_regressions.py -k "not reopened_rounds"
# 156 passed, 1 deselected in 71.92s
```

Regresiones H14/D6 de `full` (sin cambio de comportamiento fuera de D6-D8):

```
.venv/Scripts/python -m pytest -q -p no:cacheprovider tests/test_profile_callbacks.py `
  tests/regressions/test_r4_transformer.py tests/test_modes.py tests/test_plugin.py `
  tests/test_adversarial.py tests/regressions/test_r3_regressions.py tests/regressions/test_r5_transformer.py
# 286 passed in 133.64s

.venv/Scripts/python -m pytest -q -p no:cacheprovider tests/test_host.py `
  tests/regressions/test_r4_host.py tests/regressions/test_r5_host.py `
  tests/regressions/test_r8_dot_passthrough.py tests/test_profile_scope.py `
  tests/test_search_only_mode.py tests/test_profile_install.py tests/test_round4_amendments.py
# 101 passed, 1 skipped in 59.08s
```

`tests/regressions/test_r3_regressions.py::test_r3_m_r3_2_two_open_turns_are_never_guessed` se actualizó
sólo en la frase esperada: su helper pasa una identidad explícita `t1` que no resuelve ningún turno abierto,
así que ahora recibe la frase de identidad no vinculada; se conserva la aserción de ambigüedad con
`turn=""` y la de que no se registra ninguna entrada. La invariante (rechazar, no adivinar, no registrar)
no cambia.

## Sondas portadas

`tests/test_bridge2_amendments.py` reúne el resto de las sondas de las dos revisiones sin duplicar las de
`tests/test_round4_amendments.py`: redacción del renglón inválido de cita (14.1), saneo del pre-hook antes
del dispatcher real (14.2), cadenas de excepción en quote/post, `PluginState` real alternando dos hogares,
cambio de modo del mismo hogar que no borra evidencia, consultas Unicode/whitespace nuevas, claves nativas
no string, catálogo real del loader, inventario completo de un retrieval vacío, pin del host con archivos
versionados modificados, `tar.umask` efectivo y tamaño de lock fraccionario. La sonda documental
`test_tasks_do_not_close_the_unexecuted_real_catalog` se sustituye por el invariante de evidencia: las
tareas reabiertas por las revisiones se cierran sólo si existe el reporte que las midió (la expectativa de
que 11.4 siguiera abierta quedó superseded por la corrida real de 13.4).

## Límite

La sonda M01-B2R1 usa dos registros del mismo módulo con el alcance real, como el escenario multiperfil de
D6; no reproduce una colisión entre dos copias del módulo cargadas por directorios distintos del loader. La
sonda M02-B2R1 ejerce el handler registrado y el resolvedor que también usa la vinculación de evidencia. No
se tocó `CITED_MCP_TOKEN` en modo search; ningún valor sintético de este reporte es un secreto real. La
aprobación independiente de Codex y la revisión de Fable están pendientes; este reporte no se autoevalúa.
