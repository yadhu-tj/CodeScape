from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


def api_response(data: Any, message: str = "Success", status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": True, "data": jsonable_encoder(data), "message": message},
    )


def error_response(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "data": None, "message": message},
    )
