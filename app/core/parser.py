import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}


def parse_document(file_path: Path, ocr_api_url: str, ocr_api_key: str = "") -> str:
    """
    将文档文件解析为纯文本。

    支持格式：
    - PDF      → PyMuPDF
    - .docx    → python-docx
    - .doc     → LibreOffice 转换 / win32com（Word），均不可用时返回占位文本
    - .wps     → LibreOffice 转换 / win32com（WPS Office → Word），均不可用时返回占位文本
    - .txt     → 直接读取
    - 图片     → PaddleOCR HTTP API
    """
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        return _parse_pdf(file_path)
    elif suffix == ".docx":
        return _parse_docx(file_path)
    elif suffix == ".doc":
        # 先尝试 python-docx（部分 .doc 实际是 OOXML）
        try:
            return _parse_docx(file_path)
        except Exception:
            return _parse_doc_legacy(file_path)
    elif suffix == ".wps":
        # 先尝试 python-docx（新版 WPS 部分文件为 OOXML 格式）
        try:
            return _parse_docx(file_path)
        except Exception:
            return _parse_wps(file_path)
    elif suffix == ".txt":
        return file_path.read_text(encoding="utf-8", errors="ignore")
    elif suffix in IMAGE_EXTENSIONS:
        return _parse_image_ocr(file_path, ocr_api_url, ocr_api_key)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def _parse_pdf(path: Path) -> str:
    import fitz  # PyMuPDF

    doc = fitz.open(str(path))
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text.strip()


def _parse_docx(path: Path) -> str:
    from docx import Document

    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _parse_doc_legacy(path: Path) -> str:
    """
    解析旧版 .doc 二进制文件（Word 97-2003 OLE 格式）。
    依次尝试：LibreOffice headless 转换 → win32com（需安装 Word）。
    均不可用时返回占位提示，避免任务整体失败。
    """
    # 1. LibreOffice headless 转换（推荐，跨平台）
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        with tempfile.TemporaryDirectory() as tmp_dir:
            try:
                subprocess.run(
                    [soffice, "--headless", "--convert-to", "txt:Text",
                     "--outdir", tmp_dir, str(path.absolute())],
                    capture_output=True,
                    timeout=60,
                    check=True,
                )
                txt_path = Path(tmp_dir) / (path.stem + ".txt")
                if txt_path.exists():
                    return txt_path.read_text(encoding="utf-8", errors="ignore").strip()
            except Exception as e:
                logger.warning("LibreOffice 转换 .doc 失败 (%s): %s", path.name, e)

    # 2. win32com COM 自动化（Windows + 已安装 Word）
    try:
        import win32com.client  # type: ignore[import]

        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        try:
            doc = word.Documents.Open(str(path.absolute()))
            text = doc.Content.Text
            doc.Close(False)
        finally:
            word.Quit()
        return text.strip()
    except ImportError:
        pass
    except Exception as e:
        logger.warning("win32com 解析 .doc 失败 (%s): %s", path.name, e)

    # 3. 降级：返回占位文本，任务继续运行
    logger.warning("无法解析 .doc 文件 %s（未找到 LibreOffice 或 Word），已跳过", path.name)
    return f"[无法解析旧版 .doc 文件: {path.name}，请手动转换为 .docx 或 .pdf 后重新上传]"


def _parse_wps(path: Path) -> str:
    """
    解析 WPS Writer .wps 文件。
    依次尝试：LibreOffice headless 转换 → WPS Office COM → Word COM。
    均不可用时返回占位提示，避免任务整体失败。
    """
    # 1. LibreOffice headless 转换（支持 .wps 格式，推荐）
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        with tempfile.TemporaryDirectory() as tmp_dir:
            try:
                subprocess.run(
                    [soffice, "--headless", "--convert-to", "txt:Text",
                     "--outdir", tmp_dir, str(path.absolute())],
                    capture_output=True,
                    timeout=60,
                    check=True,
                )
                txt_path = Path(tmp_dir) / (path.stem + ".txt")
                if txt_path.exists():
                    return txt_path.read_text(encoding="utf-8", errors="ignore").strip()
            except Exception as e:
                logger.warning("LibreOffice 转换 .wps 失败 (%s): %s", path.name, e)

    # 2. WPS Office COM 自动化（Windows + 已安装 WPS Office）
    try:
        import win32com.client  # type: ignore[import]

        wps = win32com.client.Dispatch("WPS.Application")
        wps.Visible = False
        try:
            doc = wps.Documents.Open(str(path.absolute()))
            text = doc.Content.Text
            doc.Close(False)
        finally:
            wps.Quit()
        return text.strip()
    except ImportError:
        pass
    except Exception as e:
        logger.warning("WPS Office COM 解析 .wps 失败 (%s): %s", path.name, e)

    # 3. Word COM 自动化（部分 WPS 安装会注册 Word.Application 兼容接口）
    try:
        import win32com.client  # type: ignore[import]

        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        try:
            doc = word.Documents.Open(str(path.absolute()))
            text = doc.Content.Text
            doc.Close(False)
        finally:
            word.Quit()
        return text.strip()
    except ImportError:
        pass
    except Exception as e:
        logger.warning("Word COM 解析 .wps 失败 (%s): %s", path.name, e)

    # 4. 降级：返回占位文本，任务继续运行
    logger.warning("无法解析 .wps 文件 %s（未找到 LibreOffice 或 WPS/Word COM），已跳过", path.name)
    return f"[无法解析 .wps 文件: {path.name}，请安装 LibreOffice 或确认 WPS Office 已正确安装]"


def _parse_image_ocr(path: Path, ocr_api_url: str, ocr_api_key: str) -> str:
    headers = {}
    if ocr_api_key:
        headers["ly-api-key"] = ocr_api_key

    with open(path, "rb") as f:
        resp = httpx.post(
            ocr_api_url,
            files={"file": (path.name, f, "application/octet-stream")},
            headers=headers,
            timeout=60,
        )
    resp.raise_for_status()
    data = resp.json()

    # 兼容常见响应格式：
    # {"results": [{"text": "..."}, ...]}  或  {"data": {"text": "..."}}
    if "results" in data:
        return "\n".join(item.get("text", "") for item in data["results"])
    if "data" in data and "text" in data["data"]:
        return data["data"]["text"]
    # 兜底：返回原始 JSON 文本，供人工排查
    return str(data)
