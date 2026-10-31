# T07 Dependency graph

Implement `app/graph.py`: `install_order(deps: dict[str, list[str]]) -> list[str]`, where `deps[name]` lists
what `name` depends on.

Requirements
- R1 Every package appears once, after all of its dependencies.
- R2 Among packages that are ready at the same time, alphabetical order decides (the result is deterministic).
- R3 A dependency that is not a key of `deps` raises `MissingDependency` naming it.
- R4 A cycle raises `CycleError` whose `members` attribute is the sorted list of the packages on a cycle.
- R5 A package depending on itself is a cycle. Duplicate entries in a dependency list are allowed.
- R6 `deps` is not modified.
