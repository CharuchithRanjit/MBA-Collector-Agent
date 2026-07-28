import pytest

from chief.llm.fake import FakeLLM


def test_fake_llm_returns_canned_response_for_known_purpose():
    llm = FakeLLM(complete_responses={"summarize": "a canned summary"})

    response = llm.complete(prompt="anything", purpose="summarize", prompt_version="v1")

    assert response.text == "a canned summary"


def test_fake_llm_raises_for_unregistered_purpose():
    llm = FakeLLM(complete_responses={"summarize": "a canned summary"})

    with pytest.raises(KeyError):
        llm.complete(prompt="anything", purpose="unregistered", prompt_version="v1")
