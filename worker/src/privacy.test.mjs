// node --experimental-strip-types src/privacy.test.mjs  (teste rápido sem dependências)
import assert from "node:assert/strict";
import { cleanKey } from "./privacy.ts";
const c = (q) => cleanKey("search_no_result", { q });
assert.equal(c("123.456.789-09"), "q=#");
assert.equal(c("71 9 9876 5432"), "q=#");
assert.equal(c("40.140-110"), "q=#");
assert.equal(c("rg 12.345.678-9"), "q=rg #");
assert.equal(c("fulano@exemplo.com"), "q=[email]");
assert.equal(c("Juazeiro"), "q=juazeiro");
assert.equal(cleanKey("calc_scenario", { s: "r25" }), "s=r25");
assert.equal(cleanKey("outro", { q: "x" }), null);
console.log("privacy ok");
