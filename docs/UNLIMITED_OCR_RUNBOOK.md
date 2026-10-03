# Unlimited-OCR Runbook — bringing up the endpoint & OCR-ing a document

The model (baidu/Unlimited-OCR, arXiv:2606.23050) needs an NVIDIA GPU, so it is
served remotely and reached via `UNLIMITED_OCR_URL`. Two ways to bring it up.

---

## Path A — Google Colab (free T4)

1. Open the notebook (already on GitHub):
   https://colab.research.google.com/github/herrrickshaw/global-market-research-platform/blob/claude/strategy-pipeline/ocr/serve/serve_unlimited_ocr_colab.ipynb
2. Runtime → Change runtime type → **T4 GPU** → Save.
3. Runtime → **Run all** (click "Run anyway" on the not-authored-by-Google warning).
4. Wait ~10–15 min (pip install + weight download). The last cell prints:
   `UNLIMITED_OCR_URL = https://<random>.trycloudflare.com`
5. Known failure modes (hit on 2026-07-29):
   - **Runtime crash during vLLM load** → the notebook's launch cell is already
     tuned (8K ctx, eager, 0.85 GPU util); if it still crashes, lower
     `--max-model-len` to 4096.
   - **Reassigned a CPU VM after a crash** (`nvidia-smi: command not found`) →
     Runtime → Change runtime type → re-select T4 → Save → Run all again.
   - **Stuck at "Connecting / Initializing T4"** → free-tier GPU throttle;
     wait it out (minutes to ~1 h) or use Path B.
6. Keep the tab open while using the endpoint (free tier disconnects after a
   few hours; rerun when needed).

## Path B — AWS EC2 spot GPU (~$0.20/hr, reliable)

**One-time unblock:** account 120354379043 is on the AWS *Free plan*, which
refuses non-free instance types. Upgrade (root user only, no charge by itself):
https://console.aws.amazon.com/billing/home#/account → "Account plan" →
**Upgrade to Paid plan**.

Already staged (created 2026-07-29, all free while idle):
- Key pair `unlimited-ocr` → `~/.ssh/unlimited-ocr.pem`
- Security group `sg-0a712e70271b195cc` — ports 22/8000 open ONLY to your IP
  (update with `aws ec2 authorize-security-group-ingress` if your IP changes)
- AMI `ami-02c52c305263fdec5` (Deep Learning Base OSS Nvidia, Ubuntu 22.04)

Launch (user-data boots vLLM in docker automatically):

```bash
aws ec2 run-instances --region us-east-1 --instance-type g4dn.xlarge \
  --image-id ami-02c52c305263fdec5 --key-name unlimited-ocr \
  --security-group-ids sg-0a712e70271b195cc \
  --instance-market-options '{"MarketType":"spot"}' \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":100,"VolumeType":"gp3"}}]' \
  --user-data '#!/bin/bash
docker run -d --gpus all -p 8000:8000 --restart unless-stopped --name ocr \
  vllm/vllm-openai:unlimited-ocr \
  --model baidu/Unlimited-OCR --trust-remote-code \
  --limit-mm-per-prompt '"'"'{"image": 32}'"'"' --max-model-len 16384 \
  --gpu-memory-utilization 0.9' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=unlimited-ocr}]'
```

Then: get the public IP (`aws ec2 describe-instances --filters
Name=tag:Name,Values=unlimited-ocr Name=instance-state-name,Values=running
--query 'Reservations[].Instances[].PublicIpAddress' --output text`),
wait ~8–10 min for the docker image + weights, endpoint is `http://<ip>:8000`.

**Teardown when done (spot = terminate, not stop):**
```bash
aws ec2 terminate-instances --instance-ids <id> --region us-east-1
```

---

## Using the endpoint (either path)

1. Put the URL in `~/.config/market-secrets/credentials.env`:
   `UNLIMITED_OCR_URL=https://... (or http://<ec2-ip>:8000)`
2. Verify: `cd ~ && python3 -m ocr --ping`
3. OCR anything: `python3 -m ocr some_scanned.pdf -o out.md`
4. Re-parse the MANAS factsheet (scanned attachment auto-OCRs now):
   `cd ~/india-trade-sector-policy-recommendations && python3 scripts/pib_factsheets.py --id 150669`

Client tuning env vars: `UNLIMITED_OCR_PAGES_PER_CALL` (default 8),
`UNLIMITED_OCR_DPI` (170), `UNLIMITED_OCR_TIMEOUT` (600s).
Never commit a tunnel/EC2 URL — endpoints are ephemeral and live only in
credentials.env.
