"""Tests for DictatorState — mission oversight tracking."""

from datetime import datetime

from magenta.dictator.state import DictatorState, DictatorStatus


class TestDictatorState:
    def test_initial_state_is_idle(self):
        state = DictatorState()
        assert state.status == DictatorStatus.idle
        assert state.active_missions == {}
        assert state.completed_missions == []

    def test_track_mission_adds_oversight(self):
        state = DictatorState()
        state.track_mission(mission_id="mission-1", teaming="supervisor", agents=3)

        assert "mission-1" in state.active_missions
        oversight = state.active_missions["mission-1"]
        assert oversight.teaming_structure == "supervisor"
        assert oversight.agent_count == 3
        assert oversight.status == "active"
        assert state.status == DictatorStatus.commanding

    def test_track_multiple_missions(self):
        state = DictatorState()
        state.track_mission("m1")
        state.track_mission("m2")
        assert len(state.active_missions) == 2

    def test_complete_mission_removes_from_active(self):
        state = DictatorState()
        state.track_mission("mission-1")
        assert "mission-1" in state.active_missions

        state.complete_mission("mission-1")
        assert "mission-1" not in state.active_missions
        assert "mission-1" in state.completed_missions

    def test_complete_all_returns_to_idle(self):
        state = DictatorState()
        state.track_mission("m1")
        state.track_mission("m2")
        state.complete_mission("m1")
        state.complete_mission("m2")
        assert state.status == DictatorStatus.idle

    def test_log_directive_tracks_count_on_oversight(self):
        state = DictatorState()
        state.track_mission("mission-x")
        state.log_directive({"type": "deploy_agent", "mission_id": "mission-x", "target": "triage"})

        oversight = state.active_missions["mission-x"]
        assert oversight.directive_count == 1
        assert len(state.directive_log) == 1

    def test_log_directive_no_mission_match(self):
        state = DictatorState()
        state.log_directive(
            {"type": "system_command", "mission_id": "nonexistent", "target": "framework"}
        )
        assert len(state.directive_log) == 1

    def test_completed_missions_tracked_separately(self):
        state = DictatorState()
        state.track_mission("m1")
        state.track_mission("m2")
        state.complete_mission("m1")
        assert state.completed_missions == ["m1"]
        assert "m2" in state.active_missions

    def test_oversight_timestamps(self):
        state = DictatorState()
        before = datetime.utcnow()
        state.track_mission("m1")
        after = datetime.utcnow()
        oversight = state.active_missions["m1"]
        assert before <= oversight.started_at <= after
        assert before <= oversight.last_seen <= after

    def test_directive_log_timestamp(self):
        state = DictatorState()
        before = datetime.utcnow()
        state.log_directive({"type": "halt_mission", "target": "test"})
        after = datetime.utcnow()
        log_entry = state.directive_log[0]
        assert "timestamp" in log_entry
        assert before <= datetime.fromisoformat(log_entry["timestamp"]) <= after
