// Fixture: a banned endpoint called with a query string. Not shipped, not compiled.
export async function handleQuery(client: { get(p: string): Promise<unknown> }) {
  return client.get(`/vault/graph?limit=${500}`);
}
