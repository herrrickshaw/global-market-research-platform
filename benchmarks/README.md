# Token Optimizer Benchmark Suite

Comprehensive benchmark validation for token optimization across 100+ diverse documents.

---

## 📊 Overview

This benchmark suite validates the token compression claims of the Token Optimizer system across multiple file types and document sources.

**Claim**: 55-75% token reduction through file conversion to markdown

**Method**: Measure actual token count before/after conversion for 100+ documents

**Results**: See `results/benchmark_*.json` and `results/benchmark_*.md`

---

## 📁 Directory Structure

```
benchmarks/
├── pdfs/              # PDF documents (20 files)
├── docx/              # Word documents (20 files)
├── json/              # JSON files (20 files)
├── html/              # HTML files (20 files)
├── code/              # Code files (20 files)
├── results/           # Benchmark results (JSON + markdown)
├── README.md          # This file
└── run_benchmark.py   # Benchmark runner script
```

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Install markitdown (required)
pipx install markitdown

# Install optional token counter (for accuracy)
pip install tiktoken
```

### 2. Populate Benchmark Dataset

```bash
# Copy sample documents to each directory
# You can use:
# - ArXiv papers (pdfs)
# - GitHub documentation (docx, markdown)
# - API schemas (json)
# - Public websites (html)
# - Open-source projects (code)

# Or run the setup script (if available):
python setup_benchmark_dataset.py
```

### 3. Run Benchmark

```bash
python run_benchmark.py

# Custom output directory:
python run_benchmark.py --output-dir ~/results
```

### 4. Review Results

Results are saved to `results/benchmark_YYYYMMDD_HHMMSS.json` and `.md`

```bash
# View markdown report
cat results/benchmark_*.md

# View JSON details
jq '.aggregate' results/benchmark_*.json
```

---

## 📚 Sample Dataset Sources

### PDFs (20 files)
- **ArXiv papers**: https://arxiv.org (CS, ML categories)
- **Legal documents**: Public SEC filings, legal templates
- **Annual reports**: Public company reports (10-50 pages)
- **Research papers**: NIPS, ICML proceedings
- **Technical books**: Open-source documentation PDFs

### DOCX (20 files)
- **GitHub documentation**: README.md exported to DOCX
- **Technical specifications**: System design documents
- **Project proposals**: RFP/RFI documents
- **Meeting minutes**: Sample meeting notes
- **Project plans**: Project planning templates

### JSON (20 files)
- **API schemas**: OpenAI, Stripe, GitHub APIs
- **Large nested objects**: Complex configurations
- **Flattened data**: Export from databases
- **Logs**: Structured logs with many fields
- **Datasets**: Sample JSON datasets from Kaggle

### HTML (20 files)
- **Wikipedia articles**: Full article HTML
- **Technical blogs**: Hacker News articles
- **Documentation**: MDN, developer.mozilla.org
- **News articles**: Public news websites
- **E-commerce**: Sample product pages

### Code (20 files)
- **Python scripts**: Flask/Django apps (1-5k LOC)
- **JavaScript**: React components, Node.js modules
- **Go**: Microservices, CLI tools
- **SQL**: Database schemas and queries
- **Configuration**: Docker, Kubernetes YAML

---

## 📊 Expected Results

Based on prior measurements:

| File Type | Expected Compression | Reasoning |
|-----------|----------------------|-----------|
| PDF | 60-70% | Text extraction + formatting removal |
| DOCX | 65-75% | XML structure overhead |
| JSON | 70-80% | Structural simplification |
| HTML | 65-75% | Tag removal + content extraction |
| Code | 75-85% | Comments + indentation, preserved structure |
| **Overall** | **65-75%** | Mix of all types |

---

## 🔍 Methodology

### Token Counting

**Default**: Approximate (1 token ≈ 4 characters)  
**With tiktoken**: Exact OpenAI tokenizer

To use exact token counting:
```bash
pip install tiktoken
python run_benchmark.py  # Automatically uses tiktoken if available
```

### Conversion

All files are converted using `markitdown.convert()` (same as Token Optimizer)

### Metrics Recorded

- **Original tokens**: Tokens in original file
- **Markdown tokens**: Tokens in markdown output
- **Compression ratio**: (original - markdown) / original
- **Conversion time**: Time to convert (milliseconds)
- **File size** (bytes): Before/after

---

## 📈 Interpreting Results

### Compression Ratio > 75%

✅ **Better than claimed** (claim is 55-75%)  
- File type may compress better than average
- Example: Code files often >80%

### Compression Ratio 55-75%

✅ **Within claimed range**  
- Expected for most document types
- This is the target range

### Compression Ratio < 55%

⚠️ **Below claimed range**  
- File type may not compress well
- Example: Already-compressed JSON may only compress 40%
- Reason: File type lacks structure to optimize

### Compression Ratio Negative

❌ **Markdown larger than original**  
- Markdown representation added overhead
- Typical for: Already-compressed files, small files
- Action: Don't convert these files

---

## 🛠️ Customization

### Add Custom File Type

```bash
# Create new directory
mkdir benchmarks/videos

# Add sample files
cp /path/to/videos/*.mp4 benchmarks/videos/

# Run benchmark (will include videos)
python run_benchmark.py
```

### Change Token Counter

```python
# In run_benchmark.py, modify count_tokens()
def count_tokens(self, text: str, model: str = 'claude-3-5-sonnet-20241022') -> int:
    # Use Claude's token counter instead
    # import anthropic
    # ...
```

### Adjust Benchmark Size

```bash
# Test with smaller dataset (5 files per type)
# Move most files to a backup directory
# Run: python run_benchmark.py
```

---

## 📋 Validation Checklist

- [ ] All 5 file type directories populated (20 files each)
- [ ] Markitdown installed (`pipx install markitdown`)
- [ ] Tiktoken installed for accuracy (`pip install tiktoken`)
- [ ] Benchmark runs without errors
- [ ] Results saved to `results/` directory
- [ ] Overall compression within 55-75% range
- [ ] Markdown report generated

---

## 🔗 Related Documents

- [Token Optimizer System](../.claude/SYSTEM_WIDE_SETUP.md)
- [Feature Implementation Plan](../.claude/FEATURE_IMPLEMENTATION_PLAN.md)
- [Competitive Analysis](../.claude/COMPETITIVE_COMPARISON.md)

---

## 📞 Support

If benchmark fails:

1. **Check markitdown is installed**: `which markitdown`
2. **Check sample files exist**: `ls benchmarks/pdfs/` (should not be empty)
3. **Check Python version**: `python3 --version` (need 3.8+)
4. **Review error output**: Errors logged to console

For detailed debugging:
```bash
python run_benchmark.py --verbose
python -c "import markitdown; print(markitdown.__version__)"
```

---

**Status**: Ready to run | **Validation**: 100 diverse documents | **Expected time**: 5-15 minutes
