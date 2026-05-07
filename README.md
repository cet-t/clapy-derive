# clapy-derive

A [clap](https://docs.rs/clap/latest/clap/)-inspired declarative CLI argument parser for Python.

Define your CLI as a plain class with type annotations — clapy-derive handles parsing, help generation, and type conversion.

```python
from clapy_derive import clapy_arg, clapy_parser

@clapy_parser("version", "verbose")
class Cli:
    """My awesome tool."""

    input: str = clapy_arg(short=True, long=True, help="input file")
    output: str = clapy_arg(short=True, long=True, default="output.txt")

if __name__ == "__main__":
    cli = Cli.parse()
    print(cli.input)
    print(cli.output)
```

```
$ python main.py --input data.csv
data.csv
output.txt

$ python main.py -i data.csv -o result.txt
data.csv
result.txt

$ python main.py --help
usage: cli [-h] [-V] [-v] -i INPUT [-o OUTPUT]

My awesome tool.

options:
  -h, --help            show this help message and exit
  -V, --version         show program's version number and exit
  -v, --verbose         Enable verbose output
  -i, --input INPUT     input file
  -o, --output OUTPUT
```

## Installation

```bash
pip install clapy-derive
```

## Usage

### Positional arguments

A field with no `clapy_arg()` becomes a required positional argument — the same as clap's default behaviour for bare struct fields.

```python
@clapy_parser()
class Cli:
    name: str          # positional, required
    greeting: str = "hello"  # positional, optional with default
```

```
$ python main.py alice
```

### Named flags (`--long` / `-s`)

Use `clapy_arg(short=True, long=True)` to add `-x` / `--xxx` flags.

```python
@clapy_parser()
class Cli:
    output: str = clapy_arg(short=True, long=True, default="out.txt")
    count:  int = clapy_arg(short=True, long=True, default=1)
```

- `short=True` — auto-assign the first character of the field name (`-o`, `-c`)
- `long=True` — use the field name as the long flag (`--output`, `--count`)
- Pass an explicit string to override: `short="O"`, `long="out"`

Underscores in field names are converted to hyphens on the CLI (`output_file` → `--output-file`).

### Optional values (`T | None`)

Annotate with `T | None` to make an argument optional. The value is `None` when not provided.

```python
@clapy_parser()
class Cli:
    config: str | None = clapy_arg(short=True, long=True)
```

```
$ python main.py          # cli.config is None
$ python main.py -c x    # cli.config == "x"
```

### Multiple values (`list[T]`)

Annotate with `list[T]` to accept one or more values.

```python
@clapy_parser()
class Cli:
    files: list[str] = clapy_arg(short=True, long=True)
```

```
$ python main.py --files a.txt b.txt c.txt
```

### Boolean flags

A `bool` field becomes a store-true flag (default `False`).

```python
@clapy_parser()
class Cli:
    debug: bool = clapy_arg(short=True, long=True)
```

```
$ python main.py --debug   # cli.debug is True
$ python main.py           # cli.debug is False
```

### Built-in flags

Pass strings to `@clapy_parser()` to enable built-in flags:

| String | Flags added |
|--------|-------------|
| `"version"` | `-V` / `--version` (reads version from package metadata) |
| `"verbose"` | `-v` / `--verbose` (sets `cli.verbose: bool`) |

```python
@clapy_parser("version", "verbose")
class Cli:
    ...
```

### Type conversion

clapy-derive infers the conversion type from the field annotation automatically.

| Annotation | CLI input | Python value |
|------------|-----------|-------------|
| `str` | `"hello"` | `"hello"` |
| `int` | `"42"` | `42` |
| `float` | `"3.14"` | `3.14` |
| `pathlib.Path` | `"/tmp/f"` | `Path("/tmp/f")` |
| `bool` | flag present | `True` |

### `clapy_arg()` reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `short` | `bool \| str` | `False` | `-x` flag. `True` = first char of field name |
| `long` | `bool \| str` | `True` | `--xxx` flag. `True` = field name |
| `help` | `str` | `""` | Help text shown in `--help` |
| `default` | `Any` | *(required)* | Default value; makes the argument optional |
| `choices` | `list \| None` | `None` | Restrict to a set of allowed values |
| `metavar` | `str \| None` | `None` | Placeholder name in help output |
| `env` | `str \| None` | `None` | Environment variable to fall back to |

## Requirements

- Python 3.12+

## License

MIT
