# AWS EC2 Execution Guide — EDGAR Production Pipeline

**Run EDGAR extraction on AWS EC2 with automatic data logging + 15-min Dropbox backup.**

---

## ✅ Prerequisites

```bash
# Install AWS CLI (if needed)
brew install awscli

# Configure AWS credentials
aws configure --profile default
# Enter:
#   AWS Access Key ID: [your-key]
#   AWS Secret Access Key: [your-secret]
#   Default region: us-east-1
#   Default output: json

# Verify credentials
aws ec2 describe-instances --profile default --region us-east-1

# Install rclone for Dropbox sync
brew install rclone

# Configure Dropbox in rclone
rclone config
# Select: Dropbox
# Follow OAuth flow
```

---

## 🚀 Step 1: Launch EC2 Instance

```bash
# List available instances
aws ec2 describe-instances \
  --profile default \
  --region us-east-1 \
  --filters "Name=instance-state-name,Values=running" \
  --query "Reservations[].Instances[].[InstanceId,Tags[?Key=='Name'].Value|[0],InstanceType,PublicIpAddress]" \
  --output table

# Or launch a new instance if needed
aws ec2 run-instances \
  --profile default \
  --region us-east-1 \
  --image-id ami-0c55b159cbfafe1f0 \
  --instance-type t3.xlarge \
  --key-name market-pipeline \
  --security-group-ids sg-12345678 \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=edgar-processor}]" \
  --user-data file://~/install-edgar.sh

# Get instance ID
INSTANCE_ID=$(aws ec2 describe-instances \
  --profile default \
  --region us-east-1 \
  --filters "Name=tag:Name,Values=edgar-processor" "Name=instance-state-name,Values=running" \
  --query "Reservations[0].Instances[0].InstanceId" \
  --output text)

echo "Instance ID: $INSTANCE_ID"
```

---

## 🔗 Step 2: Copy Scripts to EC2

```bash
# First, SCP the Python scripts to EC2
INSTANCE_ID="i-1234567890abcdef0"  # From above

# Copy all EDGAR scripts
aws ssm send-command \
  --profile default \
  --region us-east-1 \
  --document-name "AWS-RunShellScript" \
  --targets "Key=instanceids,Values=$INSTANCE_ID" \
  --parameters 'commands=[
    "cd /home/ec2-user",
    "git clone https://github.com/herrrickshaw/market-pipeline.git",
    "cd market-pipeline/code/python_files",
    "python3 -m pip install -q yfinance pandas numpy",
    "echo \"✓ Setup complete\""
  ]'

# OR manually SCP (if instance has SSH key)
scp -i ~/.ssh/market-pipeline.pem \
  edgar_production_full.py \
  ec2-user@instance-ip:/home/ec2-user/market-pipeline/code/python_files/
```

---

## 🏃 Step 3: Run Extraction on EC2

### Option A: Interactive Session (Real-time Monitoring)

```bash
INSTANCE_ID="i-1234567890abcdef0"

# Start session (requires EC2 Instance Connect enabled)
aws ssm start-session \
  --profile default \
  --region us-east-1 \
  --target $INSTANCE_ID

# Inside session:
cd /home/ec2-user/market-pipeline/code/python_files
python3 edgar_production_full.py --workers 8 --symbols-limit 2200

# Logs stream to CloudWatch
```

### Option B: Send Command (Background Execution)

```bash
INSTANCE_ID="i-1234567890abcdef0"

# Submit extraction as background command
aws ssm send-command \
  --profile default \
  --region us-east-1 \
  --document-name "AWS-RunShellScript" \
  --targets "Key=instanceids,Values=$INSTANCE_ID" \
  --parameters 'commands=[
    "cd /home/ec2-user/market-pipeline/code/python_files",
    "nohup python3 edgar_production_full.py --workers 8 --symbols-limit 2200 > extraction.log 2>&1 &",
    "echo \"Extraction started. Monitor with: tail -f extraction.log\""
  ]' \
  --output text

# Get command ID
COMMAND_ID=$(aws ssm send-command ... --query 'Command.CommandId' --output text)

# Monitor command status
aws ssm get-command-invocation \
  --profile default \
  --region us-east-1 \
  --command-id $COMMAND_ID \
  --instance-id $INSTANCE_ID
```

### Option C: With Data Logger + Dropbox Sync (Recommended)

```bash
INSTANCE_ID="i-1234567890abcdef0"

# Run with data logger + Dropbox backup
aws ssm send-command \
  --profile default \
  --region us-east-1 \
  --document-name "AWS-RunShellScript" \
  --targets "Key=instanceids,Values=$INSTANCE_ID" \
  --parameters 'commands=[
    "cd /home/ec2-user/market-pipeline/code/python_files",
    "nohup python3 edgar_aws_runner.py --local --symbols-limit 2200 > edgar_runner.log 2>&1 &",
    "echo \"✓ Extraction + Dropbox sync started (every 15 min)\""
  ]'
```

---

## 📊 Step 4: Monitor Progress

### Monitor Logs (Real-time)

```bash
INSTANCE_ID="i-1234567890abcdef0"

# Tail extraction log
aws ssm send-command \
  --profile default \
  --region us-east-1 \
  --document-name "AWS-RunShellScript" \
  --targets "Key=instanceids,Values=$INSTANCE_ID" \
  --parameters 'commands=["tail -50f /home/ec2-user/market-pipeline/code/python_files/extraction.log"]'

# Or SSH and tail directly
ssh -i ~/.ssh/market-pipeline.pem ec2-user@instance-ip
tail -f /home/ec2-user/market-pipeline/code/python_files/reports/edgar_full_*.log
```

