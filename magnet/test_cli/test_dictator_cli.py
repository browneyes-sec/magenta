"""Tests for Dictator CLI — Typer CliRunner validation of all 11 commands."""

import pytest
from typer.testing import CliRunner

from magenta.main import app


@pytest.fixture
def runner():
    return CliRunner()


class TestDictatorCLIStatus:
    def test_status(self, runner):
        result = runner.invoke(app, ["dictator", "status"])
        assert result.exit_code == 0
        assert "Dictator Oversight Board" in result.stdout

    def test_framework(self, runner):
        result = runner.invoke(app, ["dictator", "framework"])
        assert result.exit_code == 0
        assert "Magenta Framework Status" in result.stdout
        assert "Dictator" in result.stdout

    def test_oversight(self, runner):
        result = runner.invoke(app, ["dictator", "oversight"])
        assert result.exit_code == 0
        assert "Active Mission Oversight" in result.stdout or "No active missions" in result.stdout

    def test_directives(self, runner):
        result = runner.invoke(app, ["dictator", "directives"])
        assert result.exit_code == 0


class TestDictatorCLIActions:
    def test_halt(self, runner):
        result = runner.invoke(app, ["dictator", "halt", "test-mission", "--reason", "CLI test"])
        assert result.exit_code == 0
        assert "halted" in result.stdout

    def test_escalate(self, runner):
        result = runner.invoke(
            app, ["dictator", "escalate", "test-mission", "--reason", "CLI test"]
        )
        assert result.exit_code == 0
        assert "escalated" in result.stdout

    def test_deploy(self, runner):
        result = runner.invoke(app, ["dictator", "deploy", "triage"])
        assert result.exit_code == 0
        assert "Deployed" in result.stdout

    def test_deploy_with_model(self, runner):
        result = runner.invoke(app, ["dictator", "deploy", "enrich", "--model", "mistral:7b"])
        assert result.exit_code == 0
        assert "Deployed" in result.stdout

    def test_recall_not_found(self, runner):
        result = runner.invoke(app, ["dictator", "recall", "nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.stdout

    def test_override(self, runner):
        result = runner.invoke(app, ["dictator", "override", "test-mission", "debate"])
        assert result.exit_code == 0
        assert "overridden" in result.stdout


class TestDictatorCLIPolicy:
    def test_policy_list(self, runner):
        result = runner.invoke(app, ["dictator", "policy", "list"])
        assert result.exit_code == 0
        assert "Orchestration Policies" in result.stdout

    def test_policy_override(self, runner):
        result = runner.invoke(
            app,
            [
                "dictator",
                "policy",
                "override",
                "--name",
                "cli_test",
                "--rules",
                '{"teaming": "mesh"}',
            ],
        )
        assert result.exit_code == 0
        assert "override applied" in result.stdout

    def test_policy_clear(self, runner):
        result = runner.invoke(app, ["dictator", "policy", "clear"])
        assert result.exit_code == 0
        assert "overrides cleared" in result.stdout

    def test_policy_invalid_action(self, runner):
        result = runner.invoke(app, ["dictator", "policy", "bogus"])
        assert result.exit_code == 1

    def test_policy_override_missing_args(self, runner):
        result = runner.invoke(app, ["dictator", "policy", "override"])
        assert result.exit_code == 1


class TestDictatorCLIProbe:
    def test_probe_promote(self, runner):
        result = runner.invoke(app, ["dictator", "probe", "promote", "--name", "memory_test"])
        assert result.exit_code == 0
        assert "promoted" in result.stdout

    def test_probe_promote_guard(self, runner):
        result = runner.invoke(
            app, ["dictator", "probe", "promote", "--name", "net_test", "--guard"]
        )
        assert result.exit_code == 0
        assert "to guard" in result.stdout


class TestDictatorCLIHelp:
    def test_dictator_help(self, runner):
        result = runner.invoke(app, ["dictator", "--help"])
        assert result.exit_code == 0
        assert "Super-agent orchestration" in result.stdout

    def test_state_help(self, runner):
        result = runner.invoke(app, ["state", "--help"])
        assert result.exit_code == 0
        assert "probe" in result.stdout
        assert "regression" in result.stdout
        assert "report" in result.stdout
        assert "attest" in result.stdout
