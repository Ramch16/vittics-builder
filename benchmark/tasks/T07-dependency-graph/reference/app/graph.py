import heapq


class MissingDependency(Exception):
    pass


class CycleError(Exception):
    def __init__(self, members):
        super().__init__(", ".join(members))
        self.members = list(members)


def _cycle_members(deps, remaining):
    """Packages on a cycle among `remaining` (strongly connected components of size > 1, or self-loops)."""
    index, low, stack, on, out, counter = {}, {}, [], set(), set(), [0]

    def visit(v):
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on.add(v)
        for w in set(deps[v]) & remaining:
            if w not in index:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on.discard(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1 or v in deps[v]:
                out.update(comp)
    for v in sorted(remaining):
        if v not in index:
            visit(v)
    return sorted(out)


def install_order(deps):
    for name, needs in deps.items():
        for need in needs:
            if need not in deps:
                raise MissingDependency(need)
    waiting = {name: set(needs) for name, needs in deps.items()}
    users = {name: set() for name in deps}
    for name, needs in waiting.items():
        for need in needs:
            users[need].add(name)
    ready = [n for n, needs in waiting.items() if not needs]
    heapq.heapify(ready)
    order = []
    while ready:
        n = heapq.heappop(ready)
        order.append(n)
        for user in users[n]:
            waiting[user].discard(n)
            if not waiting[user]:
                heapq.heappush(ready, user)
    if len(order) != len(deps):
        raise CycleError(_cycle_members(deps, set(deps) - set(order)))
    return order