### Monitor Data Logger (JSON Progress)

```bash
# Watch JSON progress in real-time
aws ssm send-command \
  --profile default \
  --region us-east-1 \
  --document-name "AWS-RunShellScript" \
  --targets "Key=instanceids,Values=$INSTANCE_ID" \
  --parameters 'commands=[
    "tail -f /home/ec2-user/market-pipeline/code/python_files/reports/edgar_progress_*.json | jq ."
  ]'
```

### Check CloudWatch Metrics

```bash
# View EC2 CPU/Memory utilization
aws cloudwatch get-metric-statistics \
  --profile default \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --dimensions Name=InstanceId,Value=$INSTANCE_ID \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average
```

---

## 💾 Step 5: Dropbox Auto-Sync

### First-time Setup

```bash
# On EC2 instance, configure rclone
ssh -i ~/.ssh/market-pipeline.pem ec2-user@instance-ip
rclone config

# Select: Dropbox
# Click OAuth link, authorize
# Verify: rclone listremotes
```

### Automatic Sync (Every 15 Minutes)

The `edgar_aws_runner.py` script includes built-in Dropbox sync:

```bash
# Start with Dropbox sync
python3 edgar_aws_runner.py --local

# Files sync to: dropbox:/market-data/edgar/
# Automatically syncs every 15 minutes

# Monitor sync status
tail -f /home/ec2-user/market-pipeline/code/python_files/reports/edgar_metrics_*.log
```

---

## ⬇️ Step 6: Download Results to Local

```bash
INSTANCE_ID="i-1234567890abcdef0"
INSTANCE_IP=$(aws ec2 describe-instances \
  --profile default \
  --region us-east-1 \
  --instance-ids $INSTANCE_ID \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)

# Download CQL batches
scp -r -i ~/.ssh/market-pipeline.pem \
  ec2-user@$INSTANCE_IP:/home/ec2-user/market-pipeline/code/python_files/reports/edgar_cassandra_batch_*.cql \
  ./reports/

# Download JSON results
scp -r -i ~/.ssh/market-pipeline.pem \
  ec2-user@$INSTANCE_IP:/home/ec2-user/market-pipeline/code/python_files/reports/edgar_production_results_*.json \
  ./reports/

# Or just grab from Dropbox (files auto-synced)
rclone copy dropbox:/market-data/edgar/ ./reports/
```

---

## 🗑️ Step 7: Cleanup

```bash
INSTANCE_ID="i-1234567890abcdef0"

# Terminate instance when done
aws ec2 terminate-instances \
  --profile default \
  --region us-east-1 \
  --instance-ids $INSTANCE_ID

# Verify termination
aws ec2 describe-instances \
  --profile default \
  --region us-east-1 \
  --instance-ids $INSTANCE_ID \
  --query 'Reservations[0].Instances[0].State.Name'
```

---

## 🔧 Troubleshooting

| Issue | Solution |
|-------|----------|
| SSM permission denied | Add IAM policy: `AmazonSSMManagedInstanceCore` |
| Instance can't connect to Dropbox | Check EC2 security group outbound rules (allow HTTPS) |
| Extraction slow on EC2 | Increase instance type (t3.xlarge → t3.2xlarge) or workers |
| Dropbox sync failing | Re-configure: `rclone config` and re-authorize |
| EC2 too expensive | Use spot instances: add `--instance-market-options "MarketType=spot"` |

---

## 📋 Complete Command List

```bash
# Setup
aws configure --profile default
rclone config

# Launch
aws ec2 run-instances --profile default --region us-east-1 --image-id ami-0c55b159cbfafe1f0 --instance-type t3.xlarge

# Run extraction
aws ssm send-command --profile default --region us-east-1 \
  --document-name "AWS-RunShellScript" \
  --targets "Key=instanceids,Values=$INSTANCE_ID" \
  --parameters 'commands=["python3 edgar_aws_runner.py --local"]'

# Monitor
aws ssm start-session --profile default --region us-east-1 --target $INSTANCE_ID
tail -f /home/ec2-user/market-pipeline/code/python_files/reports/edgar_progress_*.json

# Download
scp -r ec2-user@$INSTANCE_IP:/home/ec2-user/market-pipeline/code/python_files/reports/ ./

# Cleanup
aws ec2 terminate-instances --profile default --region us-east-1 --instance-ids $INSTANCE_ID
```

---

## 📈 Cost Estimation

| Component | Type | Cost | Duration |
|-----------|------|------|----------|
| **EC2** | t3.xlarge | $0.1664/hr | 6-8 hrs = ~$1.00-1.33 |
| **Data transfer** | Out (to Dropbox) | $0.09/GB | ~0.5 GB = ~$0.05 |
| **CloudWatch logs** | Storage | $0.03/GB | ~0.1 GB = ~$0.003 |
| **Total** | - | - | **~$1.05** |

Spot instance (70% discount): **~$0.30-0.40**

---

**Last Updated**: 2026-07-28  
**Status**: ✅ Ready for AWS Execution  
**Expected Timeline**: 6-8 hours (extraction + sync)

