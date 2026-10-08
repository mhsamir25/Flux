"""POST /api/data/upload: public"""
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.csv_io.parser import FileParsingError, parse_csv
from app.csv_io.xlsx_io import parse_xlsx
from app.data_cache import data_reference_cache
from app.rate_limit import tiered_rate_limit
from app.schemas.data import DataUploadResponse

router = APIRouter(prefix="/api/data", tags=["data"])

_ALLOWED_EXTENSIONS = {"csv", "xlsx"}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.post("/upload", response_model=DataUploadResponse)
@tiered_rate_limit
async def upload_data(
    request: Request,  # required by slowapi's @tiered_rate_limit, unused otherwise
    file: UploadFile = File(...),
    sheet_name: Optional[str] = Form(None),
) -> DataUploadResponse:
    extension = _extension_of(file.filename)
    if extension not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only .csv and .xlsx files are supported.")

    raw = await file.read()
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400, detail=f"File exceeds the {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit."
        )

    try:
        flux_df = parse_csv(raw) if extension == "csv" else parse_xlsx(raw, sheet_name=sheet_name)
    except FileParsingError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    reference_id = data_reference_cache.put(flux_df, raw=raw)
    return DataUploadResponse(
        data_reference_id=reference_id, columns=flux_df.schema.columns, row_count=flux_df.total_row_count,
    )


def _extension_of(filename: Optional[str]) -> str:
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()
