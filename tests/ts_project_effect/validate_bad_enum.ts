import { Schema } from "effect"
import { ChildRecordSchema } from "./generated.ts"

// Schema.decodeUnknownSync should throw for invalid enum value
try {
  Schema.decodeUnknownSync(ChildRecordSchema)({
    status: 999,
  })
  console.error("FAIL: should have thrown for bad enum value")
  process.exit(1)
} catch {
  console.log("OK: correctly rejected bad enum value")
}
