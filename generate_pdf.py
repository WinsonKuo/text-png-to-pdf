#!/usr/bin/env python3
"""Combine plain text/markdown files and PNG images into a PDF."""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path
from typing import Iterable, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    ListFlowable,
    ListItem,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
)

IMAGE_TAG_PATTERN = re.compile(r"<([^<>]+\.png)>", re.IGNORECASE)
IMAGE_MARKER_PATTERN = re.compile(r"^\[\[IMAGE:([^\]]+)\]\]$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge text (plain text/markdown) and PNG images into a single PDF."
    )
    parser.add_argument(
        "--texts",
        nargs="+",
        required=True,
        help="One or more text files (.txt / .md / .markdown).",
    )
    parser.add_argument(
        "--images",
        nargs="*",
        default=[],
        help="Zero or more PNG files.",
    )
    parser.add_argument("--output", required=True, help="Output PDF path.")
    return parser.parse_args()


def normalise_image_map(image_paths: Iterable[str]) -> dict[str, Path]:
    image_map: dict[str, Path] = {}
    for image_path in image_paths:
        p = Path(image_path)
        if not p.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        if p.suffix.lower() != ".png":
            raise ValueError(f"Only PNG images are supported: {image_path}")
        image_map[p.name] = p
    return image_map


def replace_image_tags(content: str, seen_refs: set[str]) -> str:
    def _repl(match: re.Match[str]) -> str:
        image_name = match.group(1)
        seen_refs.add(image_name)
        return f"\n[[IMAGE:{image_name}]]\n"

    return IMAGE_TAG_PATTERN.sub(_repl, content)


def scale_image(path: Path, max_width: float, max_height: float) -> Image:
    img = Image(str(path))
    ratio = min(max_width / img.imageWidth, max_height / img.imageHeight, 1.0)
    img.drawWidth = img.imageWidth * ratio
    img.drawHeight = img.imageHeight * ratio
    img.hAlign = "LEFT"
    return img


