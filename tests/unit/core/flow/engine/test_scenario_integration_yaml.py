import importlib.resources

import yaml


def get_yaml_data():
    text = (
        importlib.resources.files("specweaver.workflows.pipelines") / "scenario_integration.yaml"
    ).read_text("utf-8")
    return yaml.safe_load(text)


class TestScenarioIntegrationPipeline:
    def test_pipeline_loads(self):
        data = get_yaml_data()
        assert data["name"] == "scenario_integration"
        assert "steps" in data

    def test_step_count(self):
        data = get_yaml_data()
        # Should have 4 steps: generate_contract, run_dual_pipelines, run_scenario_tests, arbitrate_verdict
        assert len(data["steps"]) == 4

    def test_dual_pipeline_mode_param(self):
        data = get_yaml_data()
        dual_step = next(step for step in data["steps"] if step["name"] == "run_dual_pipelines")
        assert dual_step["params"]["mode"] == "dual_pipeline"

    def test_arbitrate_step_gate(self):
        data = get_yaml_data()
        arbitrate_step = next(step for step in data["steps"] if step["name"] == "arbitrate_verdict")
        assert arbitrate_step["gate"]["type"] == "auto"
        assert arbitrate_step["gate"]["on_fail"] == "loop_back"
        assert arbitrate_step["gate"]["loop_target"] == "run_dual_pipelines"

    def test_arbitrate_step_max_retries(self):
        data = get_yaml_data()
        arbitrate_step = next(step for step in data["steps"] if step["name"] == "arbitrate_verdict")
        assert arbitrate_step["gate"]["max_retries"] == 3
        assert arbitrate_step["gate"]["max_retries_hitl"] == 4
