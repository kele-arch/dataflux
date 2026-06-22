# -- coding: utf-8 --
# @Author: 胡H
# @File: app/api/v1/media.py
# @Created: 2026/6/22
# @LastModified:
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: 音视频解析接口 — 上传媒体文件, 在进程隔离沙箱中返回 Whisper 转写文本

from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, UploadFile, File, Form

from app.core import logger
from app.schemas.response import BaseResponse

router = APIRouter(prefix="/media", tags=["音视频解析"])


@router.post("/transcribe", summary="上传音视频文件并返回转写文本", response_model=BaseResponse)
async def transcribe_media(
    file: UploadFile = File(..., description="音视频文件"),
    language: str = Form(default="zh", description="语言代码: zh/en/ja..."),
):
    """
    上传音视频文件（mp4/mp3/wav/mkv/avi 等），在独立子进程中转写为文本。
    ffmpeg + Whisper 运行在进程隔离沙箱中，崩溃不影响主服务。
    """
    from app.services.media.converter import media_converter
    from app.services.media.sandbox import run_whisper_in_sandbox
    from app.core.config import settings

    # 保存上传文件
    suffix = Path(file.filename or "upload").suffix or ".tmp"
    tmp_file = NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp_file.write(await file.read())
        tmp_file.close()

        local_path = tmp_file.name
        path_obj = Path(local_path)

        if not media_converter.is_media(path_obj):
            path_obj.unlink(missing_ok=True)
            return BaseResponse(
                code=0,
                msg=f"不支持的文件类型 ({path_obj.suffix})，支持: mp4/mkv/avi/mov/mp3/wav/m4a/aac/flac",
            )

        file_type = "video" if media_converter.is_video(path_obj) else "audio"

        text = await run_whisper_in_sandbox(
            local_path,
            language=language,
            timeout=300,
            model_path=getattr(settings, "WHISPER_MODEL_PATH", "./large-v3"),
            device=getattr(settings, "WHISPER_DEVICE", "cuda"),
            compute_type=getattr(settings, "WHISPER_COMPUTE_TYPE", "float16"),
            simplified=True,
        )

        if not text:
            return BaseResponse(code=0, msg="转写结果为空，可能文件中没有有效语音")

        return BaseResponse(data={
            "file_name": file.filename,
            "file_type": file_type,
            "text": text,
            "text_length": len(text),
        }, msg="转写成功")

    except RuntimeError as e:
        logger.error(f"音视频转写失败 [{file.filename}]: {e}")
        return BaseResponse(code=0, msg=str(e))

    finally:
        # 清理上传文件（WAV 由沙箱内部清理）
        try:
            Path(local_path).unlink(missing_ok=True)
        except Exception:
            pass
