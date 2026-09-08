from app.main import app

SIGNAL_QUERY_FIELDS = {
    "ticker": True,
    "period": False,
    "interval": True,
    "strategy": False,
    "parameters": False,
    "start": False,
    "end": False,
    "strategy_id": False,
    "backtest_process_uuid": False,
    "skip_optimization": False,
}


def _response_schema(operation: dict[str, object]) -> dict[str, object]:
    responses = operation["responses"]
    assert isinstance(responses, dict)
    success = responses["200"]
    assert isinstance(success, dict)
    content = success["content"]
    assert isinstance(content, dict)
    json_content = content["application/json"]
    assert isinstance(json_content, dict)
    response_schema = json_content["schema"]
    assert isinstance(response_schema, dict)
    return response_schema


def _query_fields(operation: dict[str, object]) -> dict[str, bool]:
    parameters = operation.get("parameters", [])
    assert isinstance(parameters, list)
    return {
        parameter["name"]: parameter.get("required", False)
        for parameter in parameters
        if parameter["in"] == "query"
    }


def test_core_signal_routes_keep_their_methods_and_response_models():
    schema = app.openapi()
    paths = schema["paths"]

    assert set(paths["/signals/"]) == {"get"}
    assert set(paths["/signals/backtest"]) == {"get"}
    assert set(paths["/signals/backtest/sync"]) == {"get"}
    assert set(paths["/signals/backtest/replay"]) == {"get"}
    assert set(paths["/signals/portfolio-replay"]) == {"post"}
    assert set(paths["/signals/strategy-notification-job"]) == {"post"}
    assert set(paths["/signals/strategies"]) == {"get"}
    assert set(paths["/signals/hmm/regimes"]) == {"get"}

    assert _response_schema(paths["/signals/"]["get"]) == {
        "$ref": "#/components/schemas/SignalResponseDTO"
    }
    assert _response_schema(paths["/signals/backtest"]["get"])["type"] == "string"
    assert _response_schema(paths["/signals/backtest/sync"]["get"]) == {
        "$ref": "#/components/schemas/BacktestResponseDTO"
    }
    assert _response_schema(paths["/signals/backtest/replay"]["get"]) == {
        "$ref": "#/components/schemas/BacktestReplayResponseDTO"
    }
    assert _response_schema(paths["/signals/portfolio-replay"]["post"]) == {
        "$ref": "#/components/schemas/PortfolioReplayResponseDTO"
    }
    assert _response_schema(paths["/signals/strategies"]["get"]) == {
        "$ref": "#/components/schemas/StrategyListResponseDTO"
    }
    assert _response_schema(paths["/signals/hmm/regimes"]["get"]) == {
        "$ref": "#/components/schemas/HMMResponseDTO"
    }


def test_core_signal_routes_keep_query_fields_and_authentication():
    schema = app.openapi()
    paths = schema["paths"]

    for path in ("/signals/", "/signals/backtest", "/signals/backtest/sync"):
        assert _query_fields(paths[path]["get"]) == SIGNAL_QUERY_FIELDS

    assert _query_fields(paths["/signals/backtest/replay"]["get"]) == {
        "backtest_id": True
    }
    assert _query_fields(paths["/signals/hmm/regimes"]["get"]) == {
        "ticker": True,
        "period": False,
        "interval": False,
        "start": False,
        "end": False,
        "length": False,
        "p_stay_bull": False,
        "p_stay_bear": False,
        "p_stay_chop": False,
        "adaptive": False,
        "min_dwell": False,
        "switch_margin": False,
    }
    for path in paths:
        if path.startswith("/signals"):
            for operation in paths[path].values():
                assert operation["security"] == [{"HTTPBasic": []}]

    security_schemes = schema["components"]["securitySchemes"]
    assert security_schemes["HTTPBasic"] == {"type": "http", "scheme": "basic"}
