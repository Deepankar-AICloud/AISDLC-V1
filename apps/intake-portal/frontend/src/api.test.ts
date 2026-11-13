import { describe, expect, it } from "vitest";
import { ApiError, errorText, parseError } from "./api";
import { checkFile } from "./components/Dropzone";

describe("api errors", () => {
  it("parses server error shape including reasons", async () => {
    const res = new Response(
      JSON.stringify({
        error: { code: "approval_not_allowed", message: "No.", reasons: ["not owner"], correlation_id: "abc" },
      }),
      { status: 403 },
    );
    const err = await parseError(res);
    expect(err.code).toBe("approval_not_allowed");
    expect(err.reasons).toEqual(["not owner"]);
    expect(errorText(err)).toBe("No. (reference abc)");
  });

  it("handles non-JSON errors", async () => {
    const err = await parseError(new Response("oops", { status: 502 }));
    expect(err).toBeInstanceOf(ApiError);
    expect(err.message).toContain("502");
  });
});

describe("client-side file checks", () => {
  const f = (name: string, size: number) => new File([new Uint8Array(size)], name);
  it("rejects disallowed extensions, empty and oversized files", () => {
    expect(checkFile(f("a.exe", 10), [".pdf"], 1)).toMatch(/not allowed/);
    expect(checkFile(f("a.pdf", 0), [".pdf"], 1)).toMatch(/empty/);
    expect(checkFile(f("a.pdf", 2 * 1024 * 1024), [".pdf"], 1)).toMatch(/limit/);
    expect(checkFile(f("A.PDF", 10), [".pdf"], 1)).toBeNull();
  });
});
