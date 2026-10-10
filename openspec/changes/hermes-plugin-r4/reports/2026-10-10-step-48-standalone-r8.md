# Step 48 — M-R7-2, the isolated extraction runs the suite green with the omission announced

Contract: `tasks/mision-cited-hermes-r8.md`, M-R7-2, fourth item: *extract the final SHA in an isolated folder
without a sibling and run the suite: green, with the omission announced*.

Frozen SHA: `70fd3c41f9415fac710ca704be19d11f60a4db27` (`feature/hermes-plugin`).

Extraction and run (no personal path is versioned; the folder is under the system temp directory):

```powershell
$standalone = Join-Path $env:TEMP 'hc-standalone-r8'
git -C <repo> archive --format=zip --output="$standalone\plugin.zip" 70fd3c4
Expand-Archive -Path "$standalone\plugin.zip" -DestinationPath "$standalone\hermes-cited"
Get-ChildItem $standalone          # only `hermes-cited`: there is no sibling `community-hermes`
$env:HERMES_HOME = "$standalone\home"
$env:HERMES_REVIEW_ROOT = <the read-only copy of the host, outside the extraction>
Remove-Item Env:\CITED_DOCS_REPO
& <plugin venv>\python.exe -B -m pytest -q -p no:cacheprovider -rs
```

Result: **691 passed, 3 skipped in 242.79s**, exit 0.

```text
SKIPPED [1] tests\regressions\test_r6_docs.py:172: CITED_DOCS_REPO is not set: the cross-repository check of community-hermes/docs/mcp.md is omitted
SKIPPED [1] tests\regressions\test_r6_docs.py:202: CITED_DOCS_REPO is not set: the cross-repository check of community-hermes/docs/mcp.md is omitted
SKIPPED [1] tests\regressions\test_r8_docs.py:69: CITED_DOCS_REPO is not set: the cross-repository check of community-hermes/docs/mcp.md is omitted
```

The extraction is skipped nowhere: every non-document fixture ran (the 691 include the host integration
fixtures, which find the read-only host copy by its absolute review root, outside the extraction). The three
omissions are the cross-repository document checks and each one carries its explicit reason in the summary;
nothing is silent.

State before/after: two fixtures of the published suite failed in an isolated checkout because they resolved a
fixed sibling; after, the suite is portable and the cross-repository check runs only when its checkout is
named.
