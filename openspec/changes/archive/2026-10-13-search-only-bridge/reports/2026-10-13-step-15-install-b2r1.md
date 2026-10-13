# Bridge2 round 2 — D9/M03: re-ejecución de la instalación offline en el runner Linux

Fecha: 2026-10-13, America/Mexico_City. Agente: DeepSeek. Rama: `feature/search-only-bridge`.
Contrato: design D4, D5, D9; spec H22 (escenarios *Fresh real profile* y *Offline provisioning reaches the
catalog comparison*). Origen: `tasks/revision-bridge2-r1.md` (14.5) y `tasks/revision-bridge-r3.md`
(M03-R3). Cierra 13.4 y 11.4 sobre el commit de entrega de esta ronda. Entorno: contenedor Linux
desechable, `--network none` desde el arranque, espejo, entradas, runtime, caché uv y wheelhouse montados en
sólo lectura, hogares temporales. Nunca se usaron los puertos 3240/3241 ni la instalación personal.

## Aprovisionamiento (D9) reutilizado y verificado

La ronda 4 aprovisionó los runtimes administrados que el `plugins install` del host pin resuelve, antes de
cerrar la red: CPython `3.14.7+20260901` (SHA-256
`0ab3305457051cd3e7c031857e005f1bda17c218a1990567dacaaac6dd1d14f0`) y uv `0.12.3` (SHA-256
`600cf9a742aca00d292673b16b5acffaa7b8c269a364ad0c2e79498dcb1fe101`), más una caché uv tibia
(284956683 bytes) y el wheelhouse del build backend `setuptools-83.0.0`, `wheel-0.48.0`, `packaging-26.0`.
Esta corrida no descarga: `run.py` compara cada archivo contra el digest fijado por el propio `pm/lock.json`
del host antes de copiarlo a `/opt/runtime/fetch-<sha256>`. La salida del runner lo registra:

```json
{"network_namespace": "Iface\tDestination...",
 "external_connect_refused": true, "mirror_writable": false, "uid": 0,
 "local_index": "http://127.0.0.1:46769/simple",
 "runtime": {"runtime_dir": "/opt/runtime", "network": "closed",
   "packages": {"python": {"version": "3.14.7+20260901",
                           "sha256": "0ab3305457051cd3e7c031857e005f1bda17c218a1990567dacaaac6dd1d14f0"},
                "uv": {"version": "0.12.3",
                       "sha256": "600cf9a742aca00d292673b16b5acffaa7b8c269a364ad0c2e79498dcb1fe101"}},
   "wheelhouse": {"setuptools-83.0.0-py3-none-any.whl": "29b23c36...",
                  "wheel-0.48.0-py3-none-any.whl": "3217dcc8...",
                  "packaging-26.0-py3-none-any.whl": "b36f1fef..."}}}
```

## Espejo y archivo canónico del commit de entrega

Supervisor externo `tasks/bridge2-ds-r2-install.py` (fuera del repositorio): clon espejo nuevo y de sólo
lectura, `git archive --format=tar` con configuración Git aislada y lock canónico:

```json
{"sha": "64e05d83d827fe051ab13917f0eb9082e9bb1472",
 "sha256": "30548618d5969873a6c6f2a58ab3420e2a25ed8c206b14ceba349392bad8b736",
 "size": 2088960}
```

`64e05d8` es el HEAD de esta ronda: contiene la corrección D6/H14 de `3811a9f` y el contexto vivo de
`64e05d8`. No es el lock de release final ni sustituye la aprobación de Fable.

## Corrida offline

Argv real (contenedor `bridge2-ds-r2-install`, imagen fijada por digest
`sha256:4d1caded1f729ae443eb803f26ffde7b61e696aeaef62f099abb6dd6b14257c7`, Python 3.12.14):

```text
docker run --rm --name bridge2-ds-r2-install --network none --user 0:0 --cpus 2 --memory 4g --pids-limit 300
  --tmpfs /opt/chassis:rw,exec,size=1g,mode=1777 --tmpfs /opt/runtime:rw,exec,size=2g,mode=1777
  --env HERMES_TEST_BRIDGE_REF=64e05d83d827fe051ab13917f0eb9082e9bb1472
  --mount .../bridge-codex-r3-host/.venv:/opt/chassis/.venv:ro
  --mount .../bridge-codex-r3-linux:/inputs:ro --mount .../bridge-r4-linux:/provision:ro
  --mount .../bridge-r4-linux/upstream:/upstream:ro --mount .../bridge-r4-linux/uv-cache:/opt/uv-cache:ro
  --mount .../bridge-r4-linux/wheelhouse:/wheelhouse:ro
  --mount .../bridge2-ds-r2-linux:/review:ro --mount .../bridge2-ds-r2-linux/release:/release:ro
  --mount .../hermes-cited:/repo:ro
  sha256:4d1caded1f72... python /provision/run.py
```

El CLI real del host se ejecuta con el pin y el ref separados:

```text
/opt/chassis/.venv/bin/hermes --profile bridge-probe plugins install \
  file:///release/hermes-cited.git --ref 64e05d83d827fe051ab13917f0eb9082e9bb1472 --enable --yes-deps
```

Resultado medido:

```text
tests/test_profile_install.py::test_a_fresh_real_profile_installs_the_search_bridge PASSED
================= 1 passed, 29 deselected in 209.89s (0:03:29) =================
supervisor: {"exit": 0, "seconds": 252.89} / {"container_removed": true, "seconds_total": 253.23}
```

Catálogo efectivo del perfil tras la instalación, medido por el loader real del host (no un doble):

```json
{"name": "hermes-cited", "key": "hermes-cited", "kind": "standalone", "version": "0.2.0",
 "source": "user", "enabled": true, "tools": 1, "hooks": 0, "middleware": 0, "commands": 0, "error": null}
{"hooks": {"pre_llm_call": 0, "post_tool_call": 0, "transform_llm_output": 0}, "commands": []}
```

El dispatch scoped devolvió el sobre del modelo:

```json
{"cited_tool": "cited_search", "query": "hours", "text": "[1] sample.md\nHours\nOpen Monday to Friday.",
 "passages": [{"n": 1, "document": "sample.md", "heading": "Hours", "position": 0,
               "excerpt": "Open Monday to Friday.", "lines": [{"line": 1, "text": "Open Monday to Friday."}]}]}
```

## Inventario completo (D5)

La línea base se toma después del setup (la corrida del loader que escribe el respaldo de configuración del
host); la corrida vuelve a pedir catálogo y dispatch, y el inventario ordenado con SHA-256 de cada archivo
regular del home del perfil es idéntico antes y después: **268 archivos**, `assert after == baseline`
aprobado, y `cited/` ausente. No se excluyó ningún archivo creado por el plugin. El reporte no publica la
tabla completa por tamaño; vive en `tasks/bridge2-ds-r2-install.log` (fuera del repositorio).

## Estado

El host verificado es `dce1e9b37581dd62e480a9064dc04a709c2940d3` y el bridge instalado es
`64e05d8`; el contenedor terminó y fue eliminado (`container_removed: true`), sin puertos publicados y sin
servicios personales. La instalación offline, el catálogo, el dispatch scoped y la comparación del
inventario completo quedan ejecutados sobre el commit de entrega. 13.4 y 11.4 pasan a cerrados con este
reporte. La aprobación independiente y la revisión de Fable están pendientes; este reporte no se autoevalúa.
