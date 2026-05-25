"""文件价值/用途/风险智能分析模块"""

from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict


WORK_KEYWORDS = [
    "报告", "方案", "合同", "invoice", "resume", "简历", "offer",
    "proposal", "report", "meeting", "会议", "需求", "spec", "brief",
    "budget", "预算", "报价", "报价单", "项目", "project",
]

STUDY_KEYWORDS = [
    "课件", "笔记", "homework", "assignment", "论文", "教材",
    "lecture", "tutorial", "习题", "考试", "复习", "课程",
    "study", "notes", "textbook", "syllabus",
]

PERSONAL_KEYWORDS = [
    "截图", "screenshot", "capture", "photo", "照片",
    "travel", "旅行", "vacation", "holiday", "生日", "birthday",
]

TEMP_KEYWORDS = [
    "temp", "tmp", "cache", "缓存", "下载", "download",
    "crdownload", "partial",
]


@dataclass
class FileAnalysis:
    value: str = "medium"
    purpose: str = "unknown"
    risk: str = "safe"
    confidence: float = 0.3
    reasoning: str = ""
    recommended_action: str = "archive"
    content_type: str = ""
    content_confidence: float = 0.0


@dataclass
class AnalysisResult:
    file_analyses: dict = field(default_factory=dict)
    value_stats: dict = field(default_factory=lambda: defaultdict(int))
    purpose_stats: dict = field(default_factory=lambda: defaultdict(int))
    risk_stats: dict = field(default_factory=lambda: defaultdict(int))
    content_stats: dict = field(default_factory=lambda: defaultdict(int))
    high_value_files: list = field(default_factory=list)
    risky_files: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)


def _assess_value(fi, config=None) -> tuple:
    """评估文件价值，返回 (value, reasoning)"""
    name_lower = fi.name.lower()
    now = datetime.now()
    days_since_modified = (now - fi.modified).days
    days_since_created = (now - fi.created).days

    # ── 高价值：内容识别命中的重要文档 ──────────────────

    content_type = getattr(fi, "content_type", "")
    content_confidence = getattr(fi, "content_confidence", 0.0)

    if content_type in ("发票", "合同", "财务报表") and content_confidence >= 0.3:
        return "high", f"{content_type}（{content_confidence:.0%}）"

    if content_type == "简历" and content_confidence >= 0.3:
        return "high", f"简历（{content_confidence:.0%}）"

    if content_type == "论文" and content_confidence >= 0.3:
        return "high", f"论文（{content_confidence:.0%}）"

    # ── 高价值：近期活跃的工作文件 ──────────────────────

    # 近期修改的代码（7天内）
    if fi.category == "代码" and days_since_modified <= 7:
        return "high", "近期修改的代码文件"

    # 工作文档（文件名含工作关键词，且非垃圾文件）
    junk = config.classification.junk_keywords if config else [
        "copy", "副本", "backup", "bak", "old", "temp",
        "untitled", "新建", "未命名", "test", "debug",
    ]
    is_junk = any(kw in name_lower for kw in junk)

    if fi.category in ("文档", "PDF") and fi.size > 10 * 1024:
        if not is_junk and days_since_modified <= 180:
            return "high", "近期的工作文档"

    # 课程资料
    if content_type == "课程资料" and content_confidence >= 0.2:
        return "high", f"课程资料（{content_confidence:.0%}）"

    # ── 中价值：一般文件 ────────────────────────────────

    # 较旧的代码
    if fi.category == "代码":
        return "medium", "代码文件"

    # 文档/PDF（非垃圾）
    if fi.category in ("文档", "PDF") and fi.size > 10 * 1024:
        if is_junk:
            return "medium", "文档但文件名含垃圾关键词"
        return "medium", "文档文件"

    # 大尺寸媒体（>5MB）
    if fi.category in ("图片", "视频") and fi.size > 5 * 1024 * 1024:
        return "medium", "大尺寸媒体文件"

    # 普通图片/视频
    if fi.category in ("图片", "视频"):
        return "medium", "媒体文件"

    # 音乐
    if fi.category == "音乐":
        return "medium", "音乐文件"

    # 近期的压缩包（<30天，可能是工作文件）
    if fi.category == "压缩包" and days_since_modified <= 30:
        return "medium", "近期的压缩包"

    # ── 低价值：可清理的文件 ────────────────────────────

    # 临时文件
    if fi.category == "临时文件":
        return "low", "临时文件"

    # 重复文件
    if fi.is_duplicate:
        return "low", "重复文件"

    # 重复截图
    if content_type == "截图" or fi.category == "截图":
        if days_since_created > 7:
            return "low", "旧截图"

    # 过期安装包（>30天）
    if fi.category == "安装包" and days_since_modified > 30:
        return "low", "过期安装包"

    # 过期压缩包（>180天）
    if fi.category == "压缩包" and days_since_modified > 180:
        return "low", "过期压缩包"

    # 未知类型且极小
    if fi.category == "未知文件" and fi.size < 1024:
        return "low", "未知类型且极小的文件"

    # 安装包（未过期）
    if fi.category == "安装包":
        return "low", "安装包"

    # 垃圾关键词文件
    if is_junk:
        return "low", "文件名含垃圾关键词"

    return "medium", "一般文件"


