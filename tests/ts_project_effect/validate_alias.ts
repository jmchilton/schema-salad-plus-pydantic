import { Schema } from "effect"
import { ChildRecordSchema } from "./generated.ts"

function assert(cond: boolean, msg: string): void {
  if (!cond) {
    console.error("FAIL:", msg)
    process.exit(1)
  }
}

// Decode data with hyphenated key (alias)
const record = Schema.decodeUnknownSync(ChildRecordSchema)({
  "format-version": "2.0",
})

assert(record["format-version"] === "2.0", "format-version alias round-trip")
console.log("OK: alias round-trip passed")
