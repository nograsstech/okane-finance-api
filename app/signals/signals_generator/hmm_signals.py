"""
Hidden Markov Model (HMM) signals for market regime analysis.

Based on Pine Script: "Hidden Markov Model: Regime Probability [AlgoPoint]"
Implements a 3-state HMM (Bull, Bear, Chop) with Bayesian updating.

Regime characteristics:
- Bull: Positive momentum (μ=1.0, σ=1.0), lower volatility (μ=-0.5, σ=1.0)
- Bear: Negative momentum (μ=-1.0, σ=1.0), higher volatility (μ=1.0, σ=1.0)
- Chop: Low momentum (μ=0.0, σ=0.5), high volatility (μ=1.5, σ=1.0)
"""

import numpy as np
import pandas as pd
import pandas_ta as ta
from typing import Literal


# Regime parameters (mean and std for both momentum and volatility)
REGIME_PARAMS = {
    'bull': {'mom_mu': 1.0, 'mom_sigma': 1.0, 'vol_mu': -0.5, 'vol_sigma': 1.0},
    'bear': {'mom_mu': -1.0, 'mom_sigma': 1.0, 'vol_mu': 1.0, 'vol_sigma': 1.0},
    'chop': {'mom_mu': 0.0, 'mom_sigma': 0.5, 'vol_mu': 1.5, 'vol_sigma': 1.0},
}


def gaussian_pdf(x: float, mu: float, sigma: float) -> float:
    """
    Calculate Gaussian probability density function.

    Formula: (1 / sqrt(2πσ²)) * exp(-(x-μ)² / (2σ²))

    Args:
        x: Input value
        mu: Mean
        sigma: Standard deviation

    Returns:
        Probability density value
    """
    var = sigma ** 2
    if var == 0:
        return 0.0
    return (1.0 / np.sqrt(2.0 * np.pi * var)) * np.exp(-(x - mu) ** 2 / (2.0 * var))


