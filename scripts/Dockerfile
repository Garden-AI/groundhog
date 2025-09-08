FROM astral/uv:bookworm

ENV UV_MANAGED_PYTHON=1
ENV PATH="/.venv/bin:$PATH"

RUN uv venv
RUN uv pip install globus-compute-endpoint
