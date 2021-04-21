import pytest
import re
from nuvo_serial import get_nuvo
from .command_response import command_patterns, responses

# TEST_ZONE = 1
# TEST_SOURCE = 4
# PORT_URL = "loop://"
# model = None


# def pytest_addoption(parser):
#     parser.addoption("--model", action="store", help="model name")


# @pytest.fixture
# def params(request):
#     params = {}
#     params["model"] = request.config.getoption("--model")

#     if params['model'] is None:
#         pytest.fail()

#     global model
#     model = params["model"]

#     return params


# @pytest.fixture
# def port_url():
#     return PORT_URL


# @pytest.fixture
# def zone():
#     return TEST_ZONE


# @pytest.fixture
# def source():
#     return TEST_SOURCE


# @pytest.fixture
# def nuvo(params):
#     return get_nuvo(PORT_URL, params["model"])


# def mock_process_request(cls, request_string):

#     found_match = None

#     for command, pattern in command_patterns[model].items():
#         if re.search(pattern, request_string):
#             found_match = responses[model][command]
#             break

#     return found_match


# @pytest.fixture
# def mock_return_value_master(request, monkeypatch):
#     import pdb; pdb.set_trace()
#     global model
#     model = getattr(request.module, "MODEL")
#     monkeypatch.setattr(NuvoSync, "_process_request", mock_process_request)

# @pytest.fixture
# def get_process_request():
#     return mock_process_request


# def mock_process_request(cls, request_string):

#     found_match = None

#     for command, pattern in command_patterns[model].items():
#         if re.search(pattern, request_string):
#             found_match = responses[model][command]
#             break

#     return found_match


# @pytest.fixture
# def mock_return_value(params, monkeypatch):
#     monkeypatch.setattr(NuvoSync, "_process_request", mock_process_request)
