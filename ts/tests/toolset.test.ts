import { describe, expect, test } from "@jest/globals";
import { ADMIN_TOOLS_ENV, adminToolRefusal, listedTools } from "../src/toolset.js";

// DEC #284: the everyday tool set carries no admin power; usage, audit_log and
// the GDPR export are an opt-in admin set, off by default.
const ADMIN = ["hebbian_usage", "hebbian_gdpr_export", "hebbian_audit_log"];

describe("tool set (DEC #284)", () => {
  test("default listing has no admin tools", () => {
    const names = listedTools(false).map((t) => t.name);
    for (const admin of ADMIN) expect(names).not.toContain(admin);
    expect(names).toEqual(
      expect.arrayContaining(["hebbian_search", "hebbian_ask", "hebbian_read_node", "hebbian_capture"]),
    );
  });

  test("admin tools are listed only with the opt-in on", () => {
    const names = listedTools(true).map((t) => t.name);
    for (const admin of ADMIN) expect(names).toContain(admin);
    expect(names.length).toBe(listedTools(false).length + ADMIN.length);
  });

  test.each(ADMIN)("calling %s with the opt-in off is refused and names the flag", (name) => {
    const refusal = adminToolRefusal(name, false);
    expect(refusal).not.toBeNull();
    expect(refusal).toContain(ADMIN_TOOLS_ENV);
    expect(ADMIN_TOOLS_ENV).toBe("HEBBIAN_ADMIN_TOOLS");
  });

  test("everyday tools and opted-in admin tools are never refused", () => {
    expect(adminToolRefusal("hebbian_search", false)).toBeNull();
    for (const admin of ADMIN) expect(adminToolRefusal(admin, true)).toBeNull();
  });
});
