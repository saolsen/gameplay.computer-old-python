FROM python:3.11-slim-bullseye as build

RUN apt-get update
RUN apt-get install -y --no-install-recommends \
    build-essential \
    curl
RUN apt-get update

# Rust
RUN curl https://sh.rustup.rs -sSf | bash -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"
RUN pip install maturin

WORKDIR /root
COPY . .
RUN maturin build --release

FROM python:3.11-slim-bullseye as prod
COPY --from=build /root/target/wheels wheels
RUN pip install --upgrade pip
RUN pip install --no-cache-dir --find-links=wheels 'gameplay_computer[web]'
CMD ["uvicorn", "gameplay_computer.web.app:app", "--proxy-headers", "--forwarded-allow-ips", "*", "--host", "0.0.0.0", "--port", "8000"]
