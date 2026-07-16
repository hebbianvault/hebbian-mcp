import { afterEach, describe, expect, test } from "@jest/globals";
import { loadConfig } from "../src/config.js";

const originalEnv = {
  graphPagination: process.env.HEBBIAN_GRAPH_PAGINATION,
  token: process.env.HEBBIAN_API_TOKEN,
};

afterEach(() => {
  if (originalEnv.graphPagination === undefined) delete process.env.HEBBIAN_GRAPH_PAGINATION;
  else process.env.HEBBIAN_GRAPH_PAGINATION = originalEnv.graphPagination;
  if (originalEnv.token === undefined) delete process.env.HEBBIAN_API_TOKEN;
  else process.env.HEBBIAN_API_TOKEN = originalEnv.token;
});

describe("HEBBIAN_GRAPH_PAGINATION", () => {
  test.each(["1", "true", "yes", "on", "  true  "])("enables graph pagination for %s", (value) => {
    process.env.HEBBIAN_API_TOKEN = "test-token";
    process.env.HEBBIAN_GRAPH_PAGINATION = value;

    expect(loadConfig().graphPagination).toBe(true);
  });

  test.each([undefined, "0", "false", "no", "anything else"])(
    "leaves graph pagination disabled for %s",
    (value) => {
      process.env.HEBBIAN_API_TOKEN = "test-token";
      if (value === undefined) delete process.env.HEBBIAN_GRAPH_PAGINATION;
      else process.env.HEBBIAN_GRAPH_PAGINATION = value;

      expect(loadConfig().graphPagination).toBe(false);
    },
  );
});
