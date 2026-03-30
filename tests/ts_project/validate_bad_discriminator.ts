// This file should FAIL tsc --noEmit because class literal is wrong.
import type { PersonMember } from "./generated.ts";

const person: PersonMember = {
  // @ts-expect-error — "NotAPerson" is not assignable to "Person"
  class: "NotAPerson",
};
