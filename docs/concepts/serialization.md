# Serialization

Groundhog serializes function arguments and results to send them between processes. Understanding serialization helps you avoid common errors and handle large data efficiently.

## Serialization Roundtrip

Serialization happens in a roundtrip process between your local Python process and the remote execution environment:

### 1. Arguments: Original Process -> Shell Script

When you call `result = my_function.remote(x, y, z=10)`:

- Groundhog pickles `(args, kwargs)` as a tuple: `((x, y), {"z": 10})`
- Base64-encodes the pickled bytes to create a text string
- Embeds the string in the shell script as a heredoc (written to a `.in` file)

This happens identically for `.remote()`, `.submit()`, and `.local()` - all embed the serialized payload in the shell script.

### 2. Arguments: Shell Script -> Runner Process

The shell script runs (on HPC node for `.remote()`, locally for `.local()`):

- Writes the `.in` file containing the base64-encoded payload
- Executes the runner script
- Runner reads the `.in` file
- Runner base64-decodes and unpickles to get `(args, kwargs)`

### 3. Function Executes

The runner calls your function with the deserialized arguments:

```python
args, kwargs = deserialize(payload)
func = getattr(module, "function_name")
result = func(*args, **kwargs)
```

Your function executes and returns a value.

### 4. Results: Runner Process -> Shell Script

The runner serializes the return value:

- Pickles the result object
- Base64-encodes the pickled bytes
- Writes to a `.out` file
- Prints the `.out` contents to stdout

### 5. Results: Shell Script -> Original Process

The shell script completes and Groundhog captures stdout:

- Extracts the serialized result from stdout
- Base64-decodes and unpickles to restore the original object
- Returns to your calling code

This roundtrip ensures arguments and results travel safely as plain text through shell scripts and Globus Compute's transport layer.

## Size Limits

**Globus Compute has a 10 MB payload limit.** If your serialized arguments or results exceed this, remote calls fail with `PayloadTooLargeError`.

The limit applies to the serialized size, not the original object size. Pickle+b64 adds overhead, so a 5 MB NumPy array might serialize to 7-8 MB.

Check size before submission:

```python
import numpy as np

large_array = np.random.random((1000, 1000))

try:
    result = process.remote(large_array)
except PayloadTooLargeError as e:
    print(f"Payload too large: {e.size_mb:.2f} MB")
    # Use alternative approach
```

## Handling Large Data

For data exceeding the 10 MB limit, you have options:

### ProxyStore (`.local()` only)

!!! warning "Coming Soon for Remote Execution 👷🚧"
    ProxyStore integration is currently a proof-of-concept, and has only been implemented for `.local()` calls. Support for `.remote()` and `.submit()` proxying via Globus Transfer is under development.

`.local()` automatically uses ProxyStore for large data, creating an effective upper bound on the size of the shell script's embedded payload by writing data to disk and serializing a small proxy object instead. The proxy loads data on demand in the subprocess. See also: [proxystore docs](https://docs.proxystore.dev/latest/)

This happens automatically - no configuration needed:

```python
# Large data automatically uses ProxyStore
large_array = np.random.random((10000, 10000))
result = process.local(large_array)  # Works, no size limit
```

### Shared Storage (`.remote()` / `.submit()`)

For remote execution, use HPC shared filesystems:

```python
# Pass path instead of data
@hog.function(endpoint="anvil")
def process(data_path: str = "/scratch/shared/data.npy") -> float:
    import numpy as np
    data = np.load(data_path)
    return float(np.mean(data))
```


### Chunking

Split large data into smaller chunks:

```python
chunks = np.array_split(large_array, 10)
futures = [process.submit(chunk) for chunk in chunks]
results = [f.result() for f in futures]
final_result = combine(results)
```

## Best Practices

### Convert to Plain Python Types

NumPy and pandas types (for example) don't always deserialize cleanly:

```python
# Bad - returns numpy.float64
@hog.function(endpoint="anvil")
def compute_mean(data: list[float]) -> float:
    import numpy as np
    return np.mean(data)

# Better - returns plain float
@hog.function(endpoint="anvil")
def compute_mean(data: list[float]) -> float:
    import numpy as np
    return float(np.mean(data))
```

Explicit conversion to `int()`, `float()`, `list()` prevents errors.

### Test with `.local()` First

`.local()` uses the same serialization as `.remote()` but runs locally. Test serialization without HPC access:

```python
# Test locally first
result = my_function.local(args)

# If that works, remote will too (size permitting)
result = my_function.remote(args)
```

This catches serialization errors early.

## Next Steps

- **[Remote Execution Flow](remote-execution.md)**
- **[`.local()` Execution Example](../examples/local.md)**
