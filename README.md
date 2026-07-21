# No-Three-in-Line Explorer

A dependency-free web app for exploring the [no-three-in-line problem](https://en.wikipedia.org/wiki/No-three-in-line_problem): place `2n` points on an `n × n` grid without allowing three selected points to lie on one straight line.

The app supports grids from 3 × 3 through 90 × 90 and includes known configurations for selected sizes through 74.

## Features

- Interactive square grid with selectable points.
- Incremental detection of lines containing three or more selected points.
- Checked-by-default prevention of moves that would complete such a line.
- Identity, rotational, diagonal, orthogonal, and full symmetry modes.
- Loading and displaying compact configuration codes.
- Bundled known configurations and a converter for refreshing them from copied source data.
- No framework, build system, or runtime dependencies.

## Run locally

Serve the project directory with any static web server. For example:

```sh
python3 -m http.server 8000
```

Then open [http://localhost:8000](http://localhost:8000).

Opening `index.html` directly may also work, but a local server gives behavior closer to normal web hosting.

## Tests

Run the dependency-free test suite with:

```sh
npm test
```

The suite checks compact-code validation and round trips, randomized incremental line-index updates against a brute-force reference, every bundled optimal solution, and reproducibility of the generated solution bundle.

## Compact configuration encoding

A code starts with one symmetry-class character:

| Character | Symmetry class |
|---|---|
| `.` | `iden` |
| `:` | `rot2` |
| `/` | `dia1` |
| `-` | `ort1` |
| `o` | `rot4` |
| `c` | `rct4` |
| `x` | `dia2` |
| `+` | `ort2` |
| `*` | `full` |

The remaining characters encode the two selected columns in every row, reading rows from top to bottom and columns from left to right. Column numbers use this 90-character alphabet:

```text
0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz#$%&@?!()[]<>{}=*+|-/~^_:;,.
```

Because a complete configuration contains exactly two selected cells in each row, an `n × n` configuration has one symmetry character followed by `2n` column characters.

For example:

```text
.1224041303
```

describes this identity-symmetric 5 × 5 configuration:

```text
. o o . .
. . o . o
o . . . o
. o . o .
o . . o .
```

The format and symmetry notation follow [Achim Flammenkamp's no-three-in-line database](https://wwwhomes.uni-bielefeld.de/achim/no3in/readme.html).

### Load a configuration from the URL

Add a `code` query parameter to open the app with a configuration already loaded:

```text
http://localhost:8000/?code=o3545011706672324
```

Codes containing URL punctuation such as `#`, `&`, or `+` must be URL-encoded. When constructing a link in JavaScript, use `encodeURIComponent(code)`.

## Refresh the bundled configurations

`optimal-solutions.txt` contains copied source records. Regenerate the compact JavaScript data with:

```sh
./convert.sh
```

This is equivalent to:

```sh
python3 convert_optimal_solutions.py \
  optimal-solutions.txt \
  -o optimal-solutions.generated.js
```

The converter validates that every parsed solution is square, uses a recognized symmetry class, fits the 90-character alphabet, and selects exactly two cells per row.

## Project structure

| File | Purpose |
|---|---|
| `index.html` | App markup and controls |
| `style.css` | Layout and grid styling |
| `main.js` | UI state, interaction, symmetry handling, and rendering |
| `configuration-codec.js` | Compact-code codec and incremental line index |
| `optimal-solutions.generated.js` | Compact bundled configurations consumed by the app |
| `optimal-solutions.txt` | Source records used to generate the bundle |
| `convert_optimal_solutions.py` | Source-record parser and compact-code generator |
| `convert.sh` | Convenience regeneration command |
| `ATTRIBUTION.md` | Discovery credits, dates, sources, and uncertainty notes |

## Attribution and license

Known configurations and their attempted historical attributions are documented in [ATTRIBUTION.md](ATTRIBUTION.md). Several older discovery credits are necessarily approximate because the surviving source records identify publications or enumeration dates rather than exact first discoveries.

AI tools including OpenAI GPT-5.5 and GPT-5.6 were used to develop this project.

The project code is licensed under the [Apache License 2.0](LICENSE).
