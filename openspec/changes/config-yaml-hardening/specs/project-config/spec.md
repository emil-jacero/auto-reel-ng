## ADDED Requirements

### Requirement: A config.yaml that cannot be loaded or used fails loud as a configuration error

Every way a project `config.yaml` can fail to load SHALL surface as the typed configuration error naming
the file, never as a builtin exception. This includes YAML the parser rejects, a well-formed value its tag
cannot hold (an unquoted date that does not exist, such as `2024-02-30`, an unknown `!!bool` value), a
document nested too deeply to construct, and any other error raised while constructing the document.

After a successful load and before any field is read, the system SHALL validate the content and raise the
configuration error, naming the key path, for each of the following:

- a string, as a key or a value anywhere in the file, that cannot be encoded as UTF-8 (a lone surrogate);
- an integer too large to be printed;
- under `look`, a mapping key that is not a string (a date, a number, a boolean), at any depth;
- a mapping or list that contains itself through an alias.

Values under `look`, `worker`, `api` and `thumbnails` SHALL otherwise stay uninterpreted.

#### Scenario: An impossible date is a configuration error

- **WHEN** `config.yaml` contains `look: {a: 2024-02-30}`
- **THEN** loading raises the configuration error whose message names the file and says the YAML is
  malformed, and no `ValueError` escapes

#### Scenario: Other builtin errors from the YAML load are configuration errors

- **WHEN** `config.yaml` contains `a: !!bool maybe`, or a flow sequence nested a hundred thousand levels deep
- **THEN** loading raises the configuration error, not `KeyError` or `RecursionError`

#### Scenario: A non-string look key is refused with its path

- **WHEN** `config.yaml` contains `look: {2024-01-01: x}`, or `look: {1: a, b: c}`, or a non-string key at
  depth, as in `look: {title: {1: x}}`
- **THEN** loading raises the configuration error naming `look` (or `look.title`) and the offending key,
  before any fingerprint is computed

#### Scenario: String keys and non-string keys outside look are accepted

- **WHEN** `config.yaml` has only string keys under `look`, or an integer key under `worker`
- **THEN** it loads exactly as before

#### Scenario: A lone surrogate is refused wherever it appears

- **WHEN** `config.yaml` contains `layout: "x\ud800"`, or the same escape in a `look` value, a `look` key or
  a `database.url`
- **THEN** loading raises the configuration error naming the key path and stating the string is not valid
  Unicode text, and no `UnicodeEncodeError` can occur later when the value is printed, logged, hashed or
  sent as JSON

#### Scenario: A huge hexadecimal integer is refused

- **WHEN** `config.yaml` contains `look: {a: 0x` followed by five thousand `f` digits `}`
- **THEN** loading raises the configuration error naming `look.a`, the same refusal a `reel.yaml` gets

#### Scenario: A self-referencing alias is refused

- **WHEN** `config.yaml` contains `look: &a {x: *a}`
- **THEN** loading raises the configuration error stating the structure refers to itself, and does not
  recurse without bound

#### Scenario: A valid file is unaffected

- **WHEN** `config.yaml` has a string-keyed `look`, a `layout`, `sort`, and non-ASCII text such as `Café`
  and `日本語`
- **THEN** it loads to the same `ProjectConfig` as before
