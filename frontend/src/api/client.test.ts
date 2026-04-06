import { resolveApiBaseUrl } from "./client";

test("uses explicit API base URL when configured", () => {
  expect(resolveApiBaseUrl("http://api.example.test/api", { hostname: "192.168.1.20", protocol: "http:" })).toBe(
    "http://api.example.test/api",
  );
});

test("defaults to the current host for LAN access", () => {
  expect(resolveApiBaseUrl(undefined, { hostname: "192.168.152.128", protocol: "http:" })).toBe(
    "http://192.168.152.128:8000/api",
  );
});

test("keeps https when the page is served over https", () => {
  expect(resolveApiBaseUrl(undefined, { hostname: "evebox.local", protocol: "https:" })).toBe(
    "https://evebox.local:8000/api",
  );
});
