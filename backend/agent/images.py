import base64
import re


def image_url(image):
    if image is None:
        return None
    if not isinstance(image, dict):
        raise ValueError("图片格式无效。")
    value = image.get("data_url", "")
    if not isinstance(value, str) or len(value) > 2800000:
        raise ValueError("选区图片过大，请缩小范围。")
    match = re.fullmatch(r"data:image/(png|jpeg);base64,([A-Za-z0-9+/=]+)", value)
    if not match:
        raise ValueError("只支持内存中的PNG/JPEG选区图片。")
    try:
        raw = base64.b64decode(match[2], validate=True)
    except ValueError as error:
        raise ValueError("图片编码无效。") from error
    if len(raw) > 2000000 or not (
        raw.startswith(b"\x89PNG\r\n\x1a\n")
        if match[1] == "png"
        else raw.startswith(b"\xff\xd8\xff")
    ):
        raise ValueError("图片内容无效或过大。")
    return value


def image_urls(images):
    if images is None:
        return []
    if isinstance(images, dict):
        images = [images]
    if not isinstance(images, list):
        raise ValueError("图片格式无效。")
    return [url for url in (image_url(item) for item in images) if url]


def turn_images(turn):
    if not isinstance(turn, dict):
        return []
    images = turn.get("images")
    if isinstance(images, list):
        return [item for item in images if isinstance(item, dict)]
    single = turn.get("image")
    return [single] if isinstance(single, dict) else []
