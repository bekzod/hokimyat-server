# LAUNCH THE APP
```
  # Pull the latest changes
  git fetch origin
  git rebase origin/development

  # Build and restart the Docker Compose stack
  docker-compose down
  docker-compose up -d --build
```

# DOWNLOAD MODEL FROM HUGGING_FACE
```
  cd ./models \
  HF_HUB_ENABLE_HF_TRANSFER=1 HUGGINGFACE_TOKEN=<your-hf-token> huggingface-cli \
  download bullerwins/Llama-3.3-70B-Instruct-exl2_4.5bpw \
  --local-dir Llama-3.3-70B-Instruct-exl2_4.5bpw  \
  --cache-dir ./models/.cache \
  --local-dir-use-symlinks False
```

## Environment variables

  `true` when unset.

### docling CPU tuning

The `docling` service uses OpenMP and several runtime settings can be tuned via
your `.env` file. Recommended defaults are shown below:

```
OMP_PROC_BIND=close
OMP_PLACES=cores
KMP_BLOCKTIME=0
MALLOC_ARENA_MAX=2
TOKENIZERS_PARALLELISM=false
```

These values favour thread locality on most single-socket machines. On
multi‑socket or highly parallel systems you may achieve better throughput with
`OMP_PROC_BIND=spread` and `OMP_PLACES=threads` to distribute work across CPUs.
Increasing `KMP_BLOCKTIME` can reduce latency at the cost of higher CPU usage,
while raising `MALLOC_ARENA_MAX` and enabling `TOKENIZERS_PARALLELISM` may help
when you have ample memory and cores available.

## Running tests

Install the minimal test dependencies and run pytest:

```bash
pip install -r tests/requirements.txt
pytest -q
```
