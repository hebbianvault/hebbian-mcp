import { afterEach, beforeEach, describe, expect, test } from "@jest/globals";
import { loadConfig } from "../src/config.js";
import { listTools, rejectUnlistedTool, unknownToolResult } from "../src/tool_list.js";

// DEC #284: usage, audit_log and the GDPR export are an opt-in admin set.
const ADMIN = ["hebbian_usage", "hebbian_gdpr_export", "hebbian_audit_log"];

const saved = { ...process.env };

beforeEach(() => {
  process.env.HEBBIAN_API_TOKEN = "hbn_test";
  delete process.env.HEBBIAN_ADMIN_TOOLS;
});

afterEach(() => {
  process.env = { ...saved };
});

describe("listTools (DEC #284)", () => {
  test("default list has none of the admin tools and all 10 everyday tools", () => {
    const names = listTools(loadConfig()).map((t) => t.name);
    for (const admin of ADMIN) expect(names).not.toContain(admin);
    expect(names).toHaveLength(10);
  });

  test("HEBBIAN_ADMIN_TOOLS=1 lists all three admin tools", () => {
    process.env.HEBBIAN_ADMIN_TOOLS = "1";
    const names = listTools(loadConfig()).map((t) => t.name);
    for (const admin of ADMIN) expect(names).toContain(admin);
    expect(names).toHaveLength(13);
  });

  test("calling an admin tool without the opt-in is the plain unknown-tool error", () => {
    const config = loadConfig();
    const rejected = rejectUnlistedTool(config, "hebbian_audit_log");
    expect(rejected).toEqual(unknownToolResult("hebbian_audit_log"));
    expect(rejected?.isError).toBe(true);
    expect(rejected?.content[0].text).toBe("Unknown tool: hebbian_audit_log");
    // Same shape as a made-up name: the list is not an oracle.
    expect(rejectUnlistedTool(config, "hebbian_nope")).toEqual(unknownToolResult("hebbian_nope"));
  });

  test("with the opt-in, admin tools and everyday tools are not rejected", () => {
    process.env.HEBBIAN_ADMIN_TOOLS = "1";
    const config = loadConfig();
    for (const admin of ADMIN) expect(rejectUnlistedTool(config, admin)).toBeNull();
    expect(rejectUnlistedTool(config, "hebbian_search")).toBeNull();
  });
});
