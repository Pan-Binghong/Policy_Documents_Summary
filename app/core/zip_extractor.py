import zipfile
from pathlib import Path


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".wps", ".txt", ".jpg", ".jpeg", ".png", ".bmp", ".tiff"}


def _decode_zip_filename(member: zipfile.ZipInfo) -> str:
    """
    修正 zip 条目文件名编码。
    国内 Windows 打包的 zip 文件名通常为 GBK 编码，且未设置 UTF-8 标志位（bit 11）。
    Python zipfile 会错误地将其按 CP437 解码，导致中文路径乱码。
    此函数将 CP437 解码结果还原为原始字节后，再按 GBK 重新解码。
    """
    # bit 11 为 UTF-8 标志：已设置则文件名本身已是正确 UTF-8，直接返回
    if member.flag_bits & 0x800:
        return member.filename
    try:
        raw_bytes = member.filename.encode("cp437")
        return raw_bytes.decode("gbk")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return member.filename


def safe_extract(zip_path: Path, dest_dir: Path) -> list[Path]:
    """
    解压 .zip 文件，返回所有解压出的文件路径列表。

    安全校验：拒绝包含路径穿越（..）或绝对路径的条目，
    防止 zip-slip 攻击。
    兼容国内 Windows 打包的 GBK 文件名 zip。
    """
    if not zipfile.is_zipfile(zip_path):
        raise ValueError(
            f"文件 '{zip_path.name}' 不是有效的 ZIP 文件。"
            "请确认文件未损坏，且扩展名与实际格式一致（不支持 .rar/.7z 等格式）。"
        )

    dest_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []

    with zipfile.ZipFile(zip_path, "r") as zf:
        seen_names: set[str] = set()
        for idx, member in enumerate(zf.infolist()):
            fixed_name = _decode_zip_filename(member)
            member_path = Path(fixed_name)

            # 安全校验
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError(f"Unsafe path detected in zip entry: {member.filename!r}")

            # 跳过目录条目
            if member.is_dir():
                continue

            # 拍平目录结构：只保留文件名，避免 Windows MAX_PATH(260) 限制。
            # ZIP 内嵌套目录名过长（常见于中文路径）会导致 FileNotFoundError。
            filename = member_path.name
            if filename in seen_names:
                filename = f"{idx}_{filename}"
            seen_names.add(filename)

            dest = dest_dir / filename
            with zf.open(member) as src, dest.open("wb") as dst:
                dst.write(src.read())

            if dest.suffix.lower() in SUPPORTED_EXTENSIONS:
                extracted.append(dest)

    if not extracted:
        raise ValueError("Zip contains no supported document files (.pdf/.docx/.txt/image)")

    return extracted
