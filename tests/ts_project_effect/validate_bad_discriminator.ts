import { Schema } from "effect"
import { PersonMemberSchema } from "./generated.ts"

// Schema.decodeUnknownSync should throw for wrong discriminator
try {
  Schema.decodeUnknownSync(PersonMemberSchema)({
    class: "NotAPerson",
  })
  console.error("FAIL: should have thrown for bad discriminator")
  process.exit(1)
} catch {
  console.log("OK: correctly rejected bad discriminator")
}
