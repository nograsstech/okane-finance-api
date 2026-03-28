"""
Unit tests for HMM (Hidden Markov Model) signals module.
"""

import pytest
import pandas as pd
import numpy as np
from app.signals.signals_generator.hmm_signals import (
    gaussian_pdf,
    calculate_hmm_regime,
    hmm_to_signal,
    REGIME_PARAMS,
)


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


class TestCalculateHMMRegime:
    """Tests for HMM regime calculation."""

    @pytest.fixture
    def sample_ohlcv_data(self):
        """Create sample OHLCV data for testing."""
        np.random.seed(42)
        n = 100

        # Generate synthetic price data with trend
        trend = np.linspace(100, 110, n)
        noise = np.random.normal(0, 1, n)
        close = trend + noise

        df = pd.DataFrame({
            'Close': close,
            'High': close + 0.5,
            'Low': close - 0.5,
        })
        return df

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
            'obs_momentum',
            'obs_volatility',
            'obs_rsi',
            'prob_bull',
            'prob_bear',
            'prob_chop',
            'regime_state',
            'regime',
            'confidence',
            'Close',  # Original column should be preserved
        ]

        for col in expected_cols:
            assert col in result.columns, f"Missing column: {col}"

    def test_probabilities_sum_to_100(self, sample_ohlcv_data):
        """Regime probabilities should sum to 100 for each row."""
        result = calculate_hmm_regime(sample_ohlcv_data, length=20)

        for _, row in result.iterrows():
            sum_probs = row['prob_bull'] + row['prob_bear'] + row['prob_chop']
            assert abs(sum_probs - 100.0) < 0.01, f"Probabilities sum to {sum_probs}"

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

    def test_confidence_is_max_probability(self, sample_ohlcv_data):
        """Confidence score should equal the maximum probability."""
        result = calculate_hmm_regime(sample_ohlcv_data, length=20)

        for _, row in result.iterrows():
            max_prob = max(row['prob_bull'], row['prob_bear'], row['prob_chop'])
            assert abs(row['confidence'] - max_prob) < 0.01

    def test_dominant_regime_matches_highest_probability(self, sample_ohlcv_data):
        """Dominant regime should match the highest probability."""
        result = calculate_hmm_regime(sample_ohlcv_data, length=20)

        for _, row in result.iterrows():
            probs = {
                'bull': row['prob_bull'],
                'bear': row['prob_bear'],
                'chop': row['prob_chop'],
            }
            highest = max(probs, key=probs.get)
            assert row['regime'] == highest

    def test_custom_transition_probabilities(self, sample_ohlcv_data):
        """Should accept custom transition probabilities."""
        result = calculate_hmm_regime(
            sample_ohlcv_data,
            length=20,
            p_stay_bull=0.90,
            p_stay_bear=0.90,
            p_stay_chop=0.70,
        )

        # Should complete without error; warm-up rows are dropped so result
        # is shorter than the original input
        assert len(result) > 0
        assert len(result) <= len(sample_ohlcv_data)

    def test_observables_are_standardized(self, sample_ohlcv_data):
        """Observables should be roughly standardized (mean near 0, std near 1)."""
        result = calculate_hmm_regime(sample_ohlcv_data, length=20)

        # Check that momentum has reasonable bounds (most values within -3 to 3)
        momentum_within_bounds = (
            (result['obs_momentum'] > -5) & (result['obs_momentum'] < 5)
        ).all()
        assert momentum_within_bounds, "Momentum observable outside expected range"

        rsi_within_bounds = (
            (result['obs_rsi'] > -5) & (result['obs_rsi'] < 5)
        ).all()
        assert rsi_within_bounds, "RSI observable outside expected range"

    def test_likelihood_columns_exist(self, sample_ohlcv_data):
        """Should calculate likelihood columns for each regime."""
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
        assert result['obs_rsi'].notna().all(), "obs_rsi contains NaN after dropna"
        assert np.isfinite(result['obs_rsi']).all(), "obs_rsi contains non-finite values"


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

        # Normalize probabilities
        prob_sums = df[['prob_bull', 'prob_bear', 'prob_chop']].sum(axis=1)
        df['prob_bull'] = df['prob_bull'] / prob_sums * 100
        df['prob_bear'] = df['prob_bear'] / prob_sums * 100
        df['prob_chop'] = df['prob_chop'] / prob_sums * 100

        return df

    def test_signal_column_exists(self, hmm_result):
        """Should add HMMSignal column."""
        result = hmm_to_signal(hmm_result)
        assert 'HMMSignal' in result.columns

    def test_signal_values(self, hmm_result):
        """Signal values should be 0, 1, or 2."""
        result = hmm_to_signal(hmm_result)

        valid_signals = {0, 1, 2}
        for signal in result['HMMSignal'].unique():
            assert signal in valid_signals, f"Invalid signal value: {signal}"

    def test_custom_threshold(self, hmm_result):
        """Should accept custom bullish threshold."""
        result = hmm_to_signal(hmm_result, bullish_threshold=70.0)
        assert 'HMMSignal' in result.columns

    def test_buy_signal_when_bull_above_threshold(self, hmm_result):
        """Should generate buy signals when bull probability exceeds threshold."""
        # Set first row to have high bull probability
        hmm_result.loc[0, 'prob_bull'] = 80.0
        hmm_result.loc[0, 'prob_bear'] = 10.0
        hmm_result.loc[0, 'prob_chop'] = 10.0

        result = hmm_to_signal(hmm_result, bullish_threshold=60.0)
        assert result.loc[0, 'HMMSignal'] == 2  # Buy signal

    def test_sell_signal_when_bear_above_threshold(self, hmm_result):
        """Should generate sell signals when bear probability exceeds threshold."""
        # Set first row to have high bear probability
        hmm_result.loc[0, 'prob_bull'] = 10.0
        hmm_result.loc[0, 'prob_bear'] = 80.0
        hmm_result.loc[0, 'prob_chop'] = 10.0

        result = hmm_to_signal(hmm_result, bullish_threshold=60.0)
        assert result.loc[0, 'HMMSignal'] == 1  # Sell signal

    def test_no_signal_below_threshold(self, hmm_result):
        """Should generate no signals when no probability exceeds threshold."""
        # Set first row to have all probabilities below threshold
        hmm_result.loc[0, 'prob_bull'] = 40.0
        hmm_result.loc[0, 'prob_bear'] = 35.0
        hmm_result.loc[0, 'prob_chop'] = 25.0

        result = hmm_to_signal(hmm_result, bullish_threshold=60.0)
        assert result.loc[0, 'HMMSignal'] == 0  # No signal


class TestRegimeParams:
    """Tests for regime parameter constants."""

    def test_regime_params_structure(self):
        """Regime params should have correct structure."""
        for regime, params in REGIME_PARAMS.items():
            assert 'mom_mu' in params
            assert 'mom_sigma' in params
            assert 'vol_mu' in params
            assert 'vol_sigma' in params
            assert 'rsi_mu' in params
            assert 'rsi_sigma' in params

    def test_positive_standard_deviations(self):
        """All standard deviations should be positive."""
        for regime, params in REGIME_PARAMS.items():
            assert params['mom_sigma'] > 0
            assert params['vol_sigma'] > 0
            assert params['rsi_sigma'] > 0
