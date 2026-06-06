"""
Hidden Markov Model (HMM) signals for market regime analysis.

Based on Pine Script: "Hidden Markov Model: Regime Probability [AlgoPoint]"
Implements a 3-state HMM (Bull, Bear, Chop) with Bayesian updating.

Algorithm improvements over the original:
- Data-adaptive emission calibration via GaussianMixture (full covariance)
- Forward-backward smoothing for accurate historical regime labeling
- Hysteresis / minimum-dwell to suppress whipsaw on noisy probability series
- Entropy-based and margin-based confidence metrics

Regime characteristics (fallback fixed params, obs_momentum = (Close−EMA)/ATR):
- Bull: Price ≥2 ATR above trend EMA (μ=2.0, σ=1.5), any volatility, RSI above median
- Bear: Price ≥2 ATR below trend EMA (μ=-2.0, σ=1.5), any volatility, RSI below median
- Chop: Price within ±1 ATR of EMA (μ=0.0, σ=1.0), moderate volatility, RSI near median
"""

import numpy as np
import pandas as pd
import pandas_ta as ta
from scipy.stats import multivariate_normal
from sklearn.mixture import GaussianMixture

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Fallback emission params (used when adaptive calibration is disabled or fails).
# Each regime has characteristic mean and std for [momentum, volatility, RSI].
#
# Design rationale: momentum and RSI carry the directional signal; volatility
# is intentionally kept wide (sigma=2.0) so it does not override the direction.
# High-volatility bull moves and low-volatility bear grinds both exist — penalising
# a bull for having elevated ATR (vol_mu=-0.5 in the original) was the root cause
# of labelling volatile uptrends as bear/chop.
REGIME_PARAMS = {
    'bull': {
        'mom_mu':  2.0, 'mom_sigma': 1.5,  # price ~2 ATR above EMA; σ=1.5 spans the 0.5–4 range
        'vol_mu':  0.0, 'vol_sigma': 2.0,  # any volatility is compatible with bull
        'rsi_mu':  0.6, 'rsi_sigma': 1.0,  # RSI ~65, but flexible
    },
    'bear': {
        'mom_mu': -2.0, 'mom_sigma': 1.5,  # price ~2 ATR below EMA
        'vol_mu':  0.0, 'vol_sigma': 2.0,
        'rsi_mu': -0.6, 'rsi_sigma': 1.0,  # RSI ~35
    },
    'chop': {
        'mom_mu':  0.0, 'mom_sigma': 1.0,  # price within ±1 ATR of EMA
        'vol_mu':  0.5, 'vol_sigma': 1.5,  # slightly elevated volatility
        'rsi_mu':  0.0, 'rsi_sigma': 0.8,  # RSI near 50
    },
}

# Minimum observations required to attempt GMM calibration.
_MIN_OBS_FOR_CALIBRATION = 30

# Regime index ordering: [bull=0, bear=1, chop=2]
_IDX_TO_STATE = np.array([1, -1, 0], dtype=int)
_IDX_TO_NAME = ['bull', 'bear', 'chop']
_STATE_TO_NAME = {1: 'bull', -1: 'bear', 0: 'chop'}


# ---------------------------------------------------------------------------
# Public primitives
# ---------------------------------------------------------------------------

def gaussian_pdf(x: float, mu: float, sigma: float) -> float:
    """
    Gaussian probability density function (scalar, kept for backward compat).

    Formula: (1 / sqrt(2πσ²)) * exp(-(x-μ)² / (2σ²))
    """
    var = sigma ** 2
    if var == 0:
        return 0.0
    return (1.0 / np.sqrt(2.0 * np.pi * var)) * np.exp(-(x - mu) ** 2 / (2.0 * var))


