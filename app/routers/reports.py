"""Reports router."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Report, SimulationRun

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/", response_class=HTMLResponse)
async def list_reports(request: Request, db: Session = Depends(get_db)):
    templates = request.app.state.templates

    reports = db.query(Report).order_by(
        Report.generated_at.desc()
    ).limit(50).all()

    return await templates.TemplateResponse("reports.html", {
        "request": request,
        "reports": reports,
    })


@router.get("/download/{report_id}")
async def download_report(report_id: str, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report or not report.file_path:
        return JSONResponse({"error": "Report not found"}, status_code=404)

    media_types = {
        "markdown": "text/markdown",
        "json": "application/json",
        "pdf": "application/pdf",
    }

    ext_map = {"markdown": "md", "json": "json", "pdf": "pdf"}
    ext = ext_map.get(str(report.format), "txt")

    return FileResponse(
        path=report.file_path,
        filename=f"f1_report_{report.id[:8]}.{ext}",
        media_type=media_types.get(str(report.format), "application/octet-stream"),
    )