def calculate_hmm_regime(
    df: pd.DataFrame,
    length: int = 20,
    p_stay_bull: float = 0.80,
    p_stay_bear: float = 0.80,
    p_stay_chop: float = 0.60,
) -> pd.DataFrame:
    """
    Calculate HMM regime probabilities for market data.

    This function implements the Hidden Markov Model regime detection algorithm.
    It calculates two observables (momentum and volatility), computes likelihoods
    for each regime, and applies Bayesian updating with a transition matrix.

    Args:
        df: DataFrame with OHLCV data (must have 'Close', 'High', 'Low' columns)
        length: Lookback period for observable calculations (default: 20)
        p_stay_bull: Probability of staying in bull regime (default: 0.80)
        p_stay_bear: Probability of staying in bear regime (default: 0.80)
        p_stay_chop: Probability of staying in chop regime (default: 0.60)

    Returns:
        DataFrame with additional columns:
        - obs_momentum: Standardized momentum observable
        - obs_volatility: Standardized volatility observable
        - prob_bull: Bull regime probability (0-100)
        - prob_bear: Bear regime probability (0-100)
        - prob_chop: Chop regime probability (0-100)
        - regime_state: Dominant regime (1=bull, -1=bear, 0=chop)
        - regime: Dominant regime name ('bull', 'bear', 'chop')
        - confidence: Confidence score (max probability)

    Raises:
        ValueError: If required columns are missing or insufficient data
    """
    # Validate input
    required_cols = ['Close', 'High', 'Low']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    if len(df) < length + 1:
        raise ValueError(f"Insufficient data: need at least {length + 1} rows, got {len(df)}")

    df = df.copy()

    # ==========================================
    # Observable 1: Momentum
    # ==========================================
    # Calculate rate of change
    mom_raw = ta.roc(df['Close'], length=1)

    # Smooth with EMA
    mom_smooth = ta.ema(mom_raw, length=length)

    # Standardize: (value - mean) / std
    mom_std = ta.stdev(mom_smooth, length=length)
    mom_mean = ta.sma(mom_smooth, length=length)
    df['obs_momentum'] = (mom_std != 0).astype(float) * ((mom_smooth - mom_mean) / mom_std)
    df['obs_momentum'] = df['obs_momentum'].fillna(0.0)

    # ==========================================
    # Observable 2: Volatility
    # ==========================================
    # Calculate ATR
    vol_raw = ta.atr(df['High'], df['Low'], df['Close'], length=length)

    # Standardize
    vol_std = ta.stdev(vol_raw, length=length)
    vol_mean = ta.sma(vol_raw, length=length)
    df['obs_volatility'] = (vol_std != 0).astype(float) * ((vol_raw - vol_mean) / vol_std)
    df['obs_volatility'] = df['obs_volatility'].fillna(0.0)

    # ==========================================
    # Calculate Likelihoods for Each Regime
    # ==========================================
    bull_params = REGIME_PARAMS['bull']
    bear_params = REGIME_PARAMS['bear']
    chop_params = REGIME_PARAMS['chop']

    df['like_bull'] = (
        gaussian_pdf(df['obs_momentum'], bull_params['mom_mu'], bull_params['mom_sigma']) *
        gaussian_pdf(df['obs_volatility'], bull_params['vol_mu'], bull_params['vol_sigma'])
    )

    df['like_bear'] = (
        gaussian_pdf(df['obs_momentum'], bear_params['mom_mu'], bear_params['mom_sigma']) *
        gaussian_pdf(df['obs_volatility'], bear_params['vol_mu'], bear_params['vol_sigma'])
    )

    df['like_chop'] = (
        gaussian_pdf(df['obs_momentum'], chop_params['mom_mu'], chop_params['mom_sigma']) *
        gaussian_pdf(df['obs_volatility'], chop_params['vol_mu'], chop_params['vol_sigma'])
    )

    # ==========================================
    # Bayesian HMM Update
    # ==========================================
    # Initialize equal probabilities
    prob_bull = 1/3.0
    prob_bear = 1/3.0
    prob_chop = 1/3.0

    # Calculate transition probabilities
    trans_bull_bear = (1.0 - p_stay_bull) * 0.2
    trans_bull_chop = (1.0 - p_stay_bull) * 0.8
    trans_bear_bull = (1.0 - p_stay_bear) * 0.2
    trans_bear_chop = (1.0 - p_stay_bear) * 0.8
    trans_chop_bull = (1.0 - p_stay_chop) * 0.5
    trans_chop_bear = (1.0 - p_stay_chop) * 0.5

    # Lists to store results
    bull_probs = []
    bear_probs = []
    chop_probs = []

    # Iterate through each row
    for _, row in df.iterrows():
        # Calculate priors using transition matrix
        prior_bull = (prob_bull * p_stay_bull) + (prob_bear * trans_bear_bull) + (prob_chop * trans_chop_bull)
        prior_bear = (prob_bull * trans_bull_bear) + (prob_bear * p_stay_bear) + (prob_chop * trans_chop_bear)
        prior_chop = (prob_bull * trans_bull_chop) + (prob_bear * trans_bear_chop) + (prob_chop * p_stay_chop)

        # Calculate posteriors (likelihood * prior)
        like_bull = row['like_bull']
        like_bear = row['like_bear']
        like_chop = row['like_chop']

        post_bull = prior_bull * like_bull
        post_bear = prior_bear * like_bear
        post_chop = prior_chop * like_chop

        # Normalize
        total_post = post_bull + post_bear + post_chop
        if total_post > 0:
            prob_bull = post_bull / total_post
            prob_bear = post_bear / total_post
            prob_chop = post_chop / total_post

        bull_probs.append(prob_bull * 100)
        bear_probs.append(prob_bear * 100)
        chop_probs.append(prob_chop * 100)

    df['prob_bull'] = bull_probs
    df['prob_bear'] = bear_probs
    df['prob_chop'] = chop_probs

    # ==========================================
    # Determine Dominant State
    # ==========================================
    def get_regime_state(row: pd.Series) -> tuple[int, str]:
        """Determine dominant regime from probabilities."""
        pct_bull = row['prob_bull']
        pct_bear = row['prob_bear']
        pct_chop = row['prob_chop']

        if pct_bull > pct_bear and pct_bull > pct_chop:
            return 1, 'bull'
        elif pct_bear > pct_bull and pct_bear > pct_chop:
            return -1, 'bear'
        else:
            return 0, 'chop'

    regime_results = df.apply(get_regime_state, axis=1, result_type='expand')
    df['regime_state'] = regime_results[0]
    df['regime'] = regime_results[1]

    # Calculate confidence score (max probability)
    df['confidence'] = df[['prob_bull', 'prob_bear', 'prob_chop']].max(axis=1)

    return df


def hmm_to_signal(df: pd.DataFrame, bullish_threshold: float = 60.0) -> pd.DataFrame:
    """
    Convert HMM regime probabilities to trading signals.

    Signal values:
    - 2: Buy signal (bull regime with high confidence)
    - 1: Sell signal (bear regime with high confidence)
    - 0: No signal (chop or low confidence)

    Args:
        df: DataFrame with HMM regime probabilities (from calculate_hmm_regime)
        bullish_threshold: Minimum bull probability to trigger buy signal (default: 60)

    Returns:
        DataFrame with additional 'HMMSignal' column (0/1/2)
    """
    df = df.copy()

    def get_signal(row: pd.Series) -> int:
        if row['prob_bull'] >= bullish_threshold:
            return 2  # Buy signal
        elif row['prob_bear'] >= bullish_threshold:
            return 1  # Sell signal
        else:
            return 0  # No signal

    df['HMMSignal'] = df.apply(get_signal, axis=1)

    return df
