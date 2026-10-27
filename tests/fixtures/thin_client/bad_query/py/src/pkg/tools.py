"""Fixture: a banned endpoint called with a query string. Not shipped, not run."""


async def handle_query(client, n):
    return await client.get(f"/vault/graph?limit={n}")


async def handle_query_literal(client):
    return await client.get("/vault/graph?limit=500")
