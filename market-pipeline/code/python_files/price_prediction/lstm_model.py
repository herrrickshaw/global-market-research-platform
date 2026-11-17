"""LSTM / GRU next-day return prediction (PyTorch).

Input: sliding windows of standardised features (log return, rolling vol,
volume z-score, high-low range). Target: next-day log return. Feature scaling
is fit on the training window only — no leakage into the test period.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

torch.manual_seed(42)
DEVICE = "cpu"  # tiny nets; MPS launch overhead beats any gain


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    f = pd.DataFrame(index=df.index)
    f["ret"] = df["log_ret"]
    f["vol21"] = df["log_ret"].rolling(21).std()
    f["range"] = (df["High"] - df["Low"]) / df["Close"]
    vol_mu = df["Volume"].rolling(63).mean()
    vol_sd = df["Volume"].rolling(63).std()
    f["vol_z"] = (df["Volume"] - vol_mu) / vol_sd.replace(0, np.nan)
    f["mom5"] = df["log_ret"].rolling(5).sum()
    return f.dropna()


class SeqNet(nn.Module):
    def __init__(self, n_features: int, hidden: int = 32, cell: str = "lstm"):
        super().__init__()
        rnn_cls = nn.LSTM if cell == "lstm" else nn.GRU
        self.rnn = rnn_cls(n_features, hidden, num_layers=1, batch_first=True)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x):
        out, _ = self.rnn(x)
        return self.head(out[:, -1, :]).squeeze(-1)


def make_windows(feat: np.ndarray, target: np.ndarray, lookback: int):
    xs, ys = [], []
    for i in range(lookback, len(feat)):
        xs.append(feat[i - lookback:i])
        ys.append(target[i])
    return np.array(xs, dtype=np.float32), np.array(ys, dtype=np.float32)


class SeqModel:
    """Train-once-per-refit wrapper used by the walk-forward loop."""

    def __init__(self, cell: str = "lstm", lookback: int = 42, hidden: int = 32,
                 epochs: int = 30, lr: float = 1e-3, batch: int = 128):
        self.cell, self.lookback, self.hidden = cell, lookback, hidden
        self.epochs, self.lr, self.batch = epochs, lr, batch
        self.net: SeqNet | None = None
        self.mu = self.sd = None
        self.target_sd = 1.0

    def fit(self, feat_df: pd.DataFrame, target: pd.Series) -> "SeqModel":
        feat = feat_df.values
        self.mu, self.sd = feat.mean(0), feat.std(0) + 1e-9
        z = (feat - self.mu) / self.sd
        y = target.values
        self.target_sd = y.std() + 1e-9
        X, Y = make_windows(z, y / self.target_sd, self.lookback)
        self.net = SeqNet(feat.shape[1], self.hidden, self.cell).to(DEVICE)
        opt = torch.optim.Adam(self.net.parameters(), lr=self.lr)
        loss_fn = nn.MSELoss()
        Xt = torch.tensor(X, device=DEVICE)
        Yt = torch.tensor(Y, device=DEVICE)
        self.net.train()
        for _ in range(self.epochs):
            perm = torch.randperm(len(Xt))
            for i in range(0, len(Xt), self.batch):
                idx = perm[i:i + self.batch]
                opt.zero_grad()
                loss = loss_fn(self.net(Xt[idx]), Yt[idx])
                loss.backward()
                opt.step()
        return self

    def predict(self, feat_df: pd.DataFrame) -> pd.Series:
        """One prediction per row that has a full lookback window behind it."""
        z = (feat_df.values - self.mu) / self.sd
        X, _ = make_windows(z, np.zeros(len(z)), self.lookback)
        self.net.eval()
        with torch.no_grad():
            preds = self.net(torch.tensor(X, dtype=torch.float32, device=DEVICE))
        preds = preds.cpu().numpy() * self.target_sd
        return pd.Series(preds, index=feat_df.index[self.lookback:])
