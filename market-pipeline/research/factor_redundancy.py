#!/usr/bin/env python3
"""
factor_redundancy.py — executes BACKTEST_QUEUE.md item #1 / #9: measure how
redundant the 10-factor set actually is, using the spectral method from
Halperin (2607.19005) and the m-/participation-ratio companion (2608.09641)
found by the daily literature task, applied to factor_learning.py's own
feature matrix rather than a new correlation scan.

FACTORS (factor_learning.py:37): trend, revert, mom126, mom_st, golden_cross,
breakout, lowvol, mom252, qual_mom, def_revert — all derived from ONE weekly
close panel (factor_library(close)). qual_mom and def_revert are documented
AND-combinations of two other factors each.

METHOD: build_xy(mkt) already assembles the cross-sectional feature matrix X
(n_obs x 10) used to fit the repo's own Lasso model. Take Pearson correlation
across the 10 columns, eigendecompose it (correlation matrices are PSD, use
eigvalsh), report:
  - participation ratio PR = (sum(eigvals))^2 / sum(eigvals^2)
    -- effective number of independent factors, 1 (all redundant) to 10 (all
    independent). Halperin's exact metric, applied to factors instead of
    stock returns.
  - eigenvalue entropy H and effective rank ER = exp(H) (companion metric,
    same interpretation, different sensitivity to small eigenvalues)
  - absorption ratio AR_3 = fraction of total variance in the top 3 components
  - the raw correlation matrix, so redundant PAIRS are named, not just counted

Read-only: imports factor_learning.py's build_xy but does not write to
anything it touches (cache_seed, warehouse). Writes only under research/.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/umashankar/market-pipeline/code/python_files")
import factor_learning as FL  # noqa: E402

OUT = Path(__file__).resolve().parent / "factor_redundancy.md"


def spectral_stats(corr: np.ndarray) -> dict:
    ev = np.linalg.eigvalsh(corr)
    ev = np.clip(ev, 1e-12, None)  # numerical floor, corr matrices are PSD
    ev = np.sort(ev)[::-1]
    n = len(ev)
    pr = (ev.sum() ** 2) / (ev ** 2).sum()
    p = ev / ev.sum()
    H = -(p * np.log(p)).sum()
    er = np.exp(H)
    ar3 = ev[:3].sum() / ev.sum()
    return {"eigenvalues": ev, "participation_ratio": pr, "entropy": H,
            "effective_rank": er, "absorption_ratio_3": ar3, "n_factors": n}


def main():
    lines = ["# Factor Redundancy — spectral measurement\n",
             "Executes BACKTEST_QUEUE.md #1/#9. Motivated by 2602.00196 "
             "(decorrelated signals combine well) and 2607.19005/2608.09641 "
             "(Halperin spectral method + m- participation ratio companion).\n"]
    for mkt in ["IN", "US"]:
        print(f"=== {mkt} ===")
        X, y, wk = FL.build_xy(mkt)
        df = pd.DataFrame(X, columns=FL.FACTORS)
        corr = df.corr().values
        s = spectral_stats(corr)
        print(f"  n_obs={len(df):,}, n_factors={s['n_factors']}")
        print(f"  PARTICIPATION RATIO: {s['participation_ratio']:.2f} of {s['n_factors']} "
              f"(effective independent factors)")
        print(f"  eigenvalue entropy: {s['entropy']:.3f}  effective rank (exp H): "
              f"{s['effective_rank']:.2f}")
        print(f"  absorption ratio (top 3 components): {s['absorption_ratio_3']:.1%}")
        print(f"  eigenvalues: {np.round(s['eigenvalues'], 3).tolist()}")

        cdf = pd.DataFrame(corr, index=FL.FACTORS, columns=FL.FACTORS)
        pairs = []
        for i in range(len(FL.FACTORS)):
            for j in range(i + 1, len(FL.FACTORS)):
                pairs.append((FL.FACTORS[i], FL.FACTORS[j], corr[i, j]))
        pairs.sort(key=lambda x: -abs(x[2]))
        print(f"  top 5 most correlated pairs:")
        for a, b, c in pairs[:5]:
            print(f"    {a:<12} {b:<12} r={c:+.3f}")

        lines += [
            f"\n## {mkt}\n",
            f"n_obs={len(df):,}. **Participation ratio: {s['participation_ratio']:.2f} "
            f"of {s['n_factors']}** (effective independent factors). "
            f"Effective rank (entropy-based): {s['effective_rank']:.2f}. "
            f"Absorption ratio (top 3 PCs): {s['absorption_ratio_3']:.1%}.\n",
            "\n| pair | r |\n|---|---:|\n",
        ]
        for a, b, c in pairs[:8]:
            lines.append(f"| {a} × {b} | {c:+.3f} |\n")
        lines.append(f"\n<details><summary>full correlation matrix</summary>\n\n")
        lines.append(cdf.round(3).to_markdown())
        lines.append("\n\n</details>\n")
        print()

    OUT.write_text("".join(lines))
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