def inline_markdown_to_rl_markup(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r'<font face="Courier">\1</font>', escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", escaped)
    escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', escaped)
    return escaped


def build_markdown_flowables(
    text: str,
    styles,
    image_map: dict[str, Path],
    appended_images: set[str],
) -> List:
    flowables: List = []
    lines = text.splitlines()

    bullet_items: List[str] = []
    ordered_items: List[str] = []
    paragraph_lines: List[str] = []

    def flush_paragraph() -> None:
        if paragraph_lines:
            para = " ".join(line.strip() for line in paragraph_lines if line.strip())
            if para:
                flowables.append(Paragraph(inline_markdown_to_rl_markup(para), styles["BodyText"]))
                flowables.append(Spacer(1, 0.2 * cm))
            paragraph_lines.clear()

    def flush_lists() -> None:
        nonlocal bullet_items, ordered_items
        if bullet_items:
            items = [
                ListItem(Paragraph(inline_markdown_to_rl_markup(item), styles["BodyText"]))
                for item in bullet_items
            ]
            flowables.append(ListFlowable(items, bulletType="bullet", bulletColor=colors.black))
            flowables.append(Spacer(1, 0.2 * cm))
            bullet_items = []

        if ordered_items:
            items = [
                ListItem(Paragraph(inline_markdown_to_rl_markup(item), styles["BodyText"]))
                for item in ordered_items
            ]
            flowables.append(ListFlowable(items, bulletType="1", bulletColor=colors.black))
            flowables.append(Spacer(1, 0.2 * cm))
            ordered_items = []

    for raw_line in lines:
        line = raw_line.rstrip()
        marker_match = IMAGE_MARKER_PATTERN.match(line.strip())
        if marker_match:
            flush_paragraph()
            flush_lists()
            image_name = marker_match.group(1)
            if image_name in image_map:
                flowables.append(scale_image(image_map[image_name], max_width=16 * cm, max_height=21 * cm))
                flowables.append(Spacer(1, 0.3 * cm))
                appended_images.add(image_name)
            else:
                flowables.append(
                    Paragraph(f"[Missing image: {html.escape(image_name)}]", styles["Code"])
                )
                flowables.append(Spacer(1, 0.2 * cm))
            continue

        if not line.strip():
            flush_paragraph()
            flush_lists()
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            flush_paragraph()
            flush_lists()
            level = len(heading_match.group(1))
            content = inline_markdown_to_rl_markup(heading_match.group(2).strip())
            heading_style = ParagraphStyle(
                name=f"H{level}",
                parent=styles["Heading1"],
                fontSize=max(22 - (level * 2), 11),
                leading=max(26 - (level * 2), 13),
                spaceAfter=6,
            )
            flowables.append(Paragraph(content, heading_style))
            continue

        bullet_match = re.match(r"^[-*]\s+(.+)$", line)
        if bullet_match:
            flush_paragraph()
            bullet_items.append(bullet_match.group(1))
            continue

        ordered_match = re.match(r"^\d+\.\s+(.+)$", line)
        if ordered_match:
            flush_paragraph()
            ordered_items.append(ordered_match.group(1))
            continue

        flush_lists()
        paragraph_lines.append(line)

    flush_paragraph()
    flush_lists()
    return flowables


def build_plain_text_flowables(
    text: str,
    styles,
    image_map: dict[str, Path],
    appended_images: set[str],
) -> List:
    flowables: List = []
    for line in text.splitlines():
        stripped = line.strip()
        marker_match = IMAGE_MARKER_PATTERN.match(stripped)
        if marker_match:
            image_name = marker_match.group(1)
            if image_name in image_map:
                flowables.append(scale_image(image_map[image_name], max_width=16 * cm, max_height=21 * cm))
                flowables.append(Spacer(1, 0.3 * cm))
                appended_images.add(image_name)
            else:
                flowables.append(Paragraph(f"[Missing image: {html.escape(image_name)}]", styles["Code"]))
                flowables.append(Spacer(1, 0.2 * cm))
        else:
            flowables.append(Preformatted(line, styles["Code"]))
    flowables.append(Spacer(1, 0.3 * cm))
    return flowables


def main() -> None:
    args = parse_args()

    text_paths = [Path(p) for p in args.texts]
    for text_path in text_paths:
        if not text_path.exists():
            raise FileNotFoundError(f"Text file not found: {text_path}")

    image_map = normalise_image_map(args.images)

    styles = getSampleStyleSheet()
    body_left = ParagraphStyle(name="BodyLeft", parent=styles["BodyText"], alignment=0)
    styles.add(body_left)

    doc = SimpleDocTemplate(
        args.output,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    story: List = []
    seen_refs: set[str] = set()
    appended_images: set[str] = set()

    for idx, text_path in enumerate(text_paths):
        content = text_path.read_text(encoding="utf-8")
        content = replace_image_tags(content, seen_refs)

        if text_path.suffix.lower() in {".md", ".markdown"}:
            story.extend(build_markdown_flowables(content, styles, image_map, appended_images))
        else:
            story.extend(build_plain_text_flowables(content, styles, image_map, appended_images))

        if idx < len(text_paths) - 1:
            story.append(Spacer(1, 0.8 * cm))

    # If no image tag is used in any text, put all images at the end.
    if not seen_refs:
        for image_name, image_path in image_map.items():
            story.append(scale_image(image_path, max_width=16 * cm, max_height=21 * cm))
            story.append(Spacer(1, 0.3 * cm))
            appended_images.add(image_name)
    else:
        # Also append any provided but unreferenced image to avoid dropping inputs.
        for image_name, image_path in image_map.items():
            if image_name not in appended_images:
                story.append(scale_image(image_path, max_width=16 * cm, max_height=21 * cm))
                story.append(Spacer(1, 0.3 * cm))

    if not story:
        story.append(Paragraph("(No content)", styles["BodyText"]))

    doc.build(story)


if __name__ == "__main__":
    main()
