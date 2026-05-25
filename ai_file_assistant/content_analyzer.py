"""AI 内容识别模块 — 识别发票、合同、简历、截图、课程资料等"""

import re
from pathlib import Path
from dataclasses import dataclass

try:
    import pdfplumber
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

try:
    from PIL import Image
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif"}
PDF_EXTENSIONS = {".pdf"}
DOC_EXTENSIONS = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".pages", ".numbers", ".key"}
TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".xml", ".yaml", ".yml"}


# ── 文档类型定义 ──────────────────────────────────────────

@dataclass
class ContentMatch:
    doc_type: str
    confidence: float
    evidence: list


# ── 关键词模式 ────────────────────────────────────────────

PATTERNS = {
    "发票": {
        "keywords": [
            "发票", "invoice", "增值税", "普通发票", "专用发票",
            "发票代码", "发票号码", "开票日期", "价税合计",
            "销方", "购方", "纳税人识别号", "发票抬头",
            "金额", "税额", "合计", "¥", "￥",
        ],
        "patterns": [
            r"发票代码[：:]\s*\d{10,12}",
            r"发票号码[：:]\s*\d{8,10}",
            r"价税合计.*[¥￥]\s*[\d,]+\.?\d*",
            r"纳税人识别号[：:]\s*[A-Z0-9]{15,20}",
        ],
        "weight": 0,
    },
    "合同": {
        "keywords": [
            "合同", "contract", "协议", "甲方", "乙方",
            "签约", "签署", "条款", "违约", "仲裁",
            "合同期限", "合同编号", "生效日期", "终止日期",
            "权利义务", "保密条款", "不可抗力", "争议解决",
            "签字盖章", "法定代表人", "委托代理人",
        ],
        "patterns": [
            r"甲方[：:].{2,20}",
            r"乙方[：:].{2,20}",
            r"合同编号[：:]\s*[A-Z0-9\-]+",
            r"第[一二三四五六七八九十]+条",
        ],
        "weight": 0,
    },
    "简历": {
        "keywords": [
            "简历", "resume", "curriculum vitae", "cv",
            "求职", "应聘", "工作经历", "教育背景",
            "专业技能", "项目经验", "自我评价",
            "联系方式", "手机号", "邮箱", "学历",
            "毕业院校", "专业", "gpa", "期望薪资",
        ],
        "patterns": [
            r"1[3-9]\d{9}",  # 手机号
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",  # 邮箱
            r"(本科|硕士|博士|研究生|大专|MBA|EMBA)",
            r"(20\d{2})\s*[-–]\s*(20\d{2}|至今)",
        ],
        "weight": 0,
    },
    "截图": {
        "keywords": [
            "screenshot", "截图", "截屏", "屏幕截图",
            "capture", "snip", "snipaste", "cleanshot",
        ],
        "patterns": [
            r"Screenshot[_\s]?\d{4}[-_]?\d{2}[-_]?\d{2}",
            r"屏幕截图\s?\d{4}",
            r"IMG_\d{4,}",
        ],
        "weight": 0,
        "is_filename_only": True,
    },
    "课程资料": {
        "keywords": [
            "课程", "课件", "讲义", "教案", "教材",
            "lecture", "course", "syllabus", "教材",
            "习题", "作业", "考试", "复习", "笔记",
            "第[一二三四五六七八九十百]+[章节讲]",
            "知识点", "重点", "难点", "考点",
            "课程名称", "授课教师", "学分", "学时",
        ],
        "patterns": [
            r"第\s*[一二三四五六七八九十\d]+\s*[章节讲]",
            r"(课程|教学|学习)\s*(目标|要求|大纲|计划)",
            r"(期中|期末|随堂|模拟)\s*(考试|测试|测验)",
        ],
        "weight": 0,
    },
    "财务报表": {
        "keywords": [
            "资产负债表", "利润表", "现金流量表",
            "balance sheet", "income statement",
            "营业收入", "净利润", "总资产", "负债合计",
            "所有者权益", "应收账款", "应付账款",
            "财务报表", "年度报告", "季度报告",
        ],
        "patterns": [
            r"(资产|负债|权益|收入|费用|利润)\s*合计",
            r"编制单位[：:].{2,20}",
            r"报表日期[：:]\s*\d{4}",
        ],
        "weight": 0,
    },
    "论文": {
        "keywords": [
            "论文", "thesis", "paper", "abstract", "摘要",
            "关键词", "keywords", "参考文献", "references",
            "引言", "introduction", "结论", "conclusion",
            "文献综述", "literature review", "方法论",
            "实验结果", "数据分析", "讨论",
        ],
        "patterns": [
            r"(摘\s*要|abstract)[：:\s].{20,}",
            r"(关键词|keywords)[：:\s].{5,}",
            r"\[\d+\].*",  # 参考文献格式
        ],
        "weight": 0,
    },
}


