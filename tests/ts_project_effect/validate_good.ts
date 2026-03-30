import { Schema } from "effect"
import {
  ChildRecordSchema,
  PersonMemberSchema,
  OrgMemberSchema,
  isPersonMember,
  isOrgMember,
} from "./generated.ts"
import type { PersonMember, OrgMember } from "./generated.ts"

function assert(cond: boolean, msg: string): void {
  if (!cond) {
    console.error("FAIL:", msg)
    process.exit(1)
  }
}

// Decode valid PersonMember
const person = Schema.decodeUnknownSync(PersonMemberSchema)({
  class: "Person",
  name: "Alice",
  email: "alice@example.com",
})

assert(person.class === "Person", "person.class")
assert(person.name === "Alice", "person.name")
assert(person.email === "alice@example.com", "person.email")

// Decode valid OrgMember
const org = Schema.decodeUnknownSync(OrgMemberSchema)({
  class: "Organization",
  name: "Acme",
  url: "https://acme.org",
})

assert(org.class === "Organization", "org.class")
assert(org.name === "Acme", "org.name")

// Decode valid ChildRecord
const record = Schema.decodeUnknownSync(ChildRecordSchema)({
  id: "record-1",
  status: "active",
  "format-version": "1.0",
  items: { key1: "val1", key2: "val2" },
  tags: ["a", "b"],
  members: [
    { class: "Person", name: "Alice", email: "alice@example.com" },
    { class: "Organization", name: "Acme", url: "https://acme.org" },
  ],
})

assert(record.id === "record-1", "id")
assert(record.status === "active", "status")
assert(record["format-version"] === "1.0", "format-version")
assert(record.items!["key1"] === "val1", "items dict")
assert(record.tags!.length === 2, "tags array length")
assert(record.members!.length === 2, "members length")

// Type guards
assert(isPersonMember(person as PersonMember | OrgMember) === true, "isPersonMember(person)")
assert(isOrgMember(person as PersonMember | OrgMember) === false, "isOrgMember(person)")
assert(isOrgMember(org as PersonMember | OrgMember) === true, "isOrgMember(org)")
assert(isPersonMember(org as PersonMember | OrgMember) === false, "isPersonMember(org)")

console.log("OK: all assertions passed")
