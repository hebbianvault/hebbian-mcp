// Fixture: a tool that breaks the thin-client rule. Not shipped, not compiled.
const GRAPH_PATH = "/vault/graph";

export function scoreNode(node: { title: string }, query: string): number {
  return node.title.includes(query) ? 1 : 0;
}

export async function handleBad(client: { get(p: string): Promise<{ nodes: { title: string }[] }> }) {
  const visited = new Set<string>();
  const graph = await client.get(GRAPH_PATH);
  visited.add("x");
  return graph.nodes.sort((a, b) => scoreNode(b, "q") - scoreNode(a, "q"));
}
