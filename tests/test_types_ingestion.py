"""Unit tests for municipal deed, SEC filing, and offering memorandum ingestion schemas."""

from datetime import date

import pytest
from pydantic import ValidationError

from autonomous_cre_underwriting.types.ingestion import (
    DeedType,
    IngestionJob,
    IngestionSourceType,
    IngestionStatus,
    SECFiling,
    SECFilingType,
)


def test_deed_record_attributes(sample_deed):
    """Ensure deed record holds recorded instrument details."""
    assert sample_deed.parcel_number == "01-0203-0405-0000"
    assert sample_deed.deed_type == DeedType.SPECIAL_WARRANTY_DEED
    assert sample_deed.consideration_amount == 21500000.0
    assert sample_deed.verified is True
    assert sample_deed.id is not None
    assert sample_deed.created_at is not None


def test_sec_filing_cik_padding():
    """CIK should be automatically zero-padded to 10 digits."""
    filing = SECFiling(
        accession_number="0001234567-26-000001",
        cik="1234567",
        company_name="Test Sponsor LP",
        form_type=SECFilingType.FORM_10K,
        filing_date=date(2026, 1, 15),
    )
    assert filing.cik == "0001234567"
    assert len(filing.cik) == 10


def test_sec_filing_invalid_cik():
    """Non-numeric CIK or CIK > 10 digits must fail validation."""
    with pytest.raises(ValidationError):
        SECFiling(
            accession_number="0001234567-26-000001",
            cik="INVALID_CIK",
            company_name="Test Sponsor LP",
            form_type=SECFilingType.FORM_10K,
            filing_date=date(2026, 1, 15),
        )
    with pytest.raises(ValidationError):
        SECFiling(
            accession_number="0001234567-26-000001",
            cik="1234567890123",
            company_name="Test Sponsor LP",
            form_type=SECFilingType.FORM_10K,
            filing_date=date(2026, 1, 15),
        )


def test_sec_filing_numeric_int_cik():
    """Integer CIK input should be converted to string."""
    filing = SECFiling(
        accession_number="0001234567-26-000001",
        cik=123456,  # integer type
        company_name="Test Sponsor LP",
        form_type=SECFilingType.FORM_10K,
        filing_date=date(2026, 1, 15),
    )
    assert filing.cik == "0000123456"


def test_document_chunk_properties(sample_document_chunk):
    """Document chunk fields and vector dimensionality."""
    assert sample_document_chunk.document_id == "om-travis-001"
    assert sample_document_chunk.chunk_index == 3
    assert len(sample_document_chunk.embedding) == 4
    assert sample_document_chunk.source_type == IngestionSourceType.OFFERING_MEMORANDUM


def test_offering_memorandum_aggregation(sample_offering_memorandum):
    """Broker OM metadata and nested chunks."""
    assert sample_offering_memorandum.deal_id == "deal-atx-001"
    assert sample_offering_memorandum.claimed_cap_rate == 0.0546
    assert len(sample_offering_memorandum.chunks) == 1
    assert sample_offering_memorandum.page_count == 48


def test_ingestion_job_lifecycle():
    """Ingestion job tracking states and error reporting."""
    job = IngestionJob(
        source_type=IngestionSourceType.MUNICIPAL_DEED,
        status=IngestionStatus.PROCESSING,
        source_uri="traviscountytx.gov/deeds/search?apn=01-0203-0405-0000",
    )
    assert job.status == IngestionStatus.PROCESSING
    assert job.items_ingested == 0

    job.items_ingested = 1
    job.status = IngestionStatus.COMPLETED
    assert job.status == IngestionStatus.COMPLETED
