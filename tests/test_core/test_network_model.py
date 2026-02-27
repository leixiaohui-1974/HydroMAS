"""Tests for core.simulation.network_model module.
core.simulation.network_model 模块测试。
"""

import pytest
from core.simulation.network_model import (
    NetworkParams,
    _require_wntr,
    _HAS_WNTR,
    load_network,
    run_hydraulic_sim,
    run_leak_scenario,
    run_pump_scenario,
)


class TestNetworkParamsDefaults:
    def test_network_params_defaults(self):
        """NetworkParams should initialise with sensible zero defaults."""
        p = NetworkParams()
        assert p.inp_file == ""
        assert p.n_nodes == 0
        assert p.n_pipes == 0
        assert p.n_pumps == 0
        assert p.n_valves == 0
        assert p.total_length_m == 0.0


class TestNetworkParamsValidation:
    def test_network_params_validate_good(self):
        """Valid parameters should not raise on validate()."""
        p = NetworkParams(
            inp_file="test.inp",
            n_nodes=10,
            n_pipes=15,
            n_pumps=2,
            n_valves=3,
            total_length_m=500.0,
        )
        p.validate()  # should not raise

    def test_network_params_validate_bad_nodes(self):
        """Negative n_nodes should raise ValueError."""
        p = NetworkParams(n_nodes=-1)
        with pytest.raises(ValueError, match="n_nodes"):
            p.validate()

    def test_network_params_validate_bad_pipes(self):
        """Negative n_pipes should raise ValueError."""
        p = NetworkParams(n_pipes=-5)
        with pytest.raises(ValueError, match="n_pipes"):
            p.validate()

    def test_network_params_validate_bad_pumps(self):
        """Negative n_pumps should raise ValueError."""
        p = NetworkParams(n_pumps=-1)
        with pytest.raises(ValueError, match="n_pumps"):
            p.validate()

    def test_network_params_validate_bad_valves(self):
        """Negative n_valves should raise ValueError."""
        p = NetworkParams(n_valves=-2)
        with pytest.raises(ValueError, match="n_valves"):
            p.validate()

    def test_network_params_validate_bad_length(self):
        """Negative total_length_m should raise ValueError."""
        p = NetworkParams(total_length_m=-100.0)
        with pytest.raises(ValueError, match="total_length_m"):
            p.validate()


class TestWntrNotInstalled:
    """All WNTR-dependent functions must raise ValueError when wntr is absent."""

    @pytest.mark.skipif(_HAS_WNTR, reason="wntr is installed; skip no-wntr tests")
    def test_require_wntr_raises(self):
        """_require_wntr should raise ValueError with install instructions."""
        with pytest.raises(ValueError, match="pip install wntr"):
            _require_wntr()

    @pytest.mark.skipif(_HAS_WNTR, reason="wntr is installed; skip no-wntr tests")
    def test_load_network_no_wntr(self):
        """load_network should raise ValueError when wntr is not installed."""
        with pytest.raises(ValueError, match="WNTR is required"):
            load_network("fake.inp")

    @pytest.mark.skipif(_HAS_WNTR, reason="wntr is installed; skip no-wntr tests")
    def test_run_hydraulic_sim_no_wntr(self):
        """run_hydraulic_sim should raise ValueError when wntr is not installed."""
        with pytest.raises(ValueError, match="WNTR is required"):
            run_hydraulic_sim("fake.inp", duration=3600.0)

    @pytest.mark.skipif(_HAS_WNTR, reason="wntr is installed; skip no-wntr tests")
    def test_run_leak_scenario_no_wntr(self):
        """run_leak_scenario should raise ValueError when wntr is not installed."""
        with pytest.raises(ValueError, match="WNTR is required"):
            run_leak_scenario("fake.inp", "node1", leak_area=0.01, duration=3600.0)

    @pytest.mark.skipif(_HAS_WNTR, reason="wntr is installed; skip no-wntr tests")
    def test_run_pump_scenario_no_wntr(self):
        """run_pump_scenario should raise ValueError when wntr is not installed."""
        with pytest.raises(ValueError, match="WNTR is required"):
            run_pump_scenario(
                "fake.inp", "pump1", speed_profile=[(0, 1.0)], duration=3600.0
            )

    @pytest.mark.skipif(_HAS_WNTR, reason="wntr is installed; skip no-wntr tests")
    def test_network_params_from_inp_no_wntr(self):
        """NetworkParams.from_inp should raise ValueError without wntr."""
        with pytest.raises(ValueError, match="WNTR is required"):
            NetworkParams.from_inp("fake.inp")
