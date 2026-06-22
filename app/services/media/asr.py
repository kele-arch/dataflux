# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/media/asr.py
# @Created: 2026/6/22 11:52
# @LastModified: 
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: Whisper ASR 服务封装, 全局单例, 线程安全懒加载

import threading

from faster_whisper import WhisperModel
from opencc import OpenCC
from app.core import logger
from app.core.config import settings
from typing import Optional

_asr_instance: Optional["WhisperASR"] = None
_asr_lock = threading.Lock()


def get_asr_service() -> "WhisperASR":
    """
    全局单例, 第一次调用时初始化模型
    加锁保证多 Worker 线程并发安全——只加载一份模型到内存
    """
    global _asr_instance
    if _asr_instance is not None:
        return _asr_instance

    with _asr_lock:
        if _asr_instance is not None:
            return _asr_instance  # 双重检查, 等锁期间已有人初始化
        logger.info("首次调用, 正在加载 Whisper 模型, 请稍候...")
        _asr_instance = WhisperASR(
            model_path=getattr(settings, "WHISPER_MODEL_PATH", "./large-v3"),
            device=getattr(settings, "WHISPER_DEVICE", "cuda"),
            compute_type=getattr(settings, "WHISPER_COMPUTE_TYPE", "float16"),
            simplified=True,
        )
        logger.info("Whisper 模型加载完毕")
    return _asr_instance


class WhisperASR:
    def __init__(
        self,
        model_path: str = "./large-v3",
        device: str = "cuda",
        compute_type: str = "float16",
        simplified: bool = True,
    ):
        self.model = WhisperModel(
            model_size_or_path=model_path,
            device=device,
            compute_type=compute_type,
            num_workers=1,
            cpu_threads=4,
        )
        self.simplified = simplified
        self.cc = OpenCC("t2s") if simplified else None

    def transcribe(self, audio_path, language: str = "zh") -> str:
        from pathlib import Path
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"音频文件不存在: {path}")

        segments, info = self.model.transcribe(
            str(path),
            language=language,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500, threshold=0.5),
            without_timestamps=True,
        )
        text = "".join(segment.text for segment in segments)
        if self.cc:
            text = self.cc.convert(text)
        return text.strip()