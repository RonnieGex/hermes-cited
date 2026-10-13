# Round 4 — D9/M03: instalación offline real en el runner Linux desechable

Fecha: 2026-10-13, America/Mexico_City. Agente: DeepSeek. Rama: `feature/search-only-bridge`.
Contrato: design D4, D5, D9; spec H22. Origen: `tasks/revision-bridge-r3.md`, M03-R3 (NOT DONE / Major).
Cierra la reejecución de 5.3 que la revisión dejó abierta. Entorno: contenedor Linux desechable, red cerrada
salvo loopback, espejo y repositorio montados en sólo lectura, hogares temporales. Nunca se usaron los puertos
3240/3241 ni la instalación personal.

## Aprovisionamiento antes de cerrar la red

El espejo del bridge y su lock canónico son entradas externas de esta revisión:

```json
{
  "sha": "22a44d6bb85dcdbddeed3598a25d673a20e5d16b",
  "sha256": "46c4a80c68049e02e365732647adb91ca81fdd29bf58ae68acee4ea3edb2307b",
  "size": 2027520
}
```

Los runtimes administrados se descargaron con la red abierta y se verificaron contra las sumas que el propio
host fija en `pm/lock.json` para `linux-x64`:

| Paquete | Versión | SHA-256 | Bytes |
| --- | --- | --- | --- |
| CPython | `3.14.7+20260901` | `0ab3305457051cd3e7c031857e005f1bda17c218a1990567dacaaac6dd1d14f0` | 125528086 |
| uv | `0.12.3` | `600cf9a742aca00d292673b16b5acffaa7b8c269a364ad0c2e79498dcb1fe101` | 21721441 |

Además se calentó la caché uv con la **instalación real** `plugins install ... --enable --yes-deps` ejecutada
con red (caché resultante: 284956683 bytes) y se descargó el wheelhouse del build backend
(`setuptools-83.0.0`, `wheel-0.48.0`, `packaging-26.0`). Las tres fases de aprovisionamiento terminaron con
exit 0. La caché se monta en la corrida offline en `/opt/uv-cache`, que es exactamente
`store_root().parent/uv-cache`, el origen del que `pm.packages.uv_cache_dir` siembra su caché de máquina.

## Corrida offline

Imagen fijada por digest `sha256:4d1caded1f729ae443eb803f26ffde7b61e696aeaef62f099abb6dd6b14257c7`
(Python 3.12.14). Límites `--network none --user 0:0 --cpus 2 --memory 4g --pids-limit 300`; tmpfs para
`/opt/chassis` y `/opt/runtime`; montajes de sólo lectura para el venv del host, `/review`, `/inputs`,
`/upstream`, `/opt/uv-cache`, `/wheelhouse`, `/release` y `/repo`. El script interno reconstruye el índice
nativo de Git del checkout fijado, comprueba su HEAD, aprovisiona el store y arranca el índice.

La salida del runner registra la frontera de red:

```json
{"network_namespace": "Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT\n",
 "external_connect_refused": true, "mirror_writable": false, "uid": 0,
 "local_index": "http://127.0.0.1:40823/simple",
 "runtime": {"runtime_dir": "/opt/runtime", "network": "closed", ...},
 "wheelhouse": {...}}
```

El argv real del CLI fue:

```text
/opt/chassis/.venv/bin/hermes --profile bridge-probe plugins install \
  file:///release/hermes-cited.git --ref 22a44d6bb85dcdbddeed3598a25d673a20e5d16b --enable --yes-deps
```

Resultado medido:

```text
.venv-equivalente: /opt/chassis/.venv/bin/python -m pytest -vv -s --showlocals -p no:cacheprovider \
  tests/test_profile_install.py -k a_fresh_real_profile_installs
================= 1 passed, 29 deselected in 264.38s (0:04:24) =================
supervisor externo: exit 0, 301.95 s, contenedor eliminado (docker ps -a --filter name=bridge-r4: vacío)
```

Catálogo efectivo del perfil tras la instalación (medido por el loader real del host, no por un doble):

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

La línea base se toma **después del setup**, que incluye la recarga/readiness que el adaptador de
operaciones del harness posee (D4): el loader del host corre una vez y escribe su propio respaldo de
configuración; sólo entonces se fotografía el home completo. La corrida medida vuelve a pedir el catálogo y
el dispatch, y el inventario ordenado con SHA-256 de cada archivo regular del home del perfil es idéntico
antes y después. No se excluyó ningún archivo creado por el plugin. La prueba falla si el inventario cambia,
y pasa en esta corrida (`1 passed`).

## Límite declarado: el índice de build del host

El uv fijado por el host (`0.12.3`) resuelve `build-system.requires` a través de un índice **aunque** se
pasen `--no-index` y `--find-links`; se comprobó por separado que las variables `UV_NO_INDEX` y
`UV_FIND_LINKS` no cambian esa resolución, mientras que `UV_INDEX_URL` sí la atiende. Por eso el runner
sirve el wheelhouse aprovisionado en un índice PEP 503 **sólo loopback** y exporta `UV_INDEX_URL` y
`UV_INSECURE_HOST` a la corrida. La red externa permanece cerrada (`external_connect_refused: true`) y el
espejo sigue sin escritura; ninguna descarga sale de la interfaz loopback. Este límite es del host, no del
puente, y queda declarado en vez de ocultarse.

## Estado

M03-R3 queda cerrado con una instalación offline observable: el perfil nuevo contiene el commit y el digest
del bridge, el catálogo tiene `cited_search` y ningún hook/command de `full`, el dispatch scoped funciona y
el inventario completo no cambia tras el setup. 5.3 y 13.4 pasan a `[x]`. La aprobación independiente de
esta ronda y la revisión de Fable están pendientes; este reporte no se autoevalúa.
