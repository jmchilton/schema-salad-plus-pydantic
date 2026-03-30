// Validates that well-formed data satisfies the generated interfaces.
import type {
  ChildRecord,
  PersonMember,
  OrgMember,
} from "./generated.ts";
import { isPersonMember, isOrgMember } from "./generated.ts";

const person: PersonMember = {
  class: "Person",
  name: "Alice",
  email: "alice@example.com",
};

const org: OrgMember = {
  class: "Organization",
  name: "Acme",
  url: "https://acme.org",
};

const record: ChildRecord = {
  id: "record-1",
  status: "active",
  "format-version": "1.0",
  items: { key1: "val1", key2: "val2" },
  tags: ["a", "b"],
  members: [person, org],
};

// Runtime structural assertions
function assert(cond: boolean, msg: string): void {
  if (!cond) {
    console.error("FAIL:", msg);
    process.exit(1);
  }
}

assert(record.id === "record-1", "id");
assert(record.status === "active", "status");
assert(record["format-version"] === "1.0", "format-version alias");
assert(record.items!["key1"] === "val1", "items dict");
assert(record.tags!.length === 2, "tags array length");
assert(record.members!.length === 2, "members length");

// Type guard assertions
assert(isPersonMember(person) === true, "isPersonMember(person)");
assert(isOrgMember(person) === false, "isOrgMember(person)");
assert(isOrgMember(org) === true, "isOrgMember(org)");
assert(isPersonMember(org) === false, "isPersonMember(org)");

console.log("OK: all assertions passed");
