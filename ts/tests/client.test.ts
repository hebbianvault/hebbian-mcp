import { afterEach, beforeEach, describe, expect, jest, test } from "@jest/globals";

import { HebbianApiError, HebbianClient, HebbianTimeoutError } from "../src/client.js";
import { handleCapture } from "../src/tools/capture.js";

const originalTimeout = process.env.HEBBIAN_TIMEOUT_MS;
let fetchSpy: jest.SpiedFunction<typeof fetch>;

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  fetchSpy = jest.spyOn(globalThis, "fetch");
});

afterEach(() => {
  fetchSpy.mockRestore();
  if (originalTimeout === undefined) delete process.env.HEBBIAN_TIMEOUT_MS;
  else process.env.HEBBIAN_TIMEOUT_MS = originalTimeout;
});

describe("HebbianClient timeout and retry policy", () => {
  test("a hanging capture call fails with the configured timeout tool error", async () => {
    process.env.HEBBIAN_TIMEOUT_MS = "25";
    const abortError = new DOMException("Aborted", "AbortError");
    fetchSpy.mockImplementation((_input, init) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => {
        reject(abortError);
      }, { once: true });
    }));
    const client = new HebbianClient("https://api.example.test", "test-token");
    const startedAt = Date.now();

    await expect(client.post("/capture", { title: "T", body: "B" })).rejects.toMatchObject({
      statusCode: null,
      errorCode: "request_timeout",
      cause: abortError,
    } satisfies Partial<HebbianTimeoutError>);

    await expect(handleCapture(client, { title: "T", text: "B" })).rejects.toThrow(
      "Request timed out after 25ms. Set HEBBIAN_TIMEOUT_MS to a larger value if needed.",
    );

    expect(Date.now() - startedAt).toBeLessThan(300);
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });

  test("does not retry a POST when capture receives a 5xx response", async () => {
    fetchSpy
      .mockResolvedValueOnce(jsonResponse(500, { code: "server_error", message: "Try later" }))
      .mockResolvedValueOnce(jsonResponse(200, { uuid: "would-be-duplicate" }));
    const client = new HebbianClient("https://api.example.test", "test-token");

    await expect(handleCapture(client, { title: "T", text: "B" })).rejects.toThrow(
      "API error 500 (server_error): Try later",
    );

    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  test("retries a GET once after a 5xx response and returns the second response", async () => {
    fetchSpy
      .mockResolvedValueOnce(jsonResponse(500, { message: "Try later" }))
      .mockResolvedValueOnce(jsonResponse(200, { uuid: "retried" }));
    const client = new HebbianClient("https://api.example.test", "test-token");

    await expect(client.get("/nodes/retried")).resolves.toEqual({ uuid: "retried" });
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });

  test("retries a GET once after a network error", async () => {
    fetchSpy
      .mockRejectedValueOnce(new TypeError("network unavailable"))
      .mockResolvedValueOnce(jsonResponse(200, { uuid: "retried" }));
    const client = new HebbianClient("https://api.example.test", "test-token");

    await expect(client.get("/nodes/retried")).resolves.toEqual({ uuid: "retried" });
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });

  test("fails after exactly two GET attempts when both responses are 5xx", async () => {
    fetchSpy
      .mockResolvedValueOnce(jsonResponse(500, { message: "first failure" }))
      .mockResolvedValueOnce(jsonResponse(500, { code: "server_error", message: "second failure" }));
    const client = new HebbianClient("https://api.example.test", "test-token");

    await expect(client.get("/nodes/retried")).rejects.toMatchObject({
      statusCode: 500,
      errorCode: "server_error",
    } satisfies Partial<HebbianApiError>);
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });
});
