import pytest
from pydantic import ValidationError

from app.modules.document_collection.schema import DocumentCollectionFieldInput
from app.modules.document_collection.service import next_copy_name, unique_template_name


def test_document_collection_copy_name_uses_available_suffix() -> None:
    existing_names = {"Joining documents - Copy", "Joining documents - Copy (1)"}

    assert next_copy_name("Joining documents", existing_names) == "Joining documents - Copy (2)"


def test_document_collection_create_name_uses_available_suffix_for_duplicates() -> None:
    existing_names = {"Untitled document collection", "Untitled document collection (1)"}

    assert unique_template_name("Untitled document collection", existing_names) == "Untitled document collection (2)"


def test_non_file_field_discards_upload_config() -> None:
    field = DocumentCollectionFieldInput(
        fieldType="SHORT_TEXT",
        name="Current address",
        required=True,
        allowedFormatGroup="VIDEO",
        maxSizeBytes=1024,
    )

    assert field.allowedFormatGroup == "ALL"
    assert field.maxSizeBytes is None


def test_field_name_is_required_after_trimming() -> None:
    with pytest.raises(ValidationError):
        DocumentCollectionFieldInput(fieldType="DATE", name="   ", required=True)