def _infer_purpose(fi) -> tuple:
    """推断文件用途，返回 (purpose, confidence)"""
    name_lower = fi.name.lower()
    parent_lower = fi.path.parent.name.lower() if fi.path.parent else ""

    # 关键词匹配
    if any(kw in name_lower for kw in WORK_KEYWORDS):
        return "work", 0.9
    if any(kw in name_lower for kw in STUDY_KEYWORDS):
        return "study", 0.85
    if any(kw in name_lower for kw in PERSONAL_KEYWORDS):
        return "personal", 0.8

    # 临时文件
    if fi.category == "临时文件" or any(kw in name_lower for kw in TEMP_KEYWORDS):
        return "temp", 0.9

    # 过期安装包视为临时
    if fi.category == "安装包" and (datetime.now() - fi.modified).days > 30:
        return "temp", 0.7

    # 父目录线索
    if any(kw in parent_lower for kw in ("work", "工作", "项目", "project")):
        return "work", 0.6
    if any(kw in parent_lower for kw in ("学习", "课", "study", "course")):
        return "study", 0.6

    return "unknown", 0.3


def _assess_risk(fi, config=None) -> tuple:
    """评估操作风险，返回 (risk, reasoning)"""
    days = config.thresholds.old_file_days if config else 180

    # 临时文件：安全
    if fi.category == "临时文件":
        return "safe", "临时文件，可安全移动"

    # 重复文件：安全
    if fi.is_duplicate:
        return "safe", "重复文件，可安全归档"

    # 过期安装包/压缩包：安全
    if fi.category in ("安装包", "压缩包") and (datetime.now() - fi.modified).days > days:
        return "safe", "过期的安装包/压缩包"

    # 大文档：谨慎
    if fi.category in ("文档", "PDF") and fi.size > 1024 * 1024:
        return "caution", "较大的文档文件，建议确认后再操作"

    # 近期代码：高风险
    if fi.category == "代码" and (datetime.now() - fi.modified).days < 7:
        return "risky", "最近 7 天内修改的代码，可能是活跃项目"

    # 文件在根目录（不在子目录中）：谨慎
    if fi.path.parent == fi.path.parent.parent:
        pass  # 不额外标记，依赖其他规则

    return "safe", ""


def _determine_action(analysis: FileAnalysis) -> str:
    """根据价值和风险推荐操作"""
    if analysis.value == "low" and analysis.risk == "safe":
        return "review"
    if analysis.risk == "risky":
        return "review"
    if analysis.value == "high":
        return "keep"
    if analysis.purpose == "temp":
        return "review"
    return "archive"


def analyze_file(fi, config=None) -> FileAnalysis:
    """分析单个文件（含内容识别）"""
    value, value_reason = _assess_value(fi, config)
    purpose, confidence = _infer_purpose(fi)
    risk, risk_reason = _assess_risk(fi, config)

    reasoning_parts = []
    if value_reason:
        reasoning_parts.append(f"价值: {value_reason}")
    if risk_reason:
        reasoning_parts.append(f"风险: {risk_reason}")

    # 内容识别（仅对文档/图片/PDF 类型）
    content_type = ""
    content_confidence = 0.0
    if fi.category in ("文档", "PDF", "图片"):
        try:
            from .content_analyzer import analyze_content
            matches = analyze_content(fi.path, fi.name)
            if matches:
                content_type = matches[0].doc_type
                content_confidence = matches[0].confidence
                reasoning_parts.append(f"内容: {content_type} ({content_confidence:.0%})")
        except Exception:
            pass

    analysis = FileAnalysis(
        value=value,
        purpose=purpose,
        risk=risk,
        confidence=confidence,
        reasoning=" | ".join(reasoning_parts),
        content_type=content_type,
        content_confidence=content_confidence,
    )
    analysis.recommended_action = _determine_action(analysis)
    return analysis


def analyze_directory(scan_result, config=None) -> AnalysisResult:
    """批量分析目录中所有文件"""
    result = AnalysisResult()

    for fi in scan_result.files:
        analysis = analyze_file(fi, config)
        result.file_analyses[fi.path] = analysis

        # 写回 FileInfo
        fi.value = analysis.value
        fi.purpose = analysis.purpose
        fi.risk = analysis.risk
        fi.analysis_reasoning = analysis.reasoning
        fi.content_type = analysis.content_type
        fi.content_confidence = analysis.content_confidence

        # 统计
        result.value_stats[analysis.value] += 1
        result.purpose_stats[analysis.purpose] += 1
        result.risk_stats[analysis.risk] += 1

        if analysis.content_type:
            result.content_stats[analysis.content_type] += 1

        if analysis.value == "high":
            result.high_value_files.append((fi, analysis))
        if analysis.risk in ("caution", "risky"):
            result.risky_files.append((fi, analysis))

    result.recommendations = _generate_recommendations(result)
    return result


def _generate_recommendations(result: AnalysisResult) -> list:
    """生成顶层策略建议"""
    recs = []
    total = sum(result.value_stats.values()) or 1

    high_pct = result.value_stats.get("high", 0) / total * 100
    low_pct = result.value_stats.get("low", 0) / total * 100
    risky_count = result.risk_stats.get("risky", 0)

    if high_pct > 30:
        recs.append(f"该目录包含 {high_pct:.0f}% 高价值文件，整理时请仔细确认")
    if low_pct > 40:
        recs.append(f"约 {low_pct:.0f}% 为低价值/临时文件，建议优先清理")
    if risky_count > 0:
        recs.append(f"有 {risky_count} 个近期活跃文件，操作前请确认")
    if result.purpose_stats.get("temp", 0) > 5:
        recs.append("检测到较多临时文件，建议使用 dry-run 先预览")

    if not recs:
        recs.append("目录状况良好，可安全执行整理")

    return recs
