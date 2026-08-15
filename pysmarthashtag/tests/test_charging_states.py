"""Tests for the enumerated charging and charger connection states.

Consumers such as the Home Assistant integration need to declare every state a
sensor can take up front, otherwise the automation editor cannot offer them as
trigger values. See SmartHashtag issue #439.
"""

import pytest

from pysmarthashtag.vehicle.battery import (
    CHARGER_CONNECTION_STATES,
    CHARGING_STATES,
    Battery,
    ChargerConnectionState,
    ChargingState,
    charger_connection_state_name,
)


def create_vehicle_data(charger_state: str, charger_connection: str) -> dict:
    """Create minimal vehicle data carrying the two status fields."""
    return {
        "vehicleStatus": {
            "updateTime": "1716485767970",
            "additionalVehicleStatus": {
                "electricVehicleStatus": {
                    "chargeLevel": "50",
                    "chargerState": charger_state,
                    "statusOfChargerConnection": charger_connection,
                }
            },
        },
    }


class TestChargingStates:
    """Test the de-duplicated list of charging states."""

    def test_contains_no_duplicates(self):
        """The exported states are unique, unlike the index based ChargingState."""
        assert len(CHARGING_STATES) == len(set(CHARGING_STATES))

    def test_covers_every_indexed_state(self):
        """Every state reachable through a chargerState code is exported."""
        assert set(CHARGING_STATES) == set(ChargingState)

    def test_keeps_definition_order(self):
        """The first occurrence of each state defines its position."""
        assert CHARGING_STATES[0] == "NOT_CHARGING"
        assert CHARGING_STATES[-1] == "DC_CHARGING"

    @pytest.mark.parametrize("charger_state", range(len(ChargingState)))
    def test_every_code_reports_an_exported_state(self, charger_state):
        """Parsing any known code yields a state that consumers can enumerate."""
        battery = Battery.from_vehicle_data(create_vehicle_data(str(charger_state), "0"))

        assert battery is not None
        assert battery.charging_status in CHARGING_STATES

    def test_unknown_code_falls_back_to_unknown(self):
        """Codes beyond the known range do not leak into the state."""
        battery = Battery.from_vehicle_data(create_vehicle_data("99", "0"))

        assert battery is not None
        assert battery.charging_status == "UNKNOWN"

    def test_negative_code_falls_back_to_unknown(self):
        """A negative code must not wrap around to the end of the list."""
        battery = Battery.from_vehicle_data(create_vehicle_data("-1", "0"))

        assert battery is not None
        assert battery.charging_status == "UNKNOWN"


class TestChargerConnectionState:
    """Test the named charger connection state."""

    def test_states_are_lower_case_names(self):
        """The exported names are usable as translation keys."""
        assert CHARGER_CONNECTION_STATES == (
            "not_connected",
            "dc_connected",
            "plugged_not_charging",
            "charging",
            "unknown",
        )

    @pytest.mark.parametrize("state", ChargerConnectionState)
    def test_known_codes_map_to_exported_names(self, state):
        """Every code of the enum maps to an exported name."""
        assert charger_connection_state_name(state.value) in CHARGER_CONNECTION_STATES

    def test_missing_code_stays_none(self):
        """A vehicle that does not report the field keeps the state unset."""
        assert charger_connection_state_name(None) is None

    def test_unmapped_code_falls_back_to_unknown(self):
        """Codes the API adds later do not break enumeration."""
        assert charger_connection_state_name(42) == "unknown"

    def test_parsed_from_vehicle_data(self):
        """The raw code and the named state are both available after parsing."""
        battery = Battery.from_vehicle_data(create_vehicle_data("2", "3"))

        assert battery is not None
        assert battery.charger_connection_status == 3
        assert battery.charger_connection_state == "charging"

    def test_absent_field_leaves_state_unset(self):
        """No connection field means no state, not a wrong one."""
        vehicle_data = create_vehicle_data("2", "0")
        del vehicle_data["vehicleStatus"]["additionalVehicleStatus"]["electricVehicleStatus"][
            "statusOfChargerConnection"
        ]
        battery = Battery.from_vehicle_data(vehicle_data)

        assert battery is not None
        assert battery.charger_connection_status is None
        assert battery.charger_connection_state is None
