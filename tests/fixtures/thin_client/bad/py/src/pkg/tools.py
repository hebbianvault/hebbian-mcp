"""Fixture: a tool that breaks the thin-client rule. Docstring mention of /vault/graph is ignored."""


def _score(node, query):
    return 1 if query in node["title"] else 0


async def handle_bad(client, query):
    visited = set()
    graph = await client.get("/vault/graph")
    visited.add("x")
    return sorted(graph["nodes"], key=lambda n: _score(n, query))
