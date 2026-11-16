import io
import math
import re
import threading
import time
import wave

import numpy as np

from config import SPEECH_MODEL_DIRECTORY

MODEL_DIR = SPEECH_MODEL_DIRECTORY
ENCODERS = ("sense-voice-encoder-int8.onnx", "sense-voice-encoder.onnx")
CMVN_FILE = "am.mvn"
TOKENIZER_FILE = "chn_jpn_yue_eng_ko_spectok.bpe.model"
SAMPLE_RATE = 16000
N_MELS = 80
FRAME_LENGTH = 400
FRAME_SHIFT = 160
FFT_SIZE = 512
LFR_M = 7
LFR_N = 6
PREEMPHASIS = 0.97
LOW_FREQ = 20.0
HIGH_FREQ = 8000.0
EPSILON = 1.19209290e-07
BLANK = 0
LANGUAGE_AUTO = 0
TEXTNORM_WITHITN = 14
MAX_SECONDS = 60
TAGS = re.compile(r"<\|[^|]*\|>")


class SpeechError(ValueError):
    def __init__(self, message, code="speech_input", status=400):
        super().__init__(message)
        self.code, self.status = code, status


_state = {
    "lock": threading.Lock(),
    "session": None,
    "path": None,
    "means": None,
    "scales": None,
    "banks": None,
    "window": None,
    "tokenizer": None,
}


def encoder_path():
    for name in ENCODERS:
        path = MODEL_DIR / name
        if path.is_file():
            return path
    return None


def available():
    return encoder_path() is not None and all(
        (MODEL_DIR / name).is_file() for name in (TOKENIZER_FILE, CMVN_FILE)
    )


def status():
    path = encoder_path()
    return {
        "available": available(),
        "model": path.name if path else None,
        "size_mb": round(path.stat().st_size / 1_048_576, 1) if path else 0,
        "dir": str(MODEL_DIR),
    }


def _floats(text):
    start = text.index("[")
    end = text.index("]", start)
    return np.array(
        [float(value) for value in text[start + 1 : end].replace("\n", " ").split()],
        dtype=np.float32,
    )


def _cmvn():
    raw = (MODEL_DIR / CMVN_FILE).read_text(encoding="utf-8")
    try:
        means = _floats(raw[raw.index("<AddShift>") :])
        scales = _floats(raw[raw.index("<Rescale>") :])
    except ValueError as error:
        raise SpeechError("am.mvn 缺少 AddShift 或 Rescale。") from error
    width = N_MELS * LFR_M
    if means.size != width or scales.size != width:
        raise SpeechError("am.mvn 的维度与 LFR 不一致。")
    return means, scales


def _hz_to_mel(value):
    return 1127.0 * np.log(1.0 + value / 700.0)


def _mel_to_hz(value):
    return 700.0 * (np.exp(value / 1127.0) - 1.0)


