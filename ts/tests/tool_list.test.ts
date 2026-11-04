import { afterEach, beforeEach, describe, expect, test } from "@jest/globals";
import { loadConfig } from "../src/config.js";
import { isListedTool, listTools, unknownToolResult } from "../src/tool_list.js";

// DEC #284: usage, audit_log and the GDPR export are an opt-in admin set.
const ADMIN = ["hebbian_usage", "hebbian_gdpr_export", "hebbian_audit_log"];

describe("tool list (DEC #284)", () => {
  const saved = { ...process.env };

  beforeEach(() => {
    process.env.HEBBIAN_API_TOKEN = "test-token";
    delete process.env.HEBBIAN_ADMIN_TOOLS;
  });

  afterEach(() => {
    process.env = { ...saved };
  });

  test("default list has none of the admin tools", () => {
    const names = listTools(loadConfig()).map((t) => t.name);
    for (const admin of ADMIN) expect(names).not.toContain(admin);
    expect(names).toEqual(
      expect.arrayContaining(["hebbian_search", "hebbian_ask", "hebbian_read_node", "hebbian_capture"]),
    );
  });

  test.each(["1", "true", "yes", "on"])("HEBBIAN_ADMIN_TOOLS=%s lists all three", (value) => {
    process.env.HEBBIAN_ADMIN_TOOLS = value;
    const names = listTools(loadConfig()).map((t) => t.name);
    for (const admin of ADMIN) expect(names).toContain(admin);
    expect(names.length).toBe(listTools({ adminTools: false }).length + ADMIN.length);
  });

  test("a call to hebbian_audit_log without the opt-in returns the unknown-tool error", () => {
    const cfg = loadConfig();
    expect(isListedTool(cfg, "hebbian_audit_log")).toBe(false);
    const result = unknownToolResult("hebbian_audit_log");
    expect(result.isError).toBe(true);
    expect(result.content[0].text).toBe("Unknown tool: hebbian_audit_log");
    // Same shape as any unlisted name: the list is not an oracle.
    expect(unknownToolResult("hebbian_nope")).toEqual({
      ...result,
      content: [{ type: "text", text: "Unknown tool: hebbian_nope" }],
    });
  });

  test("with the opt-in, admin tools are listed and everyday tools always are", () => {
    process.env.HEBBIAN_ADMIN_TOOLS = "1";
    const cfg = loadConfig();
    for (const admin of ADMIN) expect(isListedTool(cfg, admin)).toBe(true);
    expect(isListedTool(cfg, "hebbian_search")).toBe(true);
    expect(isListedTool(cfg, "hebbian_nope")).toBe(false);
  });
});
