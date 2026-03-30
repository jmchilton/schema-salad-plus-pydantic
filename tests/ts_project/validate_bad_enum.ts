// This file should FAIL tsc --noEmit because status is assigned a bad value.
import type { ChildRecord } from "./generated.ts";

const record: ChildRecord = {
  // @ts-expect-error — 999 is not a valid StatusEnum
  status: 999,
};
