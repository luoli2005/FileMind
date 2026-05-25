"""高级重复检测模块 — 相似图片 + 重复视频"""

import subprocess
import tempfile
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field

try:
    from PIL import Image
    import imagehash
    HAS_IMAGEHASH = True
except ImportError:
    HAS_IMAGEHASH = False

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif", ".heic"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg"}

# 汉明距离阈值：越小越严格
# 0 = 完全相同, 1-5 = 非常相似, 6-10 = 相似, >10 = 不同
IMAGE_SIMILARITY_THRESHOLD = 10


@dataclass
class SimilarGroup:
    """一组相似文件"""
    group_id: int
    files: list = field(default_factory=list)
    similarity_type: str = ""  # "similar_image" | "similar_video"
    hash_distance: int = 0


def _compute_phash(filepath: Path):
    """计算图片感知哈希 (pHash)"""
    try:
        img = Image.open(filepath)
        return imagehash.phash(img)
    except Exception:
        return None


def _compute_dhash(filepath: Path):
    """计算图片差异哈希 (dHash) — 更快，适合大图"""
    try:
        img = Image.open(filepath)
        return imagehash.dhash(img)
    except Exception:
        return None


def _extract_video_frame(filepath: Path) -> Path:
    """用 ffmpeg 提取视频第一帧"""
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.close()
        subprocess.run(
            ["ffmpeg", "-i", str(filepath), "-vframes", "1", "-y", tmp.name],
            capture_output=True, timeout=10,
        )
        result = Path(tmp.name)
        if result.exists() and result.stat().st_size > 0:
            return result
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _video_metadata(filepath: Path) -> dict:
    """提取视频元数据（时长、分辨率）"""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(filepath)],
            capture_output=True, text=True, timeout=10,
        )
        import json
        data = json.loads(result.stdout)
        info = {}
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                info["width"] = stream.get("width")
                info["height"] = stream.get("height")
                info["codec"] = stream.get("codec_name")
                break
        fmt = data.get("format", {})
        info["duration"] = float(fmt.get("duration", 0))
        info["size"] = int(fmt.get("size", 0))
        return info
    except Exception:
        return {}


def find_similar_images(files: list, threshold: int = IMAGE_SIMILARITY_THRESHOLD) -> list:
    """检测相似图片（感知哈希）

    Args:
        files: FileInfo 列表
        threshold: 汉明距离阈值（默认 10）

    Returns:
        list[SimilarGroup] 相似图片组
    """
    if not HAS_IMAGEHASH:
        return []

    # 筛选图片文件
    image_files = [f for f in files if f.extension.lower() in IMAGE_EXTENSIONS]
    if len(image_files) < 2:
        return []

    # 计算哈希
    hash_map = {}  # filepath -> phash
    for fi in image_files:
        h = _compute_phash(fi.path)
        if h is not None:
            hash_map[fi.path] = h

    # 两两比较，聚类分组
    files_with_hash = list(hash_map.keys())
    n = len(files_with_hash)
    if n < 2:
        return []

    # Union-Find 分组
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i in range(n):
        for j in range(i + 1, n):
            fi_path = files_with_hash[i]
            fj_path = files_with_hash[j]
            dist = hash_map[fi_path] - hash_map[fj_path]
            if dist < threshold:
                union(i, j)

    # 收集分组
    groups = defaultdict(list)
    for i in range(n):
        root = find(i)
        groups[root].append(files_with_hash[i])

    # 构建结果
    result = []
    group_id = 0
    for root, paths in groups.items():
        if len(paths) < 2:
            continue
        group_id += 1
        file_list = [fi for fi in files if fi.path in paths]
        result.append(SimilarGroup(
            group_id=group_id,
            files=file_list,
            similarity_type="similar_image",
        ))

    return result


def find_duplicate_videos(files: list) -> list:
    """检测重复视频（首帧哈希 + 元数据比对）

    Returns:
        list[SimilarGroup] 重复视频组
    """
    if not HAS_IMAGEHASH:
        return []

    video_files = [f for f in files if f.extension.lower() in VIDEO_EXTENSIONS]
    if len(video_files) < 2:
        return []

    # 提取首帧哈希
    frame_hashes = {}  # filepath -> (phash, metadata)
    for fi in video_files:
        # 先用元数据粗筛
        meta = _video_metadata(fi.path)

        # 提取首帧
        frame_path = _extract_video_frame(fi.path)
        if frame_path:
            h = _compute_phash(frame_path)
            frame_path.unlink(missing_ok=True)
            if h is not None:
                frame_hashes[fi.path] = (h, meta)

    # 两两比较
    files_with_hash = list(frame_hashes.keys())
    n = len(files_with_hash)
    if n < 2:
        return []

    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i in range(n):
        for j in range(i + 1, n):
            fi_path = files_with_hash[i]
            fj_path = files_with_hash[j]
            hi, mi = frame_hashes[fi_path]
            hj, mj = frame_hashes[fj_path]

            # 首帧哈希相似
            frame_dist = hi - hj

            # 元数据相似（时长差 < 2秒，分辨率相同）
            duration_match = abs(mi.get("duration", 0) - mj.get("duration", 0)) < 2
            resolution_match = (mi.get("width") == mj.get("width") and
                               mi.get("height") == mj.get("height"))

            if frame_dist < 10 or (duration_match and resolution_match):
                union(i, j)

    # 收集分组
    groups = defaultdict(list)
    for i in range(n):
        root = find(i)
        groups[root].append(files_with_hash[i])

    result = []
    group_id = 0
    for root, paths in groups.items():
        if len(paths) < 2:
            continue
        group_id += 1
        file_list = [fi for fi in files if fi.path in paths]
        result.append(SimilarGroup(
            group_id=group_id,
            files=file_list,
            similarity_type="similar_video",
        ))

    return result


def find_all_advanced_duplicates(files: list) -> dict:
    """运行所有高级重复检测

    Returns:
        {
            "similar_images": list[SimilarGroup],
            "duplicate_videos": list[SimilarGroup],
            "imagehash_available": bool,
        }
    """
    return {
        "similar_images": find_similar_images(files),
        "duplicate_videos": find_duplicate_videos(files),
        "imagehash_available": HAS_IMAGEHASH,
    }
