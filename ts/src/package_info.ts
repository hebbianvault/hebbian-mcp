/** Package metadata used for MCP self-identification. */
import { readFileSync } from "node:fs";

interface PackageJson {
  version: string;
}

const packageJsonUrl = new URL("../package.json", import.meta.url);
const packageJson = JSON.parse(readFileSync(packageJsonUrl, "utf8")) as PackageJson;

export const PACKAGE_VERSION = packageJson.version;