def _extract_pdf_text(filepath: Path, max_pages: int = 3) -> str:
    """从 PDF 提取文本（前 N 页）"""
    if not HAS_PDF:
        return ""
    try:
        text_parts = []
        with pdfplumber.open(filepath) as pdf:
            for i, page in enumerate(pdf.pages[:max_pages]):
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        return "\n".join(text_parts)
    except Exception:
        return ""


def _extract_image_text(filepath: Path, lang: str = "chi_sim+eng") -> str:
    """从图片 OCR 提取文本"""
    if not HAS_OCR:
        return ""
    try:
        img = Image.open(filepath)
        text = pytesseract.image_to_string(img, lang=lang)
        return text
    except Exception:
        return ""


def _match_patterns(text: str, doc_type: str, patterns: dict) -> ContentMatch:
    """对文本进行关键词和正则匹配"""
    if not text and not patterns.get("is_filename_only"):
        return None

    evidence = []
    score = 0

    # 关键词匹配
    keywords = patterns.get("keywords", [])
    for kw in keywords:
        if re.search(kw, text, re.IGNORECASE):
            evidence.append(f"关键词: {kw}")
            score += 1

    # 正则匹配
    regexes = patterns.get("patterns", [])
    for pattern in regexes:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            evidence.append(f"模式: {match.group()[:50]}")
            score += 2

    if score == 0:
        return None

    # 置信度计算
    max_possible = len(keywords) + len(regexes) * 2
    confidence = min(score / max(max_possible * 0.3, 1), 1.0)

    return ContentMatch(
        doc_type=doc_type,
        confidence=round(confidence, 2),
        evidence=evidence[:5],
    )


def analyze_content(filepath: Path, filename: str = None) -> list:
    """分析文件内容，返回匹配的文档类型列表

    Args:
        filepath: 文件路径
        filename: 文件名（可选，用于文件名模式匹配）

    Returns:
        list[ContentMatch] 按置信度降序排列
    """
    if filename is None:
        filename = filepath.name

    ext = filepath.suffix.lower()
    matches = []

    # 文件名匹配（截图等）
    for doc_type, patterns in PATTERNS.items():
        if patterns.get("is_filename_only"):
            match = _match_patterns(filename, doc_type, patterns)
            if match:
                matches.append(match)

    # PDF 内容分析
    if ext in PDF_EXTENSIONS:
        text = _extract_pdf_text(filepath)
        if text:
            for doc_type, patterns in PATTERNS.items():
                if patterns.get("is_filename_only"):
                    continue
                match = _match_patterns(text, doc_type, patterns)
                if match:
                    matches.append(match)

    # 图片 OCR 分析
    elif ext in IMAGE_EXTENSIONS:
        text = _extract_image_text(filepath)
        if text:
            for doc_type, patterns in PATTERNS.items():
                if patterns.get("is_filename_only"):
                    continue
                match = _match_patterns(text, doc_type, patterns)
                if match:
                    matches.append(match)

    # 文本文件分析
    elif ext in TEXT_EXTENSIONS:
        try:
            text = filepath.read_text(encoding="utf-8", errors="ignore")[:5000]
            for doc_type, patterns in PATTERNS.items():
                if patterns.get("is_filename_only"):
                    continue
                match = _match_patterns(text, doc_type, patterns)
                if match:
                    matches.append(match)
        except Exception:
            pass

    # 按置信度降序排序
    matches.sort(key=lambda m: m.confidence, reverse=True)
    return matches


def classify_by_content(filepath: Path, filename: str = None) -> str:
    """返回最高置信度的文档类型，无匹配返回空字符串"""
    matches = analyze_content(filepath, filename)
    if matches and matches[0].confidence >= 0.3:
        return matches[0].doc_type
    return ""


def batch_analyze(files: list) -> dict:
    """批量分析文件内容

    Args:
        files: FileInfo 列表

    Returns:
        {
            "results": {filepath: [ContentMatch, ...]},
            "stats": {doc_type: count},
            "total_analyzed": int,
        }
    """
    results = {}
    stats = {}

    for fi in files:
        matches = analyze_content(fi.path, fi.name)
        if matches:
            results[str(fi.path)] = matches
            for m in matches:
                stats[m.doc_type] = stats.get(m.doc_type, 0) + 1

    return {
        "results": results,
        "stats": stats,
        "total_analyzed": len(results),
    }