def _banks():
    low = _hz_to_mel(LOW_FREQ)
    high = _hz_to_mel(HIGH_FREQ)
    points = _mel_to_hz(np.linspace(low, high, N_MELS + 2))
    bins = np.floor((FFT_SIZE + 1) * points / SAMPLE_RATE).astype(int)
    matrix = np.zeros((N_MELS, FFT_SIZE // 2 + 1), dtype=np.float32)
    for index in range(N_MELS):
        left, middle, right = int(bins[index]), int(bins[index + 1]), int(bins[index + 2])
        if middle <= left:
            middle = min(left + 1, FFT_SIZE // 2)
        if right <= middle:
            right = min(middle + 1, FFT_SIZE // 2 + 1)
        for value in range(left, middle):
            if middle > left:
                matrix[index, value] = (value - left) / (middle - left)
        for value in range(middle, right):
            if right > middle:
                matrix[index, value] = (right - value) / (right - middle)
    return matrix


def _window():
    return np.hamming(FRAME_LENGTH).astype(np.float32)


def _ready():
    with _state["lock"]:
        path = encoder_path()
        if path is None:
            raise SpeechError(
                "服务器尚未安装 SenseVoice 模型，请联系管理员。", "speech_unavailable", 503
            )
        if _state["session"] is not None and _state["path"] == path:
            return
        try:
            import onnxruntime
        except ImportError as error:
            raise SpeechError(
                "服务器缺少语音推理依赖，请联系管理员。", "speech_unavailable", 503
            ) from error
        try:
            import sentencepiece
        except ImportError as error:
            raise SpeechError(
                "服务器缺少语音词表依赖，请联系管理员。", "speech_unavailable", 503
            ) from error
        options = onnxruntime.SessionOptions()
        options.intra_op_num_threads = max(1, min(4, (threading.active_count() or 1)))
        options.log_severity_level = 3
        session = onnxruntime.InferenceSession(
            str(path), sess_options=options, providers=["CPUExecutionProvider"]
        )
        means, scales = _cmvn()
        tokenizer = sentencepiece.SentencePieceProcessor()
        if not tokenizer.load_from_serialized_proto((MODEL_DIR / TOKENIZER_FILE).read_bytes()):
            raise SpeechError("BPE 词表加载失败。")
        # Publish only a fully initialized model; a failed load must be retryable.
        _state.update(
            session=session,
            path=path,
            means=means,
            scales=scales,
            banks=_banks(),
            window=_window(),
            tokenizer=tokenizer,
        )


def _samples(blob):
    if not isinstance(blob, (bytes, bytearray)) or not blob:
        raise SpeechError("没有收到音频。")
    try:
        with wave.open(io.BytesIO(bytes(blob)), "rb") as handle:
            channels = handle.getnchannels()
            width = handle.getsampwidth()
            rate = handle.getframerate()
            frames = handle.readframes(handle.getnframes())
    except (wave.Error, EOFError) as error:
        raise SpeechError("只支持 WAV 音频。") from error
    if width != 2:
        raise SpeechError("音频位深需为 16 位。")
    if (
        channels < 1
        or channels > 8
        or rate < 1
        or rate > 384000
        or len(frames) % (width * channels)
    ):
        raise SpeechError("音频声道、采样率或数据长度无效。")
    if len(frames) / (width * channels * rate) > MAX_SECONDS:
        raise SpeechError("音频超过60秒，请截取后重试。")
    data = np.frombuffer(frames, dtype="<i2").astype(np.float32)
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    data = data / 32768.0
    if rate != SAMPLE_RATE:
        if rate <= 0:
            raise SpeechError("音频采样率无效。")
        length = int(round(len(data) * SAMPLE_RATE / rate))
        if length < 1:
            raise SpeechError("音频太短。")
        data = np.interp(np.linspace(0, len(data) - 1, length), np.arange(len(data)), data).astype(
            np.float32
        )
    if len(data) < FRAME_LENGTH:
        raise SpeechError("音频太短。")
    if len(data) > SAMPLE_RATE * MAX_SECONDS:
        raise SpeechError("音频超过60秒，请截取后重试。")
    if np.max(np.abs(data)) < 0.0001:
        raise SpeechError("录音接近静音，请确认麦克风后重试。", "speech_silent")
    return data


def _fbank(samples):
    banks = _state["banks"]
    window = _state["window"]
    count = 1 + (len(samples) - FRAME_LENGTH) // FRAME_SHIFT
    frames = np.lib.stride_tricks.as_strided(
        samples,
        shape=(count, FRAME_LENGTH),
        strides=(samples.strides[0] * FRAME_SHIFT, samples.strides[0]),
    ).copy()
    frames -= frames.mean(axis=1, keepdims=True)
    frames[:, 1:] -= PREEMPHASIS * frames[:, :-1].copy()
    frames[:, 0] -= PREEMPHASIS * frames[:, 0]
    frames *= window
    spectrum = np.fft.rfft(frames, n=FFT_SIZE, axis=1)
    power = (np.abs(spectrum) ** 2).astype(np.float32)
    mel = power @ banks.T
    np.maximum(mel, EPSILON, out=mel)
    return np.log(mel, out=mel).astype(np.float32)


def _lfr(features):
    total = features.shape[0]
    count = int(math.ceil(total / LFR_N))
    left = (LFR_M - 1) // 2
    padded = np.concatenate([np.tile(features[0:1], (left, 1)), features], axis=0)
    rows = []
    for index in range(count):
        start = index * LFR_N
        block = padded[start : start + LFR_M]
        if block.shape[0] < LFR_M:
            block = np.concatenate(
                [block, np.tile(padded[-1:], (LFR_M - block.shape[0], 1))], axis=0
            )
        rows.append(block.reshape(-1))
    return np.stack(rows).astype(np.float32)


def _decode(ids):
    tokenizer = _state["tokenizer"]
    previous = None
    picked = []
    for value in ids:
        value = int(value)
        if value != previous and value != BLANK:
            picked.append(value)
        previous = value
    text = tokenizer.decode(picked) if picked else ""
    return TAGS.sub("", text).strip()


def transcribe(blob, language=LANGUAGE_AUTO, textnorm=TEXTNORM_WITHITN):
    started = time.perf_counter()
    samples = _samples(blob)
    try:
        _ready()
    except SpeechError:
        raise
    except Exception as error:
        raise SpeechError(
            "服务器语音模型加载失败，请联系管理员后重试。", "speech_unavailable", 503
        ) from error
    features = _fbank(samples)
    stacked = _lfr(features)
    stacked = (stacked + _state["means"]) * _state["scales"]
    session = _state["session"]
    feeds = {}
    for item in session.get_inputs():
        name = item.name.lower()
        if name in ("speech", "x", "feats", "feat", "input", "inputs"):
            feeds[item.name] = stacked[np.newaxis, :, :].astype(np.float32)
        elif name in ("speech_lengths", "speech_length", "x_length", "x_lens", "length", "lengths"):
            feeds[item.name] = np.array([stacked.shape[0]], dtype=np.int64)
        elif name == "language":
            feeds[item.name] = np.array([language], dtype=np.int64)
        elif name in ("text_norm", "textnorm"):
            feeds[item.name] = np.array([textnorm], dtype=np.int64)
    try:
        outputs = session.run(None, feeds)
    except Exception as error:
        raise SpeechError("服务器语音识别失败，请稍后重试。", "speech_inference", 503) from error
    logits = None
    for value in outputs:
        array = np.asarray(value)
        if array.ndim == 3:
            logits = array
            break
    if logits is None:
        raise SpeechError("模型没有返回 logits。")
    ids = logits[0].argmax(axis=-1)
    return {
        "text": _decode(ids),
        "frames": int(stacked.shape[0]),
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
    }