def calibrate_emissions(
    obs: np.ndarray,
    random_state: int = 42,
) -> dict | None:
    """
    Fit a 3-component GaussianMixture to the observable matrix and map
    the anonymous components to bull / bear / chop by their momentum mean.

    The mapping is deterministic:
    - bear  = component with the lowest momentum mean (obs[:, 0])
    - bull  = component with the highest momentum mean
    - chop  = remaining component

    A sanity check requires the bull/bear momentum means to differ by ≥ 0.3
    standard units; if they do not, calibration is considered unreliable and
    the function falls back by returning None.

    NOTE: This calibration uses the full input series, so regime *centres* are
    defined with look-ahead relative to any single bar. This is acceptable for
    a retrospective regime dashboard. Use adaptive=False in calculate_hmm_regime
    to disable it and rely on the fixed REGIME_PARAMS instead.

    Args:
        obs: (n, 3) array of standardised [momentum, volatility, RSI] observables.
        random_state: Random seed for GaussianMixture reproducibility.

    Returns:
        dict with keys 'bull', 'bear', 'chop', each containing 'mean' (3,) and
        'cov' (3, 3) arrays; or None if calibration fails / data too short.
    """
    if len(obs) < _MIN_OBS_FOR_CALIBRATION:
        return None

    try:
        gmm = GaussianMixture(
            n_components=3,
            covariance_type='full',
            random_state=random_state,
            n_init=5,
        )
        gmm.fit(obs)

        mom_means = gmm.means_[:, 0]
        sorted_idx = np.argsort(mom_means)
        bear_idx = int(sorted_idx[0])   # lowest momentum → bear
        bull_idx = int(sorted_idx[2])   # highest momentum → bull
        chop_idx = int(sorted_idx[1])   # middle → chop

        # Both directional centroids must cross zero in the correct direction.
        # In a pure bull market all three GMM clusters may have positive means
        # (e.g. +0.3, +1.2, +2.5), so the "lowest" cluster is mislabeled BEAR
        # and the steady uptrend is emitted as bear probability. Requiring
        # bull_mean > 0 AND bear_mean < 0 ensures the GMM found genuine
        # directional separation; otherwise the fallback fixed REGIME_PARAMS
        # (bear: μ=−1.0) correctly keeps uptrend bars away from bear.
        if mom_means[bull_idx] <= 0:
            return None
        if mom_means[bear_idx] >= 0:
            return None
        if mom_means[bull_idx] - mom_means[bear_idx] < 0.3:
            return None

        return {
            'bull': {'mean': gmm.means_[bull_idx].copy(), 'cov': gmm.covariances_[bull_idx].copy()},
            'bear': {'mean': gmm.means_[bear_idx].copy(), 'cov': gmm.covariances_[bear_idx].copy()},
            'chop': {'mean': gmm.means_[chop_idx].copy(), 'cov': gmm.covariances_[chop_idx].copy()},
        }
    except Exception:
        return None


def regime_likelihoods(
    obs: np.ndarray,
    emissions: dict,
) -> np.ndarray:
    """
    Compute an (n, 3) likelihood matrix using full-covariance multivariate Gaussians.

    Columns are ordered [bull, bear, chop].

    With diagonal covariance (fallback emissions built from REGIME_PARAMS sigmas),
    this is mathematically identical to the old product-of-univariate-Gaussians
    computation, providing a zero-regression fallback.

    Args:
        obs: (n, 3) observable matrix [momentum, volatility, RSI].
        emissions: dict with keys 'bull', 'bear', 'chop', each containing
                   'mean' (3,) and 'cov' (3, 3).

    Returns:
        (n, 3) non-negative likelihood values.
    """
    n = len(obs)
    likes = np.zeros((n, 3))
    for i, regime in enumerate(_IDX_TO_NAME):
        likes[:, i] = multivariate_normal.pdf(
            obs,
            mean=emissions[regime]['mean'],
            cov=emissions[regime]['cov'],
            allow_singular=True,
        )
    return likes


