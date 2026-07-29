# Serving Unlimited-OCR (baidu/Unlimited-OCR)

Model from arXiv:2606.23050 ("Unlimited OCR Works") — R-SWA attention lets it
transcribe dozens of pages in one forward pass with a constant KV cache.
It **requires an NVIDIA GPU**, so it cannot run on this Mac. Serve it on a GPU
box behind vLLM's OpenAI-compatible API and point the local client at it.

## Option A — Google Colab (free T4, the usual path)

Open `serve_unlimited_ocr_colab.ipynb` in Colab (GPU runtime), Run All.
The last cell prints a `https://*.trycloudflare.com` URL.

## Option B — any CUDA box / EC2 GPU (g4dn/g5; needs GPU quota)

```bash
docker run --gpus all -p 8000:8000 vllm/vllm-openai:unlimited-ocr \
    --model baidu/Unlimited-OCR --trust-remote-code \
    --limit-mm-per-prompt '{"image": 32}'
```

(NSE blocks AWS IPs, but that's irrelevant here — the OCR server only receives
images from this machine, it fetches nothing from NSE.)

## Point the local client at it

Add to `~/.config/market-secrets/credentials.env` (or export in the shell):

```
UNLIMITED_OCR_URL=https://<your-tunnel-or-host>:8000
```

Verify:

```bash
cd ~ && python3 -m ocr --ping
```

Then any consumer works, e.g.:

```bash
cd ~ && python3 -m ocr Downloads/some_scanned_filing.pdf -o /tmp/out.md
```

The client (`~/ocr/unlimited_ocr.py`) batches `UNLIMITED_OCR_PAGES_PER_CALL`
pages (default 8) per request to exploit the model's long-horizon single-pass
design. All consumers treat OCR as opt-in: with `UNLIMITED_OCR_URL` unset,
pipelines behave exactly as before.
