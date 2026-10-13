# Ronda 3 — M01: el runner D4/H22 verifica pin del host, digest canónico y catálogo real

Fecha: 2026-10-12, America/Mexico_City. Agente: DeepSeek. Rama: `feature/search-only-bridge`.
Contrato: D4, D5, H22. Origen: `tasks/revision-bridge-r2.md`, hallazgo M01 (Major). La tarea 5.3 sigue
[BLOCKED]: no existe la VM desechable en esta corrida.

## El defecto reproducido

Codex verificó leyendo el cuerpo del runner (`tasks/revision-bridge-r2.md`, M01): el CLI venía de una variable
arbitraria sin comprobar el pin del host, no se comparaba SHA-256/tamaño del archivo canónico con un lock, el
catálogo efectivo se sustituía por `bridge_support.FakeContext` y no se acreditaba el espejo de sólo lectura ni
la red bloqueada. Sonda nueva de esta ronda contra el runner de HEAD:

```
.venv/Scripts/python ../tasks/bridge-r3-m01-red.py
# {'check_host_pin': False, 'read_bridge_lock': False, 'canonical_archive': False,
#  'verify_bridge_lock': False, 'effective_catalog': False, 'vm_host_root': False}
# MISSING: check_host_pin, read_bridge_lock, canonical_archive, verify_bridge_lock, effective_catalog, vm_host_root
# EXIT=1  (log externo tasks/bridge-r3-m01-red.log)
```

## Lo que cambió en `tests/test_profile_install.py`

| Pieza | Qué acredita |
| --- | --- |
| `_host_cli` / `_host_python` | El CLI y el python salen de `<chassis>/.venv/(bin|Scripts)`, la ruta que nombra D4. |
| `_check_host_pin(host_root)` | El HEAD de Git del checkout del host es exactamente `dce1e9b…`; deja de aceptarse un CLI arbitrario. |
| `BridgeLock` / `_read_bridge_lock` | Parsea y valida `sha` (40 hex), `sha256` (64 hex) y `size` positivo. |
| `_canonical_archive` | Ejecuta `git archive --format=tar --output=… <sha>` con configuración Git aislada (`GIT_CONFIG_NOSYSTEM`, `GIT_CONFIG_GLOBAL` vacío, `GIT_ATTR_NOSYSTEM`, `HOME`/`XDG_CONFIG_HOME` temporales, `-c core.attributesFile=`) y rechaza un `info/attributes` no rastreado. |
| `_verify_bridge_lock` | Compara el SHA-256 y el tamaño de los bytes canónicos con el lock; un SHA de Git no basta. |
| `CATALOG_PROBE` / `_effective_catalog` / `_parse_catalog` | Corre con el python del host, liga el alcance del perfil desde su `.env`, llama al loader real (`discover_plugins`, `get_plugin_manager`, `iter_hook_callbacks`, `get_plugin_commands`) y despacha `cited_search` por el registro real (`tools.registry.dispatch`). |
| `_assert_search_catalog` | Exige el plugin `hermes-cited` habilitado sin error, un tool, cero hooks y cero comandos, los tres hooks de full a cero y una respuesta de `cited_search`. |
| `_make_git_repo` | Repositorio temporal para probar pin, archivo canónico y lock sin la VM. |

Las variables de la VM pasan a ser cuatro: `HERMES_TEST_HOST_ROOT`, `HERMES_TEST_MIRROR`,
`HERMES_TEST_BRIDGE_REF`, `HERMES_TEST_BRIDGE_LOCK`; el runner exige además `HERMES_TEST_NETWORK_BLOCKED=1` y
un espejo no escribible. El cuerpo saltado hace: verificar el pin del host, comparar el lock, validar el
commit del puente, instalar con los flags de D4, verificar commit y árbol limpio, leer el manifiesto, pedir el
catálogo efectivo al loader real, comprobar la petición al fake y que no exista `cited/` bajo el perfil.

## Verificación offline (siempre corre)

```
.venv/Scripts/python -m pytest -q -p no:cacheprovider tests/test_profile_install.py
# 29 passed, 1 skipped in 1.61s
```

La omisión es `test_a_fresh_real_profile_installs_the_search_bridge`, con la razón explícita de la VM ausente
(las cuatro variables no están definidas). Las pruebas que sí corren crean repositorios Git temporales reales y
comprueban el pin (aceptado y rechazado), el digest canónico (coincide y se rechaza al alterar sha256 o size),
el parser del lock, el parser del catálogo y el rechazo de un catálogo con hooks o comandos de full.

## La tarea 5.3

[BLOCKED], sin cambios de causa: no existen la VM desechable, el CLI Linux aprovisionado y fijado, el espejo
montado en sólo lectura ni la red bloqueada tras el aprovisionamiento. No se sustituyó el E2E por una prueba
simulada y no se marca como ejecutado. El runner queda completo y listo para esa corrida.

## Estado

M01 queda cubierto offline; la instalación real en la VM sigue pendiente y se reporta como BLOCKED, no como
aprobada. Revisión independiente de esta ronda pendiente.
