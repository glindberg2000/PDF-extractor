import os
import pytest
from dataextractai.parsers.organizer_extractor import OrganizerExtractor


def test_organizer_extractor_basic(tmp_path):
    # Use a small sample PDF for testing
    sample_pdf = "data/_examples/workbooks/22I_VALENTI_T_Organizer_V1_13710.PDF"
    output_dir = tmp_path / "output"
    extractor = OrganizerExtractor(
        str(sample_pdf), str(output_dir), generate_thumbnails=True
    )
    result = extractor.extract()
    # Check structure
    assert "toc" in result
    assert "pages" in result
    assert isinstance(result["pages"], list)
    # At least one page and one TOC entry (if present)
    assert len(result["pages"]) > 0
    # Thumbnails should be present if enabled
    for page in result["pages"]:
        assert os.path.exists(page["pdf_path"])
        if "thumbnail_path" in page:
            assert os.path.exists(page["thumbnail_path"])
    # No critical errors
    assert not result["errors"]
