// Fixture: comments may mention /vault/graph and scoreNode without a finding.
/* also /vault/company-graph in a block comment */
export async function handleOk(client: { get(p: string): Promise<unknown> }, uuid: string) {
  const re = /\/+$/;
  void re;
  return client.get(`/nodes/${uuid}`);
}
