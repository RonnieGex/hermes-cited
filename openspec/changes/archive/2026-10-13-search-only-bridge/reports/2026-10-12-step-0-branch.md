# Step 0: the branch (observed state)

Date: 2026-10-12. Change: search-only-bridge. Agent: Fable (spec author).

```
$ git branch --show-current
feature/search-only-bridge
$ git rev-parse HEAD
c0f7e9729943e6ecef1fe380ccba883e635085df
$ git merge-base main HEAD
c0f7e9729943e6ecef1fe380ccba883e635085df
```

The branch was created with `git switch -C feature/search-only-bridge main` in this session; its first commit is the change folder.
