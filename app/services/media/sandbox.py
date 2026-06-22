# -- coding: utf-8 --
# @Author: 胡H
# @File: app/services/media/sandbox.py
# @Created: 2026/6/22
# @LastModified:
# Copyright (c) 2026 by 胡H, All Rights Reserved.
# @desc: Whisper 进程隔离沙箱 — 子进程崩溃不影响主 Worker

import asyncio
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor

# 强制 spawn, 规避 Linux fork 导致的 CUDA 死锁
try:
    mp.set_start_method("spawn")
except RuntimeError:
    pass  # 已经设置过


def _isolated_whisper_task(
    local_path: str,
    language: str,
    model_path: str,
    device: str,
    compute_type: str,
    simplified: bool,
) -> str:
    """
    完全运行在独立子进程中  所有重量级库的 import 和模型加载
    必须在此函数内部完成——随子进程创建, 随子进程销毁  
    """
    from pathlib import Path as _Path
    from app.services.media.converter import media_converter
    from app.services.media.asr import WhisperASR

    # 加载模型(子进程退出时自动释放显存/内存)
    asr = WhisperASR(
        model_path=model_path,
        device=device,
        compute_type=compute_type,
        simplified=simplified,
    )

    wav_path = None
    local = _Path(local_path)
    try:
        wav_path = media_converter.to_wav(local)
        text = asr.transcribe(wav_path, language=language)
        return text
    finally:
        if wav_path and wav_path != local and wav_path.exists():
            wav_path.unlink(missing_ok=True)


async def run_whisper_in_sandbox(
    local_path: str,
    language: str = "zh",
    *,
    timeout: int = 300,
    model_path: str = "./large-v3",
    device: str = "cuda",
    compute_type: str = "float16",
    simplified: bool = True,
) -> str:
    """
    异步包装器: 通过 ProcessPoolExecutor 调度隔离任务  
    - 子进程崩溃(段错误/OOM)-> 主进程安然无恙
    - 超时 -> 子进程被 OS 强制回收
    """
    loop = asyncio.get_running_loop()

    with ProcessPoolExecutor(max_workers=1) as executor:
        try:
            text = await asyncio.wait_for(
                loop.run_in_executor(
                    executor,
                    _isolated_whisper_task,
                    local_path,
                    language,
                    model_path,
                    device,
                    compute_type,
                    simplified,
                ),
                timeout=timeout,
            )
            return text
        except asyncio.TimeoutError:
            raise RuntimeError(
                f"音视频解析超时 ({timeout}s), 子进程已被操作系统强制回收"
            )
        except Exception:
            # 段错误、OOM 等子进程异常——向上抛、主进程无影响
            raise
