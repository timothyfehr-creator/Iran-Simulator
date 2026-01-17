#!/usr/bin/env python3
"""
Unit and Integration Tests for Bayesian Network Prototype
=========================================================

Tests the CausalEngine class and supporting functions from
scripts/prototype_causal_graph.py.

Run with:
    pytest tests/test_pgmpy_prototype.py -v
"""

import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from prototype_causal_graph import (
    ALL_NODES,
    EDGES,
    ROOT_NODES,
    INTERMEDIATE_NODES,
    TERMINAL_NODES,
    CausalEngine,
    build_dag,
    window_to_daily_hazard,
    window_to_marginal,
    get_parents,
    get_cardinality,
    build_economic_stress_cpd,
    build_khamenei_health_cpd,
    build_security_loyalty_cpd_placeholder,
    build_regime_outcome_cpd_placeholder,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def priors_path():
    """Path to analyst_priors.json."""
    return Path(__file__).parent.parent / "data" / "analyst_priors.json"


@pytest.fixture
def priors(priors_path):
    """Load analyst priors."""
    with open(priors_path, 'r') as f:
        return json.load(f)


@pytest.fixture
def engine(priors_path):
    """Create CausalEngine instance."""
    return CausalEngine(priors_path)


# =============================================================================
# UNIT TESTS: UTILITY FUNCTIONS
# =============================================================================

class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_window_to_daily_hazard_basic(self):
        """Test daily hazard conversion with basic values."""
        # 35% in 14 days
        hazard = window_to_daily_hazard(0.35, 14)
        # Should be approximately 0.030
        assert 0.025 < hazard < 0.035

    def test_window_to_daily_hazard_zero(self):
        """Test that zero probability gives zero hazard."""
        assert window_to_daily_hazard(0.0, 14) == 0.0

    def test_window_to_daily_hazard_one(self):
        """Test that probability 1.0 gives hazard 1.0."""
        assert window_to_daily_hazard(1.0, 14) == 1.0

    def test_window_to_daily_hazard_reconstructs(self):
        """Test that daily hazard reconstructs window probability."""
        p_window = 0.35
        window_days = 14
        hazard = window_to_daily_hazard(p_window, window_days)

        # Reconstruct: P(event in window) = 1 - (1 - hazard)^days
        reconstructed = 1 - (1 - hazard) ** window_days
        assert abs(reconstructed - p_window) < 0.001

    def test_window_to_marginal_basic(self):
        """Test marginal conversion with basic values."""
        p_marginal = window_to_marginal(0.35, 14, 90)
        # Expected: 0.35 * (90 - 7) / 90 ≈ 0.32
        assert 0.30 < p_marginal < 0.35

    def test_window_to_marginal_longer_window(self):
        """Test marginal with longer window."""
        p_marginal = window_to_marginal(0.25, 60, 90)
        # Expected: 0.25 * (90 - 30) / 90 ≈ 0.17
        assert 0.15 < p_marginal < 0.20


# =============================================================================
# UNIT TESTS: DAG STRUCTURE
# =============================================================================

class TestDAGStructure:
    """Tests for DAG structure."""

    def test_dag_is_acyclic(self):
        """DAG must have no cycles."""
        import networkx as nx
        g = nx.DiGraph(EDGES)
        assert nx.is_directed_acyclic_graph(g), "Graph contains cycles"

    def test_all_nodes_defined(self):
        """All nodes in edges must be defined in node lists."""
        all_edge_nodes = set()
        for src, dst in EDGES:
            all_edge_nodes.add(src)
            all_edge_nodes.add(dst)

        for node in all_edge_nodes:
            assert node in ALL_NODES, f"Node {node} not defined in ALL_NODES"

    def test_edge_count(self):
        """Verify expected number of edges."""
        # Plan specifies 25 edges, but we may have added more
        assert len(EDGES) >= 25, f"Expected at least 25 edges, got {len(EDGES)}"

    def test_root_nodes_have_no_parents(self):
        """Root nodes should have no incoming edges."""
        children = {dst for _, dst in EDGES}
        for node in ROOT_NODES:
            if node in children:
                # Check if all parents are external
                parents = get_parents(node)
                assert len(parents) == 0 or all(p not in ALL_NODES for p in parents), \
                    f"Root node {node} has parents: {parents}"

    def test_terminal_node_has_parents(self):
        """Terminal node should have incoming edges."""
        for node in TERMINAL_NODES:
            parents = get_parents(node)
            assert len(parents) > 0, f"Terminal node {node} has no parents"

    def test_get_cardinality(self):
        """Test cardinality lookup."""
        assert get_cardinality("Rial_Rate") == 3
        assert get_cardinality("Khamenei_Health") == 2
        assert get_cardinality("Regime_Outcome") == 5
        assert get_cardinality("US_Policy_Disposition") == 4


# =============================================================================
# UNIT TESTS: CPDs
# =============================================================================

class TestCPDs:
    """Tests for Conditional Probability Distributions."""

    def test_economic_stress_cpd_structure(self, priors):
        """Test Economic_Stress CPD has correct structure."""
        cpd = build_economic_stress_cpd(priors)

        assert cpd.variable == "Economic_Stress"
        assert cpd.variable_card == 3
        assert list(cpd.variables) == ["Economic_Stress", "Rial_Rate", "Inflation"]

    def test_economic_stress_cpd_columns_sum_to_one(self, priors):
        """Test Economic_Stress CPD columns sum to 1."""
        cpd = build_economic_stress_cpd(priors)
        values = cpd.get_values()
        col_sums = values.sum(axis=0)
        np.testing.assert_allclose(col_sums, 1.0, atol=0.01)

    def test_economic_stress_deterministic(self, priors):
        """Test Economic_Stress is deterministic (0s and 1s)."""
        cpd = build_economic_stress_cpd(priors)
        values = cpd.get_values()
        # Each column should have exactly one 1.0 and rest 0.0
        for col in values.T:
            assert np.isclose(col.max(), 1.0), "Column max should be 1.0"
            assert np.isclose(col.sum(), 1.0), "Column sum should be 1.0"

    def test_khamenei_health_cpd(self, priors):
        """Test Khamenei_Health CPD."""
        cpd = build_khamenei_health_cpd(priors)

        assert cpd.variable == "Khamenei_Health"
        assert cpd.variable_card == 2

        values = cpd.get_values()
        assert values.shape == (2, 1)
        np.testing.assert_allclose(values.sum(), 1.0)

        # Death probability should be around 8%
        p_dead = values[1, 0]
        assert 0.03 < p_dead < 0.15, f"Khamenei death probability {p_dead} out of range"

    def test_security_loyalty_cpd_structure(self, priors):
        """Test Security_Loyalty CPD structure."""
        cpd = build_security_loyalty_cpd_placeholder(priors)

        assert cpd.variable == "Security_Loyalty"
        assert cpd.variable_card == 3
        # 3 x 5 x 4 = 60 columns
        assert cpd.get_values().shape[1] == 60

    def test_security_loyalty_cpd_columns_sum_to_one(self, priors):
        """Test Security_Loyalty CPD columns sum to 1."""
        cpd = build_security_loyalty_cpd_placeholder(priors)
        values = cpd.get_values()
        col_sums = values.sum(axis=0)
        np.testing.assert_allclose(col_sums, 1.0, atol=0.01)

    def test_regime_outcome_cpd_structure(self, priors):
        """Test Regime_Outcome CPD structure."""
        cpd = build_regime_outcome_cpd_placeholder(priors)

        assert cpd.variable == "Regime_Outcome"
        assert cpd.variable_card == 5
        # 3 x 2 x 2 x 3 = 36 columns
        assert cpd.get_values().shape[1] == 36

    def test_regime_outcome_cpd_columns_sum_to_one(self, priors):
        """Test Regime_Outcome CPD columns sum to 1."""
        cpd = build_regime_outcome_cpd_placeholder(priors)
        values = cpd.get_values()
        col_sums = values.sum(axis=0)
        np.testing.assert_allclose(col_sums, 1.0, atol=0.01)


# =============================================================================
# INTEGRATION TESTS: MODEL VALIDATION
# =============================================================================

class TestModelValidation:
    """Tests for full model validation."""

    def test_model_check(self, engine):
        """pgmpy model.check_model() passes."""
        assert engine.model.check_model(), "Model check failed"

    def test_all_cpds_valid(self, engine):
        """All CPD columns sum to 1.0."""
        for cpd in engine.model.get_cpds():
            values = cpd.get_values()
            col_sums = values.sum(axis=0)
            np.testing.assert_allclose(
                col_sums, 1.0, atol=0.01,
                err_msg=f"CPD {cpd.variable} columns don't sum to 1.0"
            )

    def test_all_cpds_present(self, engine):
        """All nodes have CPDs."""
        cpd_vars = {cpd.variable for cpd in engine.model.get_cpds()}
        for node in ALL_NODES:
            assert node in cpd_vars, f"Missing CPD for node {node}"

    def test_validate_method(self, engine):
        """Test engine.validate() method."""
        is_valid, errors = engine.validate()
        assert is_valid, f"Validation failed with errors: {errors}"


# =============================================================================
# INTEGRATION TESTS: INFERENCE
# =============================================================================

class TestInference:
    """Tests for inference queries."""

    def test_marginal_regime_outcome(self, engine):
        """Test marginal query for Regime_Outcome."""
        result = engine.infer_single("Regime_Outcome", {})

        assert len(result) == 5
        assert all(0 <= p <= 1 for p in result.values())
        assert abs(sum(result.values()) - 1.0) < 0.01

    def test_conditional_inference(self, engine):
        """Test conditional inference with evidence."""
        result = engine.infer_single(
            "Regime_Outcome",
            {"Security_Loyalty": "DEFECTED"}
        )

        # With defection, collapse should be more likely
        assert result["COLLAPSE"] > 0.3, \
            f"Collapse probability {result['COLLAPSE']} too low given defection"

    def test_economic_stress_affects_outcome(self, engine):
        """Test that economic stress affects regime outcome."""
        result_stable = engine.infer_single(
            "Regime_Outcome",
            {"Economic_Stress": "STABLE"}
        )
        result_critical = engine.infer_single(
            "Regime_Outcome",
            {"Economic_Stress": "CRITICAL"}
        )

        # Status quo should be more likely under stable economy
        assert result_stable["STATUS_QUO"] > result_critical["STATUS_QUO"], \
            "Economic stress should reduce STATUS_QUO probability"

    def test_multiple_evidence(self, engine):
        """Test inference with multiple evidence variables."""
        result = engine.infer_single(
            "Regime_Outcome",
            {
                "Economic_Stress": "CRITICAL",
                "Security_Loyalty": "WAVERING",
            }
        )

        assert len(result) == 5
        assert abs(sum(result.values()) - 1.0) < 0.01


# =============================================================================
# INTEGRATION TESTS: SENSITIVITY ANALYSIS
# =============================================================================

class TestSensitivity:
    """Tests for sensitivity analysis."""

    def test_sensitivity_returns_parents(self, engine):
        """Test sensitivity analysis returns parent nodes."""
        sens = engine.sensitivity("Regime_Outcome")

        # Should include parents of Regime_Outcome
        expected_parents = {"Security_Loyalty", "Succession_Type",
                           "Fragmentation_Outcome", "Elite_Cohesion"}
        for parent in expected_parents:
            assert parent in sens, f"Missing parent {parent} in sensitivity"

    def test_sensitivity_values_non_negative(self, engine):
        """Test sensitivity values are non-negative."""
        sens = engine.sensitivity("Regime_Outcome")

        for parent, mi in sens.items():
            assert mi >= 0, f"Negative sensitivity for {parent}: {mi}"

    def test_sensitivity_ranking(self, engine):
        """Security_Loyalty should be among top sensitivities."""
        sens = engine.sensitivity("Regime_Outcome")

        # Get sorted list
        sorted_parents = list(sens.keys())

        # Security_Loyalty should be in top 3
        assert "Security_Loyalty" in sorted_parents[:3], \
            f"Security_Loyalty not in top 3 sensitivities: {sorted_parents}"


# =============================================================================
# INTEGRATION TESTS: BLACK SWAN PRESERVATION
# =============================================================================

class TestBlackSwanPreservation:
    """Tests for black swan (tail risk) preservation."""

    def test_check_black_swan_method(self, engine):
        """Test black swan preservation check method."""
        result = engine.check_black_swan_preservation()

        assert "outcomes" in result
        assert "all_passed" in result
        assert "failures" in result

    def test_no_erased_outcomes(self, engine):
        """Test that no significant outcomes are erased by BN."""
        result = engine.check_black_swan_preservation()

        # Should pass (no analyst prior > 1% has BN prob < 0.5%)
        if not result["all_passed"]:
            pytest.fail(f"Black swan check failed: {result['failures']}")

    def test_marginal_outcome_reasonable(self, engine):
        """Test that marginal outcome distribution is reasonable."""
        result = engine.infer_single("Regime_Outcome", {})

        # All outcomes should have some probability
        for state, prob in result.items():
            assert prob > 0.001, f"Outcome {state} has near-zero probability: {prob}"

        # Status quo should be most likely (base case)
        assert result["STATUS_QUO"] > 0.20, \
            f"STATUS_QUO probability {result['STATUS_QUO']} too low"


# =============================================================================
# INTEGRATION TESTS: WHAT-IF QUERIES
# =============================================================================

class TestWhatIf:
    """Tests for causal intervention (what-if) queries."""

    def test_what_if_basic(self, engine):
        """Test basic what-if query."""
        result = engine.what_if(
            {"US_Policy_Disposition": "KINETIC"},
            "Regime_Outcome"
        )

        assert len(result) == 5
        assert all(0 <= p <= 1 for p in result.values())

    def test_what_if_defection(self, engine):
        """Test what-if with security defection intervention."""
        result = engine.what_if(
            {"Security_Loyalty": "DEFECTED"},
            "Regime_Outcome"
        )

        # Collapse should be highly probable
        assert result["COLLAPSE"] > 0.3, \
            f"Collapse probability {result['COLLAPSE']} too low under defection intervention"


# =============================================================================
# REGRESSION TESTS
# =============================================================================

class TestRegression:
    """Regression tests to catch unintended changes."""

    def test_node_count(self):
        """Test expected number of nodes."""
        assert len(ALL_NODES) == 22, f"Expected 22 nodes, got {len(ALL_NODES)}"

    def test_root_node_count(self):
        """Test expected number of root nodes."""
        assert len(ROOT_NODES) == 4, f"Expected 4 root nodes, got {len(ROOT_NODES)}"

    def test_terminal_node_count(self):
        """Test expected number of terminal nodes."""
        assert len(TERMINAL_NODES) == 1, f"Expected 1 terminal node, got {len(TERMINAL_NODES)}"

    def test_regime_outcome_states(self):
        """Test Regime_Outcome has expected states."""
        expected = ["STATUS_QUO", "CONCESSIONS", "TRANSITION", "COLLAPSE", "FRAGMENTATION"]
        assert ALL_NODES["Regime_Outcome"] == expected


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
