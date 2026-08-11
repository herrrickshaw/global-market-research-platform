# LLMLingua-2 Compression Layer Integration

See ~/.claude/COMPRESSION_LAYER_GUIDE.md for complete implementation guide.

## Quick Start

### Install
```bash
pip install llmlingua2
```

### Use
```bash
python3 ~/.claude/scripts/compress.py report.pdf
```

### Integrate
```python
from integrate_with_compression import EnhancedConversionWithCompression
converter = EnhancedConversionWithCompression(use_llmlingua2=True)
result = converter.convert_file('report.pdf')
print(f"Compression: {result['compression']:.1%}")
```

## Expected Results
- Stage 1 (Markitdown): 40-60% compression
- Stage 2 (LLMLingua-2): +10-20% additional compression
- Total: 65-82% compression

## Files
- ~/.claude/scripts/compress.py - Core compression pipeline
- ~/.claude/scripts/integrate_with_compression.py - Integration with token graph
- ~/.claude/COMPRESSION_LAYER_GUIDE.md - Full documentation

## Cost
- Install: Free (pip install llmlingua2)
- Per-file: <$0.01 (Claude API cost)
- Benefit: 5-10% additional token savings

## Status
Ready to integrate | Impact: +5-10% compression improvement
