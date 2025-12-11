# Installation

## Prerequisites

- **Python 3.10 or later**
- **Access to a Globus Compute endpoint** - You'll need access to an HPC cluster or remote compute resource running a Globus Compute endpoint. If you don't have one configured, see the [Globus Compute documentation](https://funcx.readthedocs.io/) for setup instructions.

## Installing with uv (recommended)

The recommended way to install Groundhog is using [uv's tool management](https://docs.astral.sh/uv/concepts/tools/#the-uv-tool-interface):

```bash
uv tool install groundhog-hpc@latest
```

This installs the `hog` CLI in an isolated environment, keeping your system Python clean.

### Verifying installation

Check that the installation succeeded:

```bash
hog --version
```

### Upgrading

To upgrade to the latest version:

```bash
uv tool upgrade groundhog-hpc
```

### Adding packages to the tool environment

If you need to add additional packages to Groundhog's tool environment (for example, if you need certain modules present in order to deserialize results):

```bash
uv tool install groundhog-hpc --with some-package
```

To add packages to an existing installation:

```bash
uv tool install --reinstall groundhog-hpc --with some-package
```

## Alternative: Installing with pip

You can also install with pip, though this is not recommended for most users:

```bash
pip install groundhog-hpc
```

!!! warning "pip installation caveat"
    Installing with pip into your global Python environment can cause dependency conflicts. Consider using a virtual environment or the uv tool installation method instead.

## Installing from source

For development or to use the latest unreleased features:

```bash
git clone https://github.com/Garden-AI/groundhog.git
cd groundhog
uv tool install .
```

## Next steps

Once installed, continue to the [Quickstart](quickstart.md) to write your first groundhog function.
