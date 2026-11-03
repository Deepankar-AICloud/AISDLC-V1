import { describe, expect, it } from 'vitest';
import { isPortalRequest, parsePortalRequest } from '../api';

// Fixture test: a representative JSON payload matching the shape asserted by EnumJsonSerializationTests.cs
// (enum string conversion, nullable fields), parsed through the real application parser. This is a fixture
// comparison, not a live cross-stack call: no backend was started, and this payload was hand-written to match
// the shape, not captured verbatim from an actual HTTP response.
const REPRESENTATIVE_BACKEND_SHAPED_JSON =
  '{"id":"29e0ebf9-e6fd-4d3f-9508-c40acdcbc817","kind":"Service","requestTypeId":"8a0657e1-a212-4d85-9ab2-318ea566a8f7","requestTypeName":"Laptop Request","title":"JSON check","description":"Verifying enum shape","status":"Submitted","requesterId":"emp-json","managerId":null,"createdAt":"2026-11-03T08:37:01.1214928+00:00","updatedAt":null}';

describe('apiFixture: PortalRequest JSON shape (fixture-based, not live cross-stack)', () => {
  it('parses a representative backend-shaped payload through the real application parser', () => {
    const parsed = parsePortalRequest(REPRESENTATIVE_BACKEND_SHAPED_JSON);

    expect(parsed.kind).toBe('Service');
    expect(parsed.status).toBe('Submitted');
    expect(parsed.requestTypeName).toBe('Laptop Request');
    expect(parsed.managerId).toBeNull();
    expect(parsed.updatedAt).toBeNull();
  });

  it('isPortalRequest accepts the representative shape and rejects a malformed one', () => {
    const parsed: unknown = JSON.parse(REPRESENTATIVE_BACKEND_SHAPED_JSON);
    expect(isPortalRequest(parsed)).toBe(true);

    const malformed = { ...(parsed as Record<string, unknown>), status: 'NotARealStatus' };
    expect(isPortalRequest(malformed)).toBe(false);
  });
});