def forward_backward(
    likelihoods: np.ndarray,
    transition: np.ndarray,
    init: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Scaled forward-backward algorithm for a Hidden Markov Model.

    The forward pass (α) produces **causal** posterior probabilities — identical
    to the old sequential Bayesian loop but vectorised. The backward pass (β)
    then propagates future evidence backwards to produce **smoothed** posteriors
    γ = normalise(α · β), which are more accurate for historical regime labeling.

    Convention:
    - transition[i, j] = P(state j | state i)   (row = from, col = to)
    - likelihoods[t, i] = P(obs_t | state i)

    Args:
        likelihoods: (n, 3) likelihood matrix, columns = [bull, bear, chop].
        transition:  (3, 3) transition probability matrix (rows sum to 1).
        init:        (3,)   initial state distribution.

    Returns:
        filtered: (n, 3) causal posterior probabilities (rows sum to 1).
        smoothed: (n, 3) smoothed posterior probabilities (rows sum to 1).
    """
    n, k = likelihoods.shape

    # ---- Forward pass (α) ----
    # Apply the transition matrix to `init` at t=0 to match the original
    # sequential Bayesian loop, which treated the initial [1/3,1/3,1/3] as a
    # prior distribution and always ran a prediction step before the update.
    alpha = np.empty((n, k))
    prior_0 = transition.T @ init
    alpha[0] = prior_0 * likelihoods[0]
    s = alpha[0].sum()
    if s > 0:
        alpha[0] /= s

    for t in range(1, n):
        prior = transition.T @ alpha[t - 1]   # P(s_t | x_{1:t-1})
        alpha[t] = prior * likelihoods[t]
        s = alpha[t].sum()
        if s > 0:
            alpha[t] /= s

    # ---- Backward pass (β) ----
    beta = np.ones((n, k))
    for t in range(n - 2, -1, -1):
        raw = transition @ (likelihoods[t + 1] * beta[t + 1])
        s = raw.sum()
        beta[t] = raw / s if s > 0 else np.full(k, 1.0 / k)

    # ---- Smoothed posteriors (γ = α · β, normalised) ----
    gamma = alpha * beta
    row_sums = gamma.sum(axis=1, keepdims=True)
    row_sums = np.where(row_sums > 0, row_sums, 1.0)
    smoothed = gamma / row_sums

    return alpha, smoothed


def apply_hysteresis(
    prob_matrix: np.ndarray,
    min_dwell: int = 2,
    switch_margin: float = 8.0,
) -> np.ndarray:
    """
    Apply hysteresis / minimum-dwell stabilisation to a regime probability sequence.

    A regime switch is only accepted when both conditions hold simultaneously:
    1. The new leading regime's probability exceeds the current regime's probability
       by at least `switch_margin` percentage points.
    2. The current regime has been held for at least `min_dwell` bars.

    This suppresses whipsaw caused by probabilities that hover near a decision
    boundary without materially committing to a new state.

    Args:
        prob_matrix: (n, 3) probability values in [0, 100].
                     Columns are [bull, bear, chop].
        min_dwell:   Minimum number of bars to hold a regime before it can switch.
        switch_margin: Minimum percentage-point lead the new regime must have.

    Returns:
        State-code array of shape (n,) with values 1 (bull), -1 (bear), 0 (chop).
    """
    n = len(prob_matrix)
    raw_idx = np.argmax(prob_matrix, axis=1)  # column index: 0=bull, 1=bear, 2=chop

    result_idx = np.empty(n, dtype=int)
    result_idx[0] = raw_idx[0]
    current_idx = int(raw_idx[0])
    dwell = 1

    for t in range(1, n):
        new_idx = int(raw_idx[t])
        if new_idx == current_idx:
            dwell += 1
            result_idx[t] = current_idx
        else:
            margin = prob_matrix[t, new_idx] - prob_matrix[t, current_idx]
            if dwell >= min_dwell and margin >= switch_margin:
                current_idx = new_idx
                dwell = 1
            else:
                dwell += 1
            result_idx[t] = current_idx

    return _IDX_TO_STATE[result_idx]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _fallback_emissions() -> dict:
    """Build fixed emission params from REGIME_PARAMS as diagonal-covariance Gaussians.

    The diagonal covariance makes multivariate_normal.pdf equivalent to the old
    product-of-univariate-Gaussians computation.
    """
    return {
        regime: {
            'mean': np.array([p['mom_mu'], p['vol_mu'], p['rsi_mu']]),
            'cov': np.diag([p['mom_sigma'] ** 2, p['vol_sigma'] ** 2, p['rsi_sigma'] ** 2]),
        }
        for regime, p in REGIME_PARAMS.items()
    }


def _build_transition_matrix(
    p_stay_bull: float,
    p_stay_bear: float,
    p_stay_chop: float,
) -> np.ndarray:
    """Build 3×3 transition matrix.  Row = from-state, Col = to-state.

    Off-diagonal split ratios are fixed (same as the original implementation):
    - Bull outflow: 20% → Bear, 80% → Chop
    - Bear outflow: 20% → Bull, 80% → Chop
    - Chop outflow: 50% → Bull, 50% → Bear
    """
    trans_bull_bear = (1.0 - p_stay_bull) * 0.2
    trans_bull_chop = (1.0 - p_stay_bull) * 0.8
    trans_bear_bull = (1.0 - p_stay_bear) * 0.2
    trans_bear_chop = (1.0 - p_stay_bear) * 0.8
    trans_chop_bull = (1.0 - p_stay_chop) * 0.5
    trans_chop_bear = (1.0 - p_stay_chop) * 0.5

    # Row = from-state: [bull, bear, chop]
    return np.array([
        [p_stay_bull,     trans_bull_bear, trans_bull_chop],
        [trans_bear_bull, p_stay_bear,     trans_bear_chop],
        [trans_chop_bull, trans_chop_bear, p_stay_chop     ],
    ])


def _compute_bars_in_regime(regime_states: np.ndarray) -> np.ndarray:
    """Return an integer array counting consecutive bars in the same regime."""
    n = len(regime_states)
    bars = np.ones(n, dtype=int)
    for i in range(1, n):
        if regime_states[i] == regime_states[i - 1]:
            bars[i] = bars[i - 1] + 1
    return bars


# ---------------------------------------------------------------------------
# Main API
# ---------------------------------------------------------------------------

def calculate_hmm_regime(
    df: pd.DataFrame,
    length: int = 20,
    p_stay_bull: float = 0.85,
    p_stay_bear: float = 0.85,
    p_stay_chop: float = 0.70,
    adaptive: bool = True,
    min_dwell: int = 3,
    switch_margin: float = 15.0,
) -> pd.DataFrame:
    """
    Calculate HMM regime probabilities for market data.

    Two probability streams are returned:
    - **Filtered** (prob_bull/bear/chop): causal, computed bar-by-bar from past
      data only. Suitable as a live trading signal. Never revised.
    - **Smoothed** (prob_*_smoothed): forward-backward smoothed, uses future bars
      to refine historical labels. More accurate for charting. The last bar is
      always reported from filtered to stay causal.

    Regime labels (regime / regime_state) are derived from hysteresis applied to
    the filtered probabilities, keeping labels fully causal. Smoothed probabilities
    are still returned for display purposes but do not drive the regime column.

    Args:
        df: DataFrame with OHLCV data (must have 'Close', 'High', 'Low' columns).
        length: Lookback period for observable calculations (default: 20).
        p_stay_bull: P(Bull | Bull) transition probability (default: 0.75).
        p_stay_bear: P(Bear | Bear) transition probability (default: 0.75).
        p_stay_chop: P(Chop | Chop) transition probability (default: 0.55).
        adaptive: If True, calibrate emission parameters from the data via GMM.
                  Falls back to fixed REGIME_PARAMS if calibration fails.
        min_dwell: Minimum bars to hold a regime before it can switch (default: 2).
        switch_margin: Minimum probability lead (pp) required to switch (default: 8.0).

    Returns:
        DataFrame with additional columns:
        Observables:
          obs_momentum, obs_volatility, obs_rsi
        Likelihoods (backward compat):
          like_bull, like_bear, like_chop
        Causal filtered probabilities (0-100):
          prob_bull, prob_bear, prob_chop
        Smoothed probabilities (0-100):
          prob_bull_smoothed, prob_bear_smoothed, prob_chop_smoothed
        Regime labels:
          regime_state  (1=bull, -1=bear, 0=chop)
          regime        ('bull', 'bear', 'chop')
        Confidence metrics:
          confidence        – max(filtered probs), backward compat
          confidence_entropy – (1 - H / log3) * 100, 0=uncertain, 100=certain
          confidence_margin  – top1 − top2 filtered prob (pp)
        Duration:
          bars_in_regime (bars continuously in the current regime)

    Raises:
        ValueError: If required columns are missing or insufficient data.
    """
    # ---- Input validation ----
    required_cols = ['Close', 'High', 'Low']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    min_required = max(length, 14) + max(10, length // 2) + 1
    if len(df) < min_required:
        raise ValueError(f"Insufficient data: need at least {min_required} rows, got {len(df)}")

    df = df.copy()

    # Shared normalization window (shorter than length to reduce lag)
    norm_window = max(10, length // 2)

    # ==========================================
    # Observable 1: Trend structure (EMA-relative position)
    # ==========================================
    # (Close − EMA) / ATR: how many ATR units the close is above/below the trend EMA.
    # Unlike ROC, this signal remains positive throughout a sustained uptrend even
    # during pullbacks — the close typically stays above the EMA — and only flips
    # negative when price genuinely crosses below the trend line. ROC oscillates on
    # every bar; this structural signal does not.
    ema_raw = ta.ema(df['Close'], length=length)
    atr_trend = ta.atr(df['High'], df['Low'], df['Close'], length=length)
    df['obs_momentum'] = np.where(
        atr_trend > 0,
        np.clip((df['Close'] - ema_raw) / atr_trend, -4.0, 4.0),
        0.0,
    )

    # ==========================================
    # Observable 2: Volatility
    # ==========================================
    atr_length = max(5, length // 2)
    vol_raw = ta.atr(df['High'], df['Low'], df['Close'], length=atr_length)
    vol_std = ta.stdev(vol_raw, length=norm_window)
    vol_mean = ta.sma(vol_raw, length=norm_window)
    df['obs_volatility'] = np.where(vol_std != 0, (vol_raw - vol_mean) / vol_std, np.nan)

    # ==========================================
    # Observable 3: RSI (centred at 50)
    # ==========================================
    # Fixed normalisation (÷25) preserves the directional RSI signal: RSI=75→+1,
    # RSI=25→-1. Z-scoring against a rolling window would erase a persistently
    # overbought/oversold RSI, which is exactly the bull/bear diagnostic we need.
    rsi_raw = ta.rsi(df['Close'], length=14)
    df['obs_rsi'] = (rsi_raw - 50.0) / 25.0

    # Drop warm-up rows
    df = df.dropna(subset=['obs_momentum', 'obs_volatility', 'obs_rsi']).copy()
    if len(df) == 0:
        raise ValueError("Insufficient data after removing warmup period")

    # ==========================================
    # Emission calibration
    # ==========================================
    obs = df[['obs_momentum', 'obs_volatility', 'obs_rsi']].values  # (n, 3)

    emissions: dict | None = calibrate_emissions(obs) if adaptive else None
    if emissions is None:
        emissions = _fallback_emissions()

    # ==========================================
    # Likelihoods (multivariate Gaussian)
    # ==========================================
    likes = regime_likelihoods(obs, emissions)   # (n, 3) [bull, bear, chop]
    df['like_bull'] = likes[:, 0]
    df['like_bear'] = likes[:, 1]
    df['like_chop'] = likes[:, 2]

    # ==========================================
    # Forward-backward HMM update
    # ==========================================
    transition = _build_transition_matrix(p_stay_bull, p_stay_bear, p_stay_chop)
    init = np.full(3, 1.0 / 3.0)
    filtered, smoothed = forward_backward(likes, transition, init)

    # Causal filtered probabilities (0-100) — preserves existing column names
    df['prob_bull'] = filtered[:, 0] * 100
    df['prob_bear'] = filtered[:, 1] * 100
    df['prob_chop'] = filtered[:, 2] * 100

    # Forward-backward smoothed probabilities (0-100)
    df['prob_bull_smoothed'] = smoothed[:, 0] * 100
    df['prob_bear_smoothed'] = smoothed[:, 1] * 100
    df['prob_chop_smoothed'] = smoothed[:, 2] * 100

    # ==========================================
    # Regime labels via hysteresis on filtered
    # ==========================================
    # Using filtered (causal) probabilities keeps regime labels free of look-ahead.
    # This prevents the backward pass from labeling a price rise as "bear" because
    # the smoothed pass knows a subsequent drop is coming.
    regime_states = apply_hysteresis(
        filtered * 100,
        min_dwell=min_dwell,
        switch_margin=switch_margin,
    )

    df['regime_state'] = regime_states
    df['regime'] = pd.Series(regime_states, index=df.index).map(_STATE_TO_NAME)

    # ==========================================
    # Confidence metrics
    # ==========================================
    # Max filtered probability (backward compat)
    df['confidence'] = df[['prob_bull', 'prob_bear', 'prob_chop']].max(axis=1)

    # Entropy-based confidence: (1 - H(p) / log(3)) * 100
    p_clip = np.clip(filtered, 1e-10, 1.0)
    entropy = -np.sum(p_clip * np.log(p_clip), axis=1)
    df['confidence_entropy'] = np.clip((1.0 - entropy / np.log(3)) * 100, 0.0, 100.0)

    # Margin: top-1 minus top-2 filtered probability (pp)
    sorted_probs = np.sort(filtered * 100, axis=1)
    df['confidence_margin'] = sorted_probs[:, 2] - sorted_probs[:, 1]

    # ==========================================
    # Regime duration
    # ==========================================
    df['bars_in_regime'] = _compute_bars_in_regime(regime_states)

    return df


def hmm_to_signal(df: pd.DataFrame, bullish_threshold: float = 60.0) -> pd.DataFrame:
    """
    Convert HMM regime probabilities to trading signals.

    Reads causal filtered probabilities (prob_bull / prob_bear) which are
    never revised by future data, making this safe for live signal generation.

    Signal values:
    - 2: Buy signal  (bull regime with high confidence)
    - 1: Sell signal (bear regime with high confidence)
    - 0: No signal   (chop or low confidence)

    Args:
        df: DataFrame with HMM regime probabilities (from calculate_hmm_regime).
        bullish_threshold: Minimum bull probability to trigger buy signal (default: 60).

    Returns:
        DataFrame with additional 'HMMSignal' column (0/1/2).
    """
    df = df.copy()

    def _get_signal(row: pd.Series) -> int:
        if row['prob_bull'] >= bullish_threshold:
            return 2
        if row['prob_bear'] >= bullish_threshold:
            return 1
        return 0

    df['HMMSignal'] = df.apply(_get_signal, axis=1)
    return df
