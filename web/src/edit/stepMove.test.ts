import assert from "node:assert/strict";
import { test } from "node:test";

import { EDGE_WORDS, stepMove } from "./stepMove.ts";

const chapters = [
  { key: "r0", identities: ["a", "b", "c"] },
  { key: "r1", identities: ["d", "e"] },
  { key: "r2", identities: ["f"] },
];

test("a step inside a chapter moves one place", () => {
  assert.deepEqual(stepMove(chapters, "b", -1, false), {
    kind: "move",
    chapter: "r0",
    from: 1,
    to: 0,
  });
  assert.deepEqual(stepMove(chapters, "b", 1, false), {
    kind: "move",
    chapter: "r0",
    from: 1,
    to: 2,
  });
  assert.deepEqual(stepMove(chapters, "e", -1, false), {
    kind: "move",
    chapter: "r1",
    from: 1,
    to: 0,
  });
});

test("a step goes past a missing clip as past any listed clip", () => {
  const lay = [{ key: "r0", identities: ["a", "gone", "c"] }];
  assert.deepEqual(stepMove(lay, "a", 1, false), {
    kind: "move",
    chapter: "r0",
    from: 0,
    to: 1,
  });
  assert.deepEqual(stepMove(lay, "c", -1, false), {
    kind: "move",
    chapter: "r0",
    from: 2,
    to: 1,
  });
  // The missing clip itself steps inside its chapter too.
  assert.deepEqual(stepMove(lay, "gone", 1, true), {
    kind: "move",
    chapter: "r0",
    from: 1,
    to: 2,
  });
  assert.deepEqual(stepMove(lay, "gone", -1, true), {
    kind: "move",
    chapter: "r0",
    from: 1,
    to: 0,
  });
});

test("the first clip earlier goes to the end of the previous chapter", () => {
  assert.deepEqual(stepMove(chapters, "d", -1, false), {
    kind: "clip-drop",
    from: "r1",
    to: "r0",
    at: 3,
  });
  assert.deepEqual(stepMove(chapters, "f", -1, false), {
    kind: "clip-drop",
    from: "r2",
    to: "r1",
    at: 2,
  });
});

test("the last clip later goes to the start of the next chapter", () => {
  assert.deepEqual(stepMove(chapters, "c", 1, false), {
    kind: "clip-drop",
    from: "r0",
    to: "r1",
    at: 0,
  });
  assert.deepEqual(stepMove(chapters, "e", 1, false), {
    kind: "clip-drop",
    from: "r1",
    to: "r2",
    at: 0,
  });
});

test("a step into an empty chapter lands at its only gap", () => {
  const lay = [
    { key: "r0", identities: ["a"] },
    { key: "r1", identities: [] },
  ];
  assert.deepEqual(stepMove(lay, "a", 1, false), {
    kind: "clip-drop",
    from: "r0",
    to: "r1",
    at: 0,
  });
});

test("a missing clip at its chapter edge stays, with the reason", () => {
  const lay = [
    { key: "r0", identities: ["a", "gone"] },
    { key: "r1", identities: ["gone2", "d"] },
  ];
  assert.deepEqual(stepMove(lay, "gone", 1, true), {
    kind: "edge",
    words: EDGE_WORDS.missing,
  });
  assert.deepEqual(stepMove(lay, "gone2", -1, true), {
    kind: "edge",
    words: EDGE_WORDS.missing,
  });
  assert.match(EDGE_WORDS.missing, /missing/);
});

test("the first and last clip of the event return their reasons", () => {
  assert.deepEqual(stepMove(chapters, "a", -1, false), {
    kind: "edge",
    words: EDGE_WORDS.first,
  });
  assert.deepEqual(stepMove(chapters, "f", 1, false), {
    kind: "edge",
    words: EDGE_WORDS.last,
  });
  const single = [{ key: "r0", identities: ["a"] }];
  assert.deepEqual(stepMove(single, "a", -1, false), {
    kind: "edge",
    words: EDGE_WORDS.first,
  });
  assert.deepEqual(stepMove(single, "a", 1, false), {
    kind: "edge",
    words: EDGE_WORDS.last,
  });
});

test("a clip no chapter lists throws", () => {
  assert.throws(() => stepMove(chapters, "zz", 1, false), /no listed chapter/);
});
