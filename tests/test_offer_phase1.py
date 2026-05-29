import pytest
from fastapi import HTTPException

from app.models.recruitment import PipelineStage, StageType
from app.modules.jobs.service import _assert_single_stage_type
from app.modules.offers.service import next_template_copy_name, unique_template_name


def test_template_copy_name_uses_first_available_suffix() -> None:
    existing_names = {"Offer Letter", "Offer Letter (1)"}

    assert next_template_copy_name("Offer Letter", existing_names) == "Offer Letter (2)"


def test_template_copy_name_increments_from_copy_root() -> None:
    existing_names = {"Offer Letter", "Offer Letter (1)", "Offer Letter (2)"}

    assert next_template_copy_name("Offer Letter (1)", existing_names) == "Offer Letter (3)"


def test_template_create_name_uses_available_suffix_for_duplicates() -> None:
    existing_names = {"Untitled offer template", "Untitled offer template (1)"}

    assert unique_template_name("Untitled offer template", existing_names) == "Untitled offer template (2)"


def test_single_offer_stage_guard_blocks_duplicate() -> None:
    stages = [
        PipelineStage(id="stage-1", stageType=StageType.OFFER),
        PipelineStage(id="stage-2", stageType=StageType.DEFAULT),
    ]

    with pytest.raises(HTTPException) as exc:
        _assert_single_stage_type(stages, StageType.OFFER)

    assert exc.value.status_code == 409
    assert exc.value.detail == "This job already has an offer stage."


def test_single_stage_guard_allows_current_stage_update() -> None:
    stages = [
        PipelineStage(id="stage-1", stageType=StageType.OFFER),
        PipelineStage(id="stage-2", stageType=StageType.DEFAULT),
    ]

    _assert_single_stage_type(stages, StageType.OFFER, excluded_stage_id="stage-1")
