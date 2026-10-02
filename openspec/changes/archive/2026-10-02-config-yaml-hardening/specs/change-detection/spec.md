## ADDED Requirements

### Requirement: Fingerprinting does not raise on an editorial or defaults map

Computing any fingerprint component, including the editorial hash that the API also serves as its ETag,
SHALL NOT raise because a mapping in the hashed content has keys that are not strings, or keys of mixed
types that cannot be ordered. For every input whose hash can be computed without this rule, the hash SHALL
be exactly the value it was before; the rule SHALL only supply a hash where none could be computed. Two
mappings that differ only in a key's type (`{1: x}` and `{"1": x}`) or in the presence of a key SHALL NOT be
conflated by the fallback.

#### Scenario: Native-key content hashes are unchanged

- **WHEN** an editorial dict or a defaults map has only string keys, or only integer keys, or only boolean keys
- **THEN** its hash equals the SHA-256 of its sorted-key JSON text, as it did before this requirement

#### Scenario: A date key does not crash the defaults hash

- **WHEN** the fingerprint is computed for a `look_defaults` map containing a `datetime.date` key
- **THEN** a fingerprint is returned, it is identical across two computations (including in two processes),
  and it differs from the fingerprint of the same map with a different value

#### Scenario: Mixed int and str keys do not crash the editorial hash

- **WHEN** `editorial_hash` is computed for a document whose `look` has the keys `1` and `"b"`
- **THEN** a hash is returned and a change to either value moves it

#### Scenario: Keys that differ only in type are not conflated

- **WHEN** the hash fallback is used for `{1: "a", "1": "b"}` and for `{1: "b", "1": "a"}`
- **THEN** the two hashes differ
