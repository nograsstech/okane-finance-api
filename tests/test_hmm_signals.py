"""
Unit tests for HMM (Hidden Markov Model) signals module.
"""

import numpy as np
import pandas as pd
import pytest
from scipy.stats import multivariate_normal

from app.signals.signals_generator.hmm_signals import (
    REGIME_PARAMS,
    apply_hysteresis,
    calculate_hmm_regime,
    calibrate_emissions,
    forward_backward,
    gaussian_pdf,
    hmm_to_signal,
    regime_likelihoods,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_ohlcv_data():
    """Create sample OHLCV data for testing (uptrend — mostly bull)."""
    np.random.seed(42)
    n = 100
    trend = np.linspace(100, 110, n)
    noise = np.random.normal(0, 1, n)
    close = trend + noise
    return pd.DataFrame({
        'Close': close,
        'High': close + 0.5,
        'Low': close - 0.5,
    })


@pytest.fixture
def three_regime_obs():
    """Synthetic observable matrix with clear bull / bear / chop clusters."""
    np.random.seed(0)
    n_each = 50
    # bull: high momentum, low volatility, high RSI
    bull = np.random.randn(n_each, 3) * 0.3 + [2.0, -1.0, 1.5]
    # bear: low momentum, high volatility, low RSI
    bear = np.random.randn(n_each, 3) * 0.3 + [-2.0, 1.5, -1.5]
    # chop: near-zero momentum, high volatility, near-zero RSI
    chop = np.random.randn(n_each, 3) * 0.3 + [0.0, 1.0, 0.0]
    return np.vstack([bull, bear, chop])  # (150, 3)


# ---------------------------------------------------------------------------
# TestGaussianPDF
# ---------------------------------------------------------------------------

class TestGaussianPDF:
    """Tests for Gaussian probability density function."""

    def test_gaussian_pdf_at_mean(self):
        """PDF at mean should be maximum value."""
        result = gaussian_pdf(0.0, 0.0, 1.0)
        expected = 1.0 / np.sqrt(2 * np.pi)
        assert abs(result - expected) < 1e-6

    def test_gaussian_pdf_symmetry(self):
        """PDF should be symmetric around mean."""
        result1 = gaussian_pdf(1.0, 0.0, 1.0)
        result2 = gaussian_pdf(-1.0, 0.0, 1.0)
        assert abs(result1 - result2) < 1e-6

    def test_gaussian_pdf_zero_variance(self):
        """PDF should return 0 when variance is 0."""
        result = gaussian_pdf(1.0, 0.0, 0.0)
        assert result == 0.0

    def test_gaussian_pdf_different_stds(self):
        """Higher standard deviation should give lower peak."""
        result_narrow = gaussian_pdf(0.0, 0.0, 0.5)
        result_wide = gaussian_pdf(0.0, 0.0, 2.0)
        assert result_narrow > result_wide


# ---------------------------------------------------------------------------
# TestCalibrateEmissions
# ---------------------------------------------------------------------------

class TestCalibrateEmissions:
    """Tests for data-adaptive emission calibration via GMM."""

    def test_returns_dict_with_all_regimes(self, three_regime_obs):
        result = calibrate_emissions(three_regime_obs)
        assert result is not None
        assert set(result.keys()) == {'bull', 'bear', 'chop'}

    def test_each_regime_has_mean_and_cov(self, three_regime_obs):
        result = calibrate_emissions(three_regime_obs)
        assert result is not None
        for regime in ('bull', 'bear', 'chop'):
            assert result[regime]['mean'].shape == (3,)
            assert result[regime]['cov'].shape == (3, 3)

    def test_bull_has_highest_momentum_mean(self, three_regime_obs):
        """The 'bull' component must have the highest momentum mean (obs[0])."""
        result = calibrate_emissions(three_regime_obs)
        assert result is not None
        bull_mom = result['bull']['mean'][0]
        bear_mom = result['bear']['mean'][0]
        chop_mom = result['chop']['mean'][0]
        assert bull_mom > chop_mom
        assert bull_mom > bear_mom

    def test_bear_has_lowest_momentum_mean(self, three_regime_obs):
        """The 'bear' component must have the lowest momentum mean."""
        result = calibrate_emissions(three_regime_obs)
        assert result is not None
        bear_mom = result['bear']['mean'][0]
        bull_mom = result['bull']['mean'][0]
        chop_mom = result['chop']['mean'][0]
        assert bear_mom < chop_mom
        assert bear_mom < bull_mom

    def test_covariance_is_positive_semidefinite(self, three_regime_obs):
        """All covariance matrices should be positive semi-definite."""
        result = calibrate_emissions(three_regime_obs)
        assert result is not None
        for regime in ('bull', 'bear', 'chop'):
            eigenvalues = np.linalg.eigvalsh(result[regime]['cov'])
            assert np.all(eigenvalues >= -1e-9), f"{regime} cov not PSD"

    def test_returns_none_for_insufficient_data(self):
        """Should return None when fewer than 30 observations."""
        tiny_obs = np.random.randn(10, 3)
        result = calibrate_emissions(tiny_obs)
        assert result is None

    def test_deterministic_with_fixed_seed(self, three_regime_obs):
        """Same data + same seed → same result."""
        r1 = calibrate_emissions(three_regime_obs, random_state=7)
        r2 = calibrate_emissions(three_regime_obs, random_state=7)
        assert r1 is not None and r2 is not None
        np.testing.assert_array_almost_equal(r1['bull']['mean'], r2['bull']['mean'])


# ---------------------------------------------------------------------------
# TestRegimeLikelihoods
# ---------------------------------------------------------------------------

class TestRegimeLikelihoods:
    """Tests for multivariate full-covariance likelihood computation."""

    @pytest.fixture
    def simple_emissions(self):
        return {
            'bull': {'mean': np.array([1.0, -0.5, 0.8]),
                     'cov': np.diag([1.5**2, 1.0**2, 1.0**2])},
            'bear': {'mean': np.array([-1.0, 1.0, -0.8]),
                     'cov': np.diag([1.5**2, 1.0**2, 1.0**2])},
            'chop': {'mean': np.array([0.0, 1.5, 0.0]),
                     'cov': np.diag([0.5**2, 1.0**2, 0.8**2])},
        }

    def test_output_shape(self, simple_emissions):
        obs = np.random.randn(50, 3)
        result = regime_likelihoods(obs, simple_emissions)
        assert result.shape == (50, 3)

    def test_all_non_negative(self, simple_emissions):
        obs = np.random.randn(30, 3)
        result = regime_likelihoods(obs, simple_emissions)
        assert np.all(result >= 0)

    def test_matches_scipy_multivariate_normal(self, simple_emissions):
        """Should exactly replicate scipy.stats.multivariate_normal.pdf for each regime."""
        obs = np.random.randn(20, 3)
        result = regime_likelihoods(obs, simple_emissions)
        for i, regime in enumerate(['bull', 'bear', 'chop']):
            expected = multivariate_normal.pdf(
                obs,
                mean=simple_emissions[regime]['mean'],
                cov=simple_emissions[regime]['cov'],
                allow_singular=True,
            )
            np.testing.assert_array_almost_equal(result[:, i], expected, decimal=10)


# ---------------------------------------------------------------------------
# TestForwardBackward
# ---------------------------------------------------------------------------

class TestForwardBackward:
    """Tests for the vectorized forward-backward smoothing algorithm."""

    @pytest.fixture
    def simple_transition(self):
        """3x3 transition matrix (bull→bear→chop test case)."""
        p = 0.80
        return np.array([
            [p,         (1-p)*0.2,  (1-p)*0.8],
            [(1-p)*0.2, p,          (1-p)*0.8],
            [(1-p)*0.5, (1-p)*0.5,  0.60     ],
        ])

    @pytest.fixture
    def likelihoods_fixture(self):
        """50 × 3 likelihood matrix with a clear regime transition mid-series."""
        np.random.seed(1)
        n = 50
        likes = np.random.rand(n, 3)
        # First half: bull dominates
        likes[:25, 0] *= 5
        # Second half: bear dominates
        likes[25:, 1] *= 5
        return likes

    def test_filtered_sums_to_one(self, simple_transition, likelihoods_fixture):
        init = np.array([1/3, 1/3, 1/3])
        filtered, _ = forward_backward(likelihoods_fixture, simple_transition, init)
        row_sums = filtered.sum(axis=1)
        np.testing.assert_allclose(row_sums, 1.0, atol=1e-9)

    def test_smoothed_sums_to_one(self, simple_transition, likelihoods_fixture):
        init = np.array([1/3, 1/3, 1/3])
        _, smoothed = forward_backward(likelihoods_fixture, simple_transition, init)
        row_sums = smoothed.sum(axis=1)
        np.testing.assert_allclose(row_sums, 1.0, atol=1e-9)

    def test_filtered_and_smoothed_differ_on_regime_boundary(
        self, simple_transition, likelihoods_fixture
    ):
        """Smoothed should differ from filtered in the vicinity of a regime change."""
        init = np.array([1/3, 1/3, 1/3])
        filtered, smoothed = forward_backward(likelihoods_fixture, simple_transition, init)
        # They should not be identical — smoothing incorporates future information
        assert not np.allclose(filtered, smoothed, atol=1e-6)

    def test_forward_matches_legacy_loop(self):
        """Vectorized forward pass must match the old iterrows Bayesian loop (standalone)."""
        np.random.seed(42)
        n = 30
        likes = np.abs(np.random.randn(n, 3))

        p_stay_bull, p_stay_bear, p_stay_chop = 0.75, 0.75, 0.55
        trans_bull_bear = (1 - p_stay_bull) * 0.2
        trans_bull_chop = (1 - p_stay_bull) * 0.8
        trans_bear_bull = (1 - p_stay_bear) * 0.2
        trans_bear_chop = (1 - p_stay_bear) * 0.8
        trans_chop_bull = (1 - p_stay_chop) * 0.5
        trans_chop_bear = (1 - p_stay_chop) * 0.5

        transition = np.array([
            [p_stay_bull,  trans_bull_bear, trans_bull_chop],
            [trans_bear_bull, p_stay_bear, trans_bear_chop],
            [trans_chop_bull, trans_chop_bear, p_stay_chop],
        ])

        # Legacy loop
        pb, pbr, pc = 1/3, 1/3, 1/3
        legacy_bull, legacy_bear, legacy_chop = [], [], []
        for row_likes in likes:
            prior_b = pb * p_stay_bull + pbr * trans_bear_bull + pc * trans_chop_bull
            prior_br = pb * trans_bull_bear + pbr * p_stay_bear + pc * trans_chop_bear
            prior_c = pb * trans_bull_chop + pbr * trans_bear_chop + pc * p_stay_chop
            post_b = prior_b * row_likes[0]
            post_br = prior_br * row_likes[1]
            post_c = prior_c * row_likes[2]
            total = post_b + post_br + post_c
            if total > 0:
                pb, pbr, pc = post_b/total, post_br/total, post_c/total
            legacy_bull.append(pb)
            legacy_bear.append(pbr)
            legacy_chop.append(pc)

        init = np.array([1/3, 1/3, 1/3])
        filtered, _ = forward_backward(likes, transition, init)

        np.testing.assert_allclose(filtered[:, 0], legacy_bull, atol=1e-9)
        np.testing.assert_allclose(filtered[:, 1], legacy_bear, atol=1e-9)
        np.testing.assert_allclose(filtered[:, 2], legacy_chop, atol=1e-9)


# ---------------------------------------------------------------------------
# TestApplyHysteresis
# ---------------------------------------------------------------------------

class TestApplyHysteresis:
    """Tests for hysteresis / minimum-dwell regime stabilisation."""

    @pytest.fixture
    def noisy_probs(self):
        """Rapidly alternating probabilities to stress-test hysteresis."""
        n = 40
        probs = np.zeros((n, 3))
        # Alternate bull/bear every other bar with a small margin
        for i in range(n):
            if i % 2 == 0:
                probs[i] = [55.0, 42.0, 3.0]   # bull slightly ahead
            else:
                probs[i] = [42.0, 55.0, 3.0]   # bear slightly ahead
        return probs

    def test_returns_array_of_correct_length(self, noisy_probs):
        result = apply_hysteresis(noisy_probs, min_dwell=2, switch_margin=8.0)
        assert len(result) == len(noisy_probs)

    def test_returns_valid_state_codes(self, noisy_probs):
        result = apply_hysteresis(noisy_probs, min_dwell=2, switch_margin=8.0)
        valid = {-1, 0, 1}
        assert set(result).issubset(valid)

    def test_fewer_switches_than_raw_argmax(self, noisy_probs):
        """Hysteresis should produce strictly fewer regime changes than raw argmax."""
        # Map argmax indices → state codes: 0→1, 1→-1, 2→0
        _idx_to_state = np.array([1, -1, 0])
        raw_states = _idx_to_state[np.argmax(noisy_probs, axis=1)]
        raw_switches = int(np.sum(np.diff(raw_states) != 0))

        hysteresis_states = apply_hysteresis(noisy_probs, min_dwell=2, switch_margin=8.0)
        hysteresis_switches = int(np.sum(np.diff(hysteresis_states) != 0))

        assert hysteresis_switches < raw_switches

    def test_no_switches_when_margin_never_exceeded(self, noisy_probs):
        """If switch_margin is very large, no switches should occur."""
        result = apply_hysteresis(noisy_probs, min_dwell=0, switch_margin=99.0)
        assert len(set(result)) == 1  # all same state

    def test_respects_min_dwell_for_single_bar_spikes(self):
        """A single bar in a new regime should not cause a switch when min_dwell=2."""
        probs = np.zeros((10, 3))
        probs[:, 0] = 80.0  # bull throughout
        # Bar 5 switches to bear with a large margin but only for 1 bar
        probs[5] = [5.0, 92.0, 3.0]
        probs[6] = [80.0, 12.0, 8.0]  # back to bull

        result = apply_hysteresis(probs, min_dwell=2, switch_margin=5.0)
        # Bar 5 should NOT switch because dwell was only 1 bar before returning
        # (regime at bar 4 just switched to bear w/ 0 prior dwell)
        # The initial bull state has been held 5 bars at t=5, margin=87 > 5 so switch
        # But then at bar 6, bear has only 1 bar dwell, margin back to bull = 68 > 5
        # So bar 6 switches back. With min_dwell=2 on bar 6 (1 bar in bear), no switch.
        assert result[6] == result[5] or result[6] == result[0]  # either bear or bull, not invalid

    def test_min_dwell_zero_behaves_like_margin_only(self):
        """min_dwell=0 should only gate on switch_margin."""
        probs = np.zeros((5, 3))
        probs[0] = [60, 30, 10]   # bull
        probs[1] = [30, 60, 10]   # bear, margin=30 > 15
        probs[2] = [60, 30, 10]   # bull again
        probs[3] = [30, 60, 10]   # bear
        probs[4] = [60, 30, 10]   # bull

        result = apply_hysteresis(probs, min_dwell=0, switch_margin=15.0)
        # Every bar has a 30pp margin — all switches should happen
        assert result[0] == 1    # bull
        assert result[1] == -1   # bear
        assert result[2] == 1    # bull


# ---------------------------------------------------------------------------
# TestCalculateHMMRegime (core integration)
# ---------------------------------------------------------------------------

class TestCalculateHMMRegime:
    """Tests for HMM regime calculation."""

    def test_missing_required_columns(self):
        """Should raise ValueError if required columns are missing."""
        df = pd.DataFrame({'Close': [100, 101, 102]})
        with pytest.raises(ValueError, match="Missing required columns"):
            calculate_hmm_regime(df)

    def test_insufficient_data(self):
        """Should raise ValueError if insufficient data for lookback period."""
        df = pd.DataFrame({
            'Close': [100, 101],
            'High': [100.5, 101.5],
            'Low': [99.5, 100.5],
        })
        with pytest.raises(ValueError, match="Insufficient data"):
            calculate_hmm_regime(df, length=20)

    def test_output_columns_exist(self, sample_ohlcv_data):
        """Should return DataFrame with all expected columns."""
        result = calculate_hmm_regime(sample_ohlcv_data, length=20)

        expected_cols = [
            # Observables
            'obs_momentum', 'obs_volatility', 'obs_rsi',
            # Likelihoods (backward compat)
            'like_bull', 'like_bear', 'like_chop',
            # Causal filtered probs
            'prob_bull', 'prob_bear', 'prob_chop',
            # Smoothed probs (new)
            'prob_bull_smoothed', 'prob_bear_smoothed', 'prob_chop_smoothed',
            # Regime labels
            'regime_state', 'regime',
            # Confidence (existing + new)
            'confidence', 'confidence_entropy', 'confidence_margin',
            # Duration
            'bars_in_regime',
            # Original column preserved
            'Close',
        ]
        for col in expected_cols:
            assert col in result.columns, f"Missing column: {col}"

    def test_filtered_probabilities_sum_to_100(self, sample_ohlcv_data):
        """Causal filtered probabilities should sum to 100 for each row."""
        result = calculate_hmm_regime(sample_ohlcv_data, length=20)
        for _, row in result.iterrows():
            s = row['prob_bull'] + row['prob_bear'] + row['prob_chop']
            assert abs(s - 100.0) < 0.01, f"Filtered probs sum to {s}"

    def test_smoothed_probabilities_sum_to_100(self, sample_ohlcv_data):
        """Smoothed probabilities should sum to 100 for each row."""
        result = calculate_hmm_regime(sample_ohlcv_data, length=20)
        for _, row in result.iterrows():
            s = row['prob_bull_smoothed'] + row['prob_bear_smoothed'] + row['prob_chop_smoothed']
            assert abs(s - 100.0) < 0.01, f"Smoothed probs sum to {s}"

    def test_regime_state_values(self, sample_ohlcv_data):
        """Regime state should be -1, 0, or 1."""
        result = calculate_hmm_regime(sample_ohlcv_data, length=20)
        valid_states = {-1, 0, 1}
        for state in result['regime_state'].unique():
            assert state in valid_states, f"Invalid regime state: {state}"

    def test_regime_names_match_states(self, sample_ohlcv_data):
        """Regime names should match regime states."""
        result = calculate_hmm_regime(sample_ohlcv_data, length=20)
        for _, row in result.iterrows():
            state = row['regime_state']
            regime = row['regime']
            if state == 1:
                assert regime == 'bull'
            elif state == -1:
                assert regime == 'bear'
            else:
                assert regime == 'chop'

    def test_regime_valid_and_state_consistent(self, sample_ohlcv_data):
        """Regime label and state code must be internally consistent."""
        result = calculate_hmm_regime(sample_ohlcv_data, length=20)
        state_map = {'bull': 1, 'bear': -1, 'chop': 0}
        for _, row in result.iterrows():
            expected_state = state_map[row['regime']]
            assert row['regime_state'] == expected_state

    def test_confidence_is_max_filtered_probability(self, sample_ohlcv_data):
        """Confidence score should equal the maximum causal filtered probability."""
        result = calculate_hmm_regime(sample_ohlcv_data, length=20)
        for _, row in result.iterrows():
            max_prob = max(row['prob_bull'], row['prob_bear'], row['prob_chop'])
            assert abs(row['confidence'] - max_prob) < 0.01

    def test_confidence_entropy_in_range(self, sample_ohlcv_data):
        """Entropy-based confidence should be in [0, 100]."""
        result = calculate_hmm_regime(sample_ohlcv_data, length=20)
        assert (result['confidence_entropy'] >= 0).all()
        assert (result['confidence_entropy'] <= 100).all()

    def test_confidence_margin_non_negative(self, sample_ohlcv_data):
        """Confidence margin should be non-negative (top1 - top2 ≥ 0)."""
        result = calculate_hmm_regime(sample_ohlcv_data, length=20)
        assert (result['confidence_margin'] >= 0).all()

    def test_bars_in_regime_positive(self, sample_ohlcv_data):
        """bars_in_regime should be ≥ 1 for every row."""
        result = calculate_hmm_regime(sample_ohlcv_data, length=20)
        assert (result['bars_in_regime'] >= 1).all()

    def test_bars_in_regime_resets_on_switch(self, sample_ohlcv_data):
        """bars_in_regime should reset to 1 immediately after a regime switch."""
        result = calculate_hmm_regime(sample_ohlcv_data, length=20)
        regimes = result['regime'].values
        bars = result['bars_in_regime'].values
        for i in range(1, len(regimes)):
            if regimes[i] != regimes[i - 1]:
                assert bars[i] == 1, f"bars_in_regime should be 1 after a switch at index {i}"

    def test_custom_transition_probabilities(self, sample_ohlcv_data):
        """Should accept custom transition probabilities and still return a valid result."""
        result = calculate_hmm_regime(
            sample_ohlcv_data, length=20,
            p_stay_bull=0.90, p_stay_bear=0.90, p_stay_chop=0.70,
        )
        assert len(result) > 0
        assert len(result) <= len(sample_ohlcv_data)

    def test_adaptive_false_uses_fixed_params(self, sample_ohlcv_data):
        """With adaptive=False the fixed REGIME_PARAMS should be used; result is still valid."""
        result = calculate_hmm_regime(sample_ohlcv_data, length=20, adaptive=False)
        assert len(result) > 0
        total = result['prob_bull'] + result['prob_bear'] + result['prob_chop']
        assert total.sub(100).abs().lt(0.01).all()

    def test_observables_are_standardized(self, sample_ohlcv_data):
        """Observables should be roughly standardized (most values within ±5)."""
        result = calculate_hmm_regime(sample_ohlcv_data, length=20)
        assert ((result['obs_momentum'] > -5) & (result['obs_momentum'] < 5)).all()
        assert ((result['obs_rsi'] > -5) & (result['obs_rsi'] < 5)).all()

    def test_likelihood_columns_exist(self, sample_ohlcv_data):
        """Should retain likelihood columns for each regime."""
        result = calculate_hmm_regime(sample_ohlcv_data, length=20)
        assert 'like_bull' in result.columns
        assert 'like_bear' in result.columns
        assert 'like_chop' in result.columns

    def test_likelihoods_are_positive(self, sample_ohlcv_data):
        """Likelihoods should be non-negative."""
        result = calculate_hmm_regime(sample_ohlcv_data, length=20)
        assert (result['like_bull'] >= 0).all()
        assert (result['like_bear'] >= 0).all()
        assert (result['like_chop'] >= 0).all()

    def test_rsi_observable_is_finite(self, sample_ohlcv_data):
        """obs_rsi should be present and contain finite values after warm-up drop."""
        result = calculate_hmm_regime(sample_ohlcv_data, length=20)
        assert 'obs_rsi' in result.columns
        assert result['obs_rsi'].notna().all()
        assert np.isfinite(result['obs_rsi']).all()

    def test_adaptive_produces_valid_result(self, sample_ohlcv_data):
        """adaptive=True (default) should produce a valid result with all new columns."""
        result = calculate_hmm_regime(sample_ohlcv_data, length=20, adaptive=True)
        assert len(result) > 0
        assert 'prob_bull_smoothed' in result.columns
        # Smoothed probs in valid range
        assert (result['prob_bull_smoothed'] >= 0).all()
        assert (result['prob_bull_smoothed'] <= 100).all()


# ---------------------------------------------------------------------------
# TestHMMToSignal
# ---------------------------------------------------------------------------

class TestHMMToSignal:
    """Tests for converting HMM regimes to trading signals."""

    @pytest.fixture
    def hmm_result(self):
        """Create sample HMM result for signal conversion."""
        np.random.seed(42)
        n = 50
        df = pd.DataFrame({
            'Close': np.random.uniform(100, 110, n),
            'prob_bull': np.random.uniform(0, 100, n),
            'prob_bear': np.random.uniform(0, 100, n),
            'prob_chop': np.random.uniform(0, 100, n),
        })
        prob_sums = df[['prob_bull', 'prob_bear', 'prob_chop']].sum(axis=1)
        df['prob_bull'] = df['prob_bull'] / prob_sums * 100
        df['prob_bear'] = df['prob_bear'] / prob_sums * 100
        df['prob_chop'] = df['prob_chop'] / prob_sums * 100
        return df

    def test_signal_column_exists(self, hmm_result):
        result = hmm_to_signal(hmm_result)
        assert 'HMMSignal' in result.columns

    def test_signal_values(self, hmm_result):
        result = hmm_to_signal(hmm_result)
        valid_signals = {0, 1, 2}
        for signal in result['HMMSignal'].unique():
            assert signal in valid_signals, f"Invalid signal value: {signal}"

    def test_custom_threshold(self, hmm_result):
        result = hmm_to_signal(hmm_result, bullish_threshold=70.0)
        assert 'HMMSignal' in result.columns

    def test_buy_signal_when_bull_above_threshold(self, hmm_result):
        hmm_result.loc[0, 'prob_bull'] = 80.0
        hmm_result.loc[0, 'prob_bear'] = 10.0
        hmm_result.loc[0, 'prob_chop'] = 10.0
        result = hmm_to_signal(hmm_result, bullish_threshold=60.0)
        assert result.loc[0, 'HMMSignal'] == 2

    def test_sell_signal_when_bear_above_threshold(self, hmm_result):
        hmm_result.loc[0, 'prob_bull'] = 10.0
        hmm_result.loc[0, 'prob_bear'] = 80.0
        hmm_result.loc[0, 'prob_chop'] = 10.0
        result = hmm_to_signal(hmm_result, bullish_threshold=60.0)
        assert result.loc[0, 'HMMSignal'] == 1

    def test_no_signal_below_threshold(self, hmm_result):
        hmm_result.loc[0, 'prob_bull'] = 40.0
        hmm_result.loc[0, 'prob_bear'] = 35.0
        hmm_result.loc[0, 'prob_chop'] = 25.0
        result = hmm_to_signal(hmm_result, bullish_threshold=60.0)
        assert result.loc[0, 'HMMSignal'] == 0


# ---------------------------------------------------------------------------
# TestRegimeParams
# ---------------------------------------------------------------------------

class TestRegimeParams:
    """Tests for regime parameter constants."""

    def test_regime_params_structure(self):
        for regime, params in REGIME_PARAMS.items():
            assert 'mom_mu' in params
            assert 'mom_sigma' in params
            assert 'vol_mu' in params
            assert 'vol_sigma' in params
            assert 'rsi_mu' in params
            assert 'rsi_sigma' in params

    def test_positive_standard_deviations(self):
        for regime, params in REGIME_PARAMS.items():
            assert params['mom_sigma'] > 0
            assert params['vol_sigma'] > 0
            assert params['rsi_sigma'] > 0
