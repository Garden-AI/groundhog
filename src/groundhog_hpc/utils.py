import groundhog_hpc


def get_groundhog_version_spec() -> str:
    """Return the current package version spec.

    Used for consistent installation across local/remote environments, e.g.:
        `uv run --with {get_groundhog_version_spec()}`
    """
    if "dev" not in groundhog_hpc.__version__:
        version_spec = f"groundhog-hpc=={groundhog_hpc.__version__}"
    else:
        # Get commit hash from e.g. "0.0.0.post11.dev0+71128ec"
        commit_hash = groundhog_hpc.__version__.split("+")[-1]
        version_spec = f"groundhog-hpc@git+https://github.com/Garden-AI/groundhog.git@{commit_hash}"

    return version_spec
