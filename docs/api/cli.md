# Groundhog CLI Reference

**Usage**:

```console
$ hog [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--version`
* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.

**Commands**:

* `run`: Run a Python script on a Globus Compute...
* `init`: Create a new groundhog script with PEP 723...
* `add`: Add dependencies or update Python version...
* `remove`: Remove dependencies from a script&#x27;s PEP...

## `hog run`

Run a Python script on a Globus Compute endpoint.

**Usage**:

```console
$ hog run [OPTIONS] SCRIPT [HARNESS]
```

**Arguments**:

* `SCRIPT`: Path to script with PEP 723 dependencies to deploy to the endpoint  [required]
* `[HARNESS]`: Name of harness function to invoke from script  [default: main]

**Options**:

* `--no-fun-allowed`: Suppress emoji output
* `--help`: Show this message and exit.

## `hog init`

Create a new groundhog script with PEP 723 metadata and example code.

**Usage**:

```console
$ hog init [OPTIONS] FILENAME
```

**Arguments**:

* `FILENAME`: File to create  [required]

**Options**:

* `-p, --python TEXT`: Python version specifier (e.g., --python &#x27;&gt;=3.11&#x27; or -p 3.11)
* `-e, --endpoint TEXT`: Template config for endpoint with known fields, e.g. --endpoint my-endpoint-uuid. Can also be one of the following pre-configured names: anvil, anvil.gpu, tutorial (e.g. --endpoint anvil.gpu). Can specify multiple.
* `--help`: Show this message and exit.

## `hog add`

Add dependencies or update Python version in a script&#x27;s PEP 723 metadata.

**Usage**:

```console
$ hog add [OPTIONS] SCRIPT [PACKAGES]...
```

**Arguments**:

* `SCRIPT`: Path to the script to modify  [required]
* `[PACKAGES]...`: Packages to add

**Options**:

* `-r, --requirements, --requirement PATH`: Add dependencies from file
* `-p, --python TEXT`: Python version specifier
* `--help`: Show this message and exit.

## `hog remove`

Remove dependencies from a script&#x27;s PEP 723 metadata.

**Usage**:

```console
$ hog remove [OPTIONS] SCRIPT PACKAGES...
```

**Arguments**:

* `SCRIPT`: Path to the script to modify  [required]
* `PACKAGES...`: Packages to remove  [required]

**Options**:

* `--help`: Show this message and exit.
