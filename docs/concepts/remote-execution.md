# Remote Execution

When you call `.remote()` or `.submit()`, Groundhog serializes your function call, sends it to your HPC cluster, executes it in an isolated environment, and returns the result.

## Execution Flow

Here's what happens when you call `result = my_function.remote(arg)`:

1. **Serialize arguments** - Groundhog pickles and base64-encodes your arguments and keyword arguments
2. **Resolve configuration** - Merge endpoint settings from PEP 723 metadata, decorator parameters, and call-time overrides
3. **Template shell command** - Generate a bash script (see below) containing:
    - Your script contents
    - A runner script
    - The serialized arguments
4. **Submit to Globus Compute** - Send the shell command to your HPC endpoint
5. **Remote execution**:
    - The shell script runs on an HPC compute node
    - Writes three temporary files: user script, runner script, and payload (`.in` file)
    - Executes `uv run --with groundhog-hpc==X.Y.Z runner.py`
    - `uv` reads the runner's PEP 723 metadata and installs dependencies
    - Runner imports your script as a module and deserializes arguments from `.in` file
    - Runner calls your function and serializes result to `.out` file
6. **Return result** - Shell script prints delimiter `__GROUNDHOG_RESULT__` followed by the `.out` file contents. Groundhog reads stdout, deserializes the result, and returns it.

## Groundhog vs Standard Globus Compute

Typical Globus Compute functions are registered on a per-function basis. Globus Compute serializes the function code and arguments, sends it to the endpoint, and executes it via the running endpoint process. This is a trade off: Groundhog serializes more data, but gains reproducible, declarative environments and vastly simpler dependency management.

Groundhog's approach differs in two ways:

1. **functions stay coupled to their scripts and metadata**. When you call `.remote()`, Groundhog sends your entire script (not just the function), along with the PEP 723 metadata fully describing the environment it needs.
This coupling ensures:
    - Dependencies specified in PEP 723 are always available, without manually keeping the environment in sync
    - Functions can reference module-level constants and imports
    - Multiple functions in the same script reuse configuration and environment

2. **functions are executed in their own subprocess**. It doesn't matter what version of Python the endpoint is running or what packages are available in the endpoint's environment -- the subprocess running the groundhog script doesn't even need the globus-compute package installed.
!!! note "So what?"
    Because the environment is completely independent from the endpoint process, you can quickly iterate on your environment (e.g. change python versions, install new packages) _without_ re-starting the endpoint process.

## The Shell Script

The templated shell script orchestrates the execution:

```bash
#!/bin/bash
set -euo pipefail

# Set up cache directories (prefer GROUNDHOG_CACHE_DIR if set, SCRATCH, fallback to TMPDIR or /tmp)
GROUNDHOG_CACHE_BASE="${GROUNDHOG_CACHE_DIR:-${SCRATCH:-${TMPDIR:-/tmp}}}"
export UV_CACHE_DIR="${GROUNDHOG_CACHE_BASE}/${USER}/uv"
export UV_PYTHON_INSTALL_DIR="${GROUNDHOG_CACHE_BASE}/${USER}/uv/python"

# Write user script
cat > user_script.py << 'USER_SCRIPT_EOF'
# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy"]
# ///

import groundhog_hpc as hog

@hog.function(endpoint="anvil")
def my_function(x):
    import numpy as np
    return np.sum(x)
USER_SCRIPT_EOF

# Write runner script (includes PEP 723 metadata)
cat > runner.py << 'RUNNER_EOF'
# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy"]
# ///

from groundhog_hpc.serialization import serialize, deserialize
from groundhog_hpc.utils import import_user_script
from operator import attrgetter

module = import_user_script("user_script", "user_script.py")

if __name__ == "__main__":
    # Read and deserialize arguments
    with open('payload.in', 'r') as f_in:
        args, kwargs = deserialize(f_in.read())

    # Get function and call it
    func = attrgetter("my_function")(module)
    result = func(*args, **kwargs)

    # Serialize and write result
    with open('payload.out', 'w') as f_out:
        f_out.write(serialize(result))
RUNNER_EOF

# Write serialized payload
cat > payload.in << 'PAYLOAD_EOF'
<base64-encoded pickled args/kwargs>
PAYLOAD_EOF

# Execute runner with uv
uv run --managed-python --with groundhog-hpc==X.Y.Z runner.py

# Print delimiter and serialized result
echo "__GROUNDHOG_RESULT__"
cat payload.out
```

Key points:

- **Runner has metadata**: The runner includes the same PEP 723 metadata as your script, so `uv` installs the correct dependencies
- **Import as module**: `import_user_script()` imports your script as a proper Python module
- **Cache directories**: Uses `$SCRATCH` or `$TMPDIR` (HPC scratch space) when defined to try and avoid NFS locking issues. The `GROUNDHOG_CACHE_DIR` variable has precedence if set, which can be useful to maximize `uv`'s cache hits.

## The Runner Script

The runner handles serialization and execution:

1. **Imports your script as a module** - Not `exec()`, which could confuse pickle
2. **Deserializes arguments** - Reads the `.in` file and unpickles args/kwargs
3. **Gets the function** - Uses `attrgetter()` to support nested names like `MyClass.my_method`
4. **Calls the function** - Executes with deserialized arguments
5. **Serializes the result** - Pickles and base64-encodes the return value
6. **Writes to `.out` file** - The shell script reads this and sends it back

This approach ensures:

- Your script's `if __name__ == "__main__"` blocks don't execute unintentionally on the remote node
- Referenced functions/objects pickle consistently with their module path

## Local Execution

`.local()` uses the exact same mechanism as `.remote()`, but executes the shell script in a local subprocess instead of submitting to Globus Compute:

```python
# Same execution flow, different location
result = func.remote(arg)  # Runs on HPC cluster via Globus Compute
result = func.local(arg)   # Runs in local subprocess
```

This makes `.local()` useful for testing without HPC access, running functions with incompatible dependencies, or just sanity-checking a function before submitting it to the remote endpoint.

## Next Steps

- **[Serialization](serialization.md)** - How arguments and results are serialized
- **[Configuration Example](../examples/configuration.md)** - See how and where execution can be configured
- **[Local Execution Example](../examples/local.md)** - Try `.local()` without HPC access
