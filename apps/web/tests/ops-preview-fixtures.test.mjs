import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

const fixturePath = new URL("../src/lib/ops-preview-fixtures.json", import.meta.url);
const fixture = JSON.parse(await readFile(fixturePath, "utf8"));

test("alert fixtures expose only public-status records with timeline", () => {
  assert.ok(Array.isArray(fixture.alerts));
  assert.ok(fixture.alerts.length >= 1);

  for (const alert of fixture.alerts) {
    assert.equal(alert.privacyClass, "public-status");
    assert.match(alert.id, /^alert-/);
    assert.ok(Array.isArray(alert.timeline));
    assert.ok(alert.timeline.length >= 1);
    assert.equal("secret" in alert, false);
    assert.equal("token" in alert, false);
    assert.equal("controlUrl" in alert, false);
  }
});

test("operations fixtures are read-only and status-schema scoped", () => {
  assert.equal(fixture.operations.schemaVersion, "ops-public-status/v0.proposal");
  assert.equal(fixture.operations.privacyClass, "public-status-only");
  assert.ok(Array.isArray(fixture.operations.runtimes));

  for (const runtime of fixture.operations.runtimes) {
    assert.equal(runtime.controlPolicy, "read-only-preview");
    assert.notEqual(runtime.schedule, "");
    assert.ok(Array.isArray(runtime.checks));
    assert.equal("startUrl" in runtime, false);
    assert.equal("stopUrl" in runtime, false);
    assert.equal("retryUrl" in runtime, false);
  }
});
