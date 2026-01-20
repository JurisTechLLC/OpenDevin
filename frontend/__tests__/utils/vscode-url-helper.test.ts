import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { transformVSCodeUrl } from "#/utils/vscode-url-helper";

describe("transformVSCodeUrl", () => {
  const originalWindowLocation = window.location;

  beforeEach(() => {
    // Mock window.location
    Object.defineProperty(window, "location", {
      value: {
        hostname: "example.com",
        protocol: "https:",
      },
      writable: true,
    });
  });

  afterEach(() => {
    // Restore window.location
    Object.defineProperty(window, "location", {
      value: originalWindowLocation,
      writable: true,
    });
  });

  it("should return null if input is null", () => {
    expect(transformVSCodeUrl(null)).toBeNull();
  });

  it("should replace localhost with current hostname when they differ", () => {
    const input = "http://localhost:8080/?tkn=abc123&folder=/workspace";
    const expected = "https://example.com:8080/?tkn=abc123&folder=/workspace";

    expect(transformVSCodeUrl(input)).toBe(expected);
  });

  it("should not modify URL if hostname is not localhost", () => {
    // When hostname is not localhost but protocol differs, only protocol should change
    const input = "http://otherhost:8080/?tkn=abc123&folder=/workspace";
    const expected = "https://otherhost:8080/?tkn=abc123&folder=/workspace";

    expect(transformVSCodeUrl(input)).toBe(expected);
  });

  it("should not modify URL if current hostname is also localhost and protocol matches", () => {
    // Change the mocked hostname to localhost and protocol to http
    Object.defineProperty(window, "location", {
      value: {
        hostname: "localhost",
        protocol: "http:",
      },
      writable: true,
    });

    const input = "http://localhost:8080/?tkn=abc123&folder=/workspace";

    expect(transformVSCodeUrl(input)).toBe(input);
  });

  it("should handle invalid URLs gracefully", () => {
    const input = "not-a-valid-url";

    expect(transformVSCodeUrl(input)).toBe(input);
  });

  it("should transform HTTP to HTTPS when page is served over HTTPS", () => {
    // Mock window.location with HTTPS protocol
    Object.defineProperty(window, "location", {
      value: {
        hostname: "example.com",
        protocol: "https:",
      },
      writable: true,
    });

    const input = "http://example.com:8080/?tkn=abc123&folder=/workspace";
    const expected = "https://example.com:8080/?tkn=abc123&folder=/workspace";

    expect(transformVSCodeUrl(input)).toBe(expected);
  });

  it("should not transform HTTPS to HTTP when page is served over HTTP", () => {
    // Mock window.location with HTTP protocol
    Object.defineProperty(window, "location", {
      value: {
        hostname: "example.com",
        protocol: "http:",
      },
      writable: true,
    });

    const input = "https://example.com:8080/?tkn=abc123&folder=/workspace";

    expect(transformVSCodeUrl(input)).toBe(input);
  });

  it("should transform both hostname and protocol when needed", () => {
    // Mock window.location with HTTPS protocol and non-localhost hostname
    Object.defineProperty(window, "location", {
      value: {
        hostname: "bugzap.ai",
        protocol: "https:",
      },
      writable: true,
    });

    const input = "http://localhost:41234/?tkn=abc123&folder=/workspace";
    const expected = "https://bugzap.ai:41234/?tkn=abc123&folder=/workspace";

    expect(transformVSCodeUrl(input)).toBe(expected);
  });
});
