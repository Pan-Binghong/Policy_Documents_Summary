import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from fastapi.responses import FileResponse
from typing import List

from app.core import extractor, parser, reporter, zip_extractor
from app.core.config import settings
from app.core.database import get_session
from app.models.db import PolicyRecord, Task

logger = logging.getLogger(__name__)

router = APIRouter()

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")

# 支持直接上传的单文件格式（不含 zip，zip 单独处理）
SINGLE_FILE_EXTENSIONS = {".pdf", ".docx", ".doc", ".wps", ".jpg", ".jpeg", ".png", ".bmp", ".tiff"}


@router.post("/upload", summary="批量上传文件（.zip / .pdf / .docx / 图片），所有文件合并为一个任务，导出一份 Excel")
async def upload_files(background_tasks: BackgroundTasks, files: List[UploadFile]):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    UPLOAD_DIR.mkdir(exist_ok=True)

    task_id = str(uuid.uuid4())
    zip_paths: list[Path] = []
    single_paths: list[Path] = []
    zip_idx = 0
    single_idx = 0

    for file in files:
        if not file.filename:
            continue
        suffix = Path(file.filename).suffix.lower()
        content = await file.read()

        if suffix == ".zip":
            dest = UPLOAD_DIR / f"{task_id}_z{zip_idx}.zip"
            dest.write_bytes(content)
            zip_paths.append(dest)
            zip_idx += 1
        elif suffix in SINGLE_FILE_EXTENSIONS:
            dest = UPLOAD_DIR / f"{task_id}_s{single_idx}{suffix}"
            dest.write_bytes(content)
            single_paths.append(dest)
            single_idx += 1
        else:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件格式：'{file.filename}'。支持 .zip / .pdf / .docx / .doc / .wps / .jpg / .jpeg / .png / .bmp / .tiff",
            )

    if not zip_paths and not single_paths:
        raise HTTPException(status_code=400, detail="未找到有效文件")

    filenames = ",".join(f.filename for f in files if f.filename)
    with get_session() as db:
        db.add(Task(id=task_id, status="pending", filename=filenames))
        db.commit()

    background_tasks.add_task(_process_task, task_id, zip_paths, single_paths)
    return {"task_id": task_id, "filenames": [f.filename for f in files if f.filename], "status": "pending"}


@router.get("/tasks/{task_id}", summary="查询任务状态")
def get_task(task_id: str):
    with get_session() as db:
        task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task_id": task.id, "status": task.status, "error": task.error_msg}


@router.get("/tasks/{task_id}/download", summary="下载本次任务的 Excel 报告")
def download_result(task_id: str):
    with get_session() as db:
        task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "done":
        raise HTTPException(status_code=400, detail=f"Task is not ready (status: {task.status})")

    output_path = OUTPUT_DIR / f"{task_id}.xlsx"
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Output file not found")

    return FileResponse(
        path=str(output_path),
        filename=f"policy_summary_{task_id[:8]}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _process_task(task_id: str, zip_paths: list[Path], single_paths: list[Path]) -> None:
    """后台任务：处理 ZIP 和单文件 → LLM 提取 → 写库 → 导出一份合并 Excel。

    每个 ZIP 内的所有文档合并为一次 LLM 提取；每个单文件独立进行一次 LLM 提取。
    """

    def _set_status(status: str, error_msg: str | None = None) -> None:
        with get_session() as db:
            task = db.get(Task, task_id)
            if task:
                task.status = status
                task.error_msg = error_msg
                db.commit()

    _set_status("processing")

    try:
        all_rows = []

        # ── ZIP 文件：解压 → 合并文本 → 一次 LLM 提取 ──
        for idx, zip_path in enumerate(zip_paths):
            extract_dir = UPLOAD_DIR / f"{task_id}_z{idx}"
            logger.info("Task %s ZIP[%d/%d] 开始解压: %s", task_id, idx + 1, len(zip_paths), zip_path.name)
            files = zip_extractor.safe_extract(zip_path, extract_dir)
            logger.info("Task %s ZIP[%d] 解压完成，共 %d 个文件", task_id, idx + 1, len(files))

            texts = []
            for file_path in files:
                logger.info("Task %s 解析文件: %s", task_id, file_path.name)
                text = parser.parse_document(
                    file_path,
                    ocr_api_url=settings.paddle_ocr_api_url,
                    ocr_api_key=settings.paddle_ocr_api_key,
                )
                logger.info("Task %s 文件解析完成，文本长度 %d 字符", task_id, len(text))
                texts.append(text)

            merged_text = "\n\n---\n\n".join(texts) if len(texts) > 1 else texts[0]
            logger.info("Task %s ZIP[%d] 开始 LLM 提取，合并文本 %d 字符", task_id, idx + 1, len(merged_text))
            rows = extractor.extract(merged_text)
            logger.info("Task %s ZIP[%d] LLM 提取完成，共 %d 行", task_id, idx + 1, len(rows))
            all_rows.extend(rows)

        # ── 单文件：直接解析 → 独立一次 LLM 提取 ──
        for idx, file_path in enumerate(single_paths):
            logger.info("Task %s 单文件[%d/%d] 解析: %s", task_id, idx + 1, len(single_paths), file_path.name)
            text = parser.parse_document(
                file_path,
                ocr_api_url=settings.paddle_ocr_api_url,
                ocr_api_key=settings.paddle_ocr_api_key,
            )
            logger.info("Task %s 单文件[%d] 解析完成，文本长度 %d 字符", task_id, idx + 1, len(text))
            logger.info("Task %s 单文件[%d] 开始 LLM 提取", task_id, idx + 1)
            rows = extractor.extract(text)
            logger.info("Task %s 单文件[%d] LLM 提取完成，共 %d 行", task_id, idx + 1, len(rows))
            all_rows.extend(rows)

        # ── 写入 MySQL ──
        with get_session() as db:
            for row in all_rows:
                db.add(PolicyRecord(task_id=task_id, **row.model_dump()))
            db.commit()
            records = db.query(PolicyRecord).filter(PolicyRecord.task_id == task_id).all()

        # ── 导出 Excel ──
        reporter.export_to_excel(task_id, records, OUTPUT_DIR)

        _set_status("done")

    except Exception as e:
        logger.exception("Task %s failed", task_id)
        _set_status("error", error_msg=str(e))
