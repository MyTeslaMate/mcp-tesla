FROM python:3.10

WORKDIR /code

RUN apt update && apt install -y --no-install-recommends curl unzip && rm -rf /var/lib/apt/lists/*

# Deno is required by prefab_ui's server-side sandbox (generative_generate_prefab_ui).
# Installed to /usr/local/bin so it's on PATH for shutil.which("deno").
RUN curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh -s -- --yes \
    && deno --version

# Install app
COPY ./requirements.txt /code/requirements.txt
RUN pip install -r /code/requirements.txt

COPY ./tesla_mcp /code/tesla_mcp

# Force prefab_ui renderer to ship the bundled (single-file) HTML instead of
# the CDN stub. Needed because the CDN stub lazy-loads recharts as a separate
# chunk, and during generative streaming the chart's ResponsiveContainer can
# capture width=0 before the chunk + parent layout settle, leaving an
# invisible chart. Bundled mode embeds recharts non-lazily so the chart
# renders deterministically. See:
# .venv/lib/python3.12/site-packages/prefab_ui/renderer/__init__.py:6
ENV PREFAB_BUNDLED_RENDERER=1

EXPOSE 80
CMD ["uvicorn", "tesla_mcp.app:app", "--host", "0.0.0.0", "--port", "80"]