#!/usr/bin/env python3
"""
Generate Hubba Hubba stage cards as PDFs from a list of names.

Reads names from names.txt (or from a provided list), splits on connector
words ("and", "&", etc.) for multi-line layout, and writes one PDF per name
with text sized to fit 11x17 landscape pages.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Literal, TypedDict

from fpdf import FPDF


# --- Conversion constants ---
IN_TO_MM = 25.4
# 1 pt = 1/72 inch; common in typography for font sizes.
PT_TO_MM = 0.352778

# --- Page and layout config ---
# 11x17 paper, landscape
PAGE_HEIGHT_MM = 11 * IN_TO_MM
PAGE_WIDTH_MM = 17 * IN_TO_MM

LEADING_MM = 5  # Extra spacing between lines
DEBUG = False  # Set True to draw margin/label lines and bounding boxes

# Font size search
FONT_STEP = 2
FONT_MIN = 100
FONT_MAX = 800

# Connector words: each gets its own line in a smaller font
CONNECTOR_WORDS: frozenset[str] = frozenset({
    "and", "&", "with", "featuring", "presents",
})
CONNECTOR_FONT_RATIO = 0.55  # Connector line font = main * this
CONNECTOR_FONT_MIN_PT = 24   # Minimum connector font size (pt)


class Segment(TypedDict):
    """One segment of parsed name text: either a main block or a connector."""

    type: Literal["main", "connector"]
    text: str


def _default_output_dir() -> str:
    """Return default output directory name (date-based)."""
    return datetime.now().strftime("%Y_%m_%d")


def parse_into_segments(text: str) -> list[Segment]:
    """
    Split name text into main blocks and connector tokens.

    Connector words (e.g. "and", "&") are split onto their own segments so
    they can be rendered on a separate line in a smaller font.

    Args:
        text: Full name or act title, e.g. "Charlie quinn and friends".

    Returns:
        List of segments in order. Each segment has "type" ("main" or
        "connector") and "text". Example: "Charlie quinn and friends"
        -> [main "Charlie quinn", connector "and", main "friends"].

    Examples:
        >>> parse_into_segments("Solo Act")
        [{'type': 'main', 'text': 'Solo Act'}]
        >>> parse_into_segments("A & B")
        [{'type': 'main', 'text': 'A'}, {'type': 'connector', 'text': '&'}, ...
    """
    words = text.split()
    if not words:
        return []

    segments: list[Segment] = []
    current: list[str] = []

    for word in words:
        if word == "&" or word.lower() in CONNECTOR_WORDS:
            if current:
                segments.append({"type": "main", "text": " ".join(current)})
                current = []
            segments.append({"type": "connector", "text": word})
        else:
            current.append(word)

    if current:
        segments.append({"type": "main", "text": " ".join(current)})

    return segments


class StageCardPDF(FPDF):
    """
    PDF generator for Hubba Hubba stage cards (11x17 landscape, one name per page).

    Uses a greedy segment-based layout: main text is maximized to fit width;
    connector words are rendered on their own line in a smaller font.
    """

    FONT_FAMILY = "diner"

    def _get_font_height_mm(self, font_size_pt: float, sample_text: str) -> float:
        """
        Compute height (mm) of a line of text at the given font size.

        Uses a temporary PDF instance to measure MultiCell output.
        """
        temp = StageCardPDF(
            orientation="L", unit="mm", format=(PAGE_HEIGHT_MM, PAGE_WIDTH_MM)
        )
        temp.add_font(
            family=self.FONT_FAMILY,
            style="",
            fname="./Fontdinerdotcom-unlocked.ttf",
            uni=True,
        )
        temp.add_page()
        temp.set_xy(0, 0)
        temp.set_font(self.FONT_FAMILY, "", font_size_pt)
        temp.multi_cell(
            w=self.w - 1.0,
            h=(font_size_pt * PT_TO_MM) + LEADING_MM,
            align="C",
            txt=sample_text,
            border=1,
        )
        return float(temp.get_y())

    def _get_multi_cell_height(
        self,
        width_mm: float,
        line_height_mm: float,
        txt: str,
        border: int = 0,
        align: str = "J",
    ) -> float:
        """
        Compute total height (mm) of MultiCell with automatic line breaks.

        Mirrors FPDF's MultiCell logic for height calculation. The `border`
        parameter is kept for API consistency with MultiCell but not used.
        """
        # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        # Mirrors FPDF internals; self.ws is from parent FPDF.
        border = max(0, border)
        char_widths = self.current_font["cw"]
        if width_mm == 0:
            width_mm = self.w - self.r_margin - self.x

        width_max_units = (width_mm - 2 * self.c_margin) * 1000 / self.font_size
        string = txt.replace("\r", "")
        length = len(string)
        if length > 0 and string[length - 1] == "\n":
            length -= 1

        sep = -1
        i = 0
        j = 0
        line_len = 0
        num_spaces = 0
        height = 0.0

        while i < length:
            char = string[i]

            if char == "\n":
                if self.ws > 0:
                    self.ws = 0
                    self._out("0 Tw")
                height += line_height_mm
                i += 1
                sep = -1
                j = i
                line_len = 0
                num_spaces = 0
                continue

            if char == " ":
                sep = i
                last_line_len = line_len
                num_spaces += 1

            line_len += char_widths[ord(char)]

            if line_len > width_max_units:
                if sep == -1:
                    if i == j:
                        i += 1
                    if self.ws > 0:
                        self.ws = 0
                        self._out("0 Tw")
                    height += line_height_mm
                else:
                    if align == "J":
                        if num_spaces > 1:
                            self.ws = (
                                (width_max_units - last_line_len)
                                / 1000
                                * self.font_size
                                / (num_spaces - 1)
                            )
                        else:
                            self.ws = 0
                        self._out(f"{self.ws * self.k:.3F} Tw")
                    height += line_height_mm
                    i = sep + 1
                sep = -1
                j = i
                line_len = 0
                num_spaces = 0
            else:
                i += 1

        if self.ws > 0:
            self.ws = 0
            self._out("0 Tw")
        height += line_height_mm
        return height

    def _get_longest_word(self, text: str) -> str:
        """Return the longest word in the given text."""
        words = text.split()
        return max(words, key=len)

    def _get_max_font_for_width(self, text: str, max_width_mm: float) -> int:
        """
        Largest font size (pt) for which the text fits within max_width_mm.
        """
        font_size = FONT_MIN
        while font_size <= FONT_MAX:
            self.set_font(self.FONT_FAMILY, "", font_size)
            if self.get_string_width(text) > max_width_mm:
                font_size -= FONT_STEP
                break
            font_size += FONT_STEP
        font_size = max(FONT_MIN, min(FONT_MAX, font_size))
        self.set_font(self.FONT_FAMILY, "", font_size)
        return font_size

    def get_segment_layout(  # pylint: disable=too-many-locals
        self, text: str
    ) -> tuple[list[tuple[str, int]], float]:
        """
        Compute greedy segment-based layout: one (text, font_size_pt) per line.

        Main segments are sized to fit the page width; connector segments use
        a smaller font. If total height exceeds the page, all main sizes are
        scaled down.

        Args:
            text: Full name or act title.

        Returns:
            (lines, total_height_mm): list of (line_text, font_size_pt) and
            total height in mm.
        """
        segments = parse_into_segments(text)
        available_width = self.w - self.l_margin - self.r_margin
        available_height = self.h - 2 * self.t_margin

        if not segments:
            return [], 0.0

        if len(segments) == 1 and segments[0]["type"] == "main":
            text_only = segments[0]["text"]
            font_size = self._get_max_font_for_width(text_only, available_width)
            line_height_mm = font_size * PT_TO_MM + LEADING_MM
            if line_height_mm > available_height:
                scale = available_height / line_height_mm
                font_size = max(FONT_MIN, int(font_size * scale))
                line_height_mm = font_size * PT_TO_MM + LEADING_MM
            return [(text_only, font_size)], line_height_mm

        # Multiple segments: main font = min of max-fit per main segment
        main_font = FONT_MAX
        for seg in segments:
            if seg["type"] == "main":
                self.set_font(self.FONT_FAMILY, "", main_font)
                fit = self._get_max_font_for_width(seg["text"], available_width)
                main_font = min(main_font, fit)

        connector_font = max(
            CONNECTOR_FONT_MIN_PT,
            int(main_font * CONNECTOR_FONT_RATIO),
        )

        lines: list[tuple[str, int]] = []
        total_height = 0.0
        for seg in segments:
            font_pt = main_font if seg["type"] == "main" else connector_font
            lines.append((seg["text"], font_pt))
            total_height += font_pt * PT_TO_MM + LEADING_MM

        if total_height > available_height:
            scale = available_height / total_height
            main_font = max(FONT_MIN, int(main_font * scale))
            connector_font = max(
                CONNECTOR_FONT_MIN_PT,
                int(main_font * CONNECTOR_FONT_RATIO),
            )
            total_height = 0.0
            lines = []
            for seg in segments:
                font_pt = main_font if seg["type"] == "main" else connector_font
                lines.append((seg["text"], font_pt))
                total_height += font_pt * PT_TO_MM + LEADING_MM

        return lines, total_height

    def _draw_debug_line(  # pylint: disable=too-many-arguments
        self,
        y_mm: float,
        red: int,
        green: int,
        blue: int,
        label: str,
    ) -> None:
        """Draw a horizontal dashed line with a small label (DEBUG only)."""
        font_pt = 30
        self.set_xy(0, y_mm - (font_pt * PT_TO_MM))
        self.set_line_width(0.2)
        self.set_draw_color(red, green, blue)
        self.set_text_color(red, green, blue)
        self.set_font(self.FONT_FAMILY, "", font_pt)
        self.cell(
            self.w,
            h=font_pt * PT_TO_MM,
            align="L",
            txt=label,
            border=0,
            ln=0,
        )
        self.dashed_line(0, y_mm, self.w, y_mm, 3, 2)

    def add_name(self, text: str) -> None:
        """
        Add the name/act title to the page using the greedy segment layout.

        Text is centered vertically and horizontally; connector words appear
        on their own line in a smaller font.
        """
        self.set_xy(0.0, 0.0)
        self.set_font(self.FONT_FAMILY, "", 100)
        self.set_text_color(0, 0, 0)

        lines, total_height = self.get_segment_layout(text)

        if DEBUG:
            self._draw_debug_line(self.t_margin, 255, 0, 0, "MARGIN")

        y_offset = self.t_margin + (
            (self.h - 2 * self.t_margin) - total_height
        ) / 2

        if DEBUG:
            print(f"   segments: {len(lines)}")
            print(f"   total_height: {total_height:.2f} mm")
            print(f"   y_offset: {y_offset:.2f}")
            self._draw_debug_line(y_offset, 0, 255, 0, "YOFFSET")

        self.set_xy(0, y_offset)
        self.set_fill_color(0, 0, 0)
        self.set_text_color(0, 0, 0)

        for line_text, font_pt in lines:
            line_height_mm = font_pt * PT_TO_MM + LEADING_MM
            self.set_font(self.FONT_FAMILY, "", font_pt)
            border = 1 if DEBUG else 0
            if DEBUG:
                self.set_draw_color(255, 0, 255)
            self.multi_cell(
                w=self.w,
                h=line_height_mm,
                align="C",
                txt=line_text,
                border=border,
            )


def make_sign(
    name_line: str,
    output_dir: str | Path | None = None,
) -> Path:
    """
    Generate a single stage card PDF for the given name.

    Args:
        name_line: Name or act title (leading/trailing whitespace is stripped).
        output_dir: Directory for the output PDF. Defaults to date-based dir.

    Returns:
        Path to the written PDF file.

    Raises:
        FileNotFoundError: If the font file is missing.
    """
    if output_dir is None:
        output_dir = _default_output_dir()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    pdf = StageCardPDF(
        orientation="L",
        unit="mm",
        format=(PAGE_HEIGHT_MM, PAGE_WIDTH_MM),
    )
    pdf.set_auto_page_break(False)
    pdf.add_font(
        family=StageCardPDF.FONT_FAMILY,
        style="",
        fname="./Fontdinerdotcom-unlocked.ttf",
        uni=True,
    )
    pdf.add_page()

    if DEBUG:
        print(f"\npage WIDTH: {pdf.w:.2f} mm  height: {pdf.h:.2f} mm")
        print(
            f"margin L: {pdf.l_margin:.2f} R: {pdf.r_margin:.2f} "
            f"T: {pdf.t_margin:.2f} B: {pdf.b_margin:.2f}"
        )
        pdf.set_draw_color(255, 255, 0)
        pdf.rect(0, 0, pdf.w, pdf.h, "D")
        pdf.set_draw_color(255, 0, 0)
        pdf.rect(
            pdf.l_margin,
            pdf.t_margin,
            pdf.w - pdf.r_margin - pdf.l_margin,
            pdf.h - pdf.t_margin - pdf.t_margin,
            "D",
        )

    name = name_line.strip()
    print(f"\n{name}\n")

    pdf.add_name(name)
    out_file = output_path / f"{name.replace(' ', '_')}.pdf"
    pdf.output(str(out_file), "F")
    return out_file


def make_from_file(
    names_file: str | Path = "names.txt",
    output_dir: str | Path | None = None,
) -> None:
    """
    Generate stage card PDFs for each non-blank line in a text file.

    Args:
        names_file: Path to a file with one name per line.
        output_dir: Directory for output PDFs. Defaults to date-based dir.
    """
    if output_dir is None:
        output_dir = _default_output_dir()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    with open(names_file, "r", encoding="utf-8") as names_stream:
        for line in names_stream:
            if len(line.strip()) < 2:
                print("Skipping blank line.")
                continue
            print(f"make {line.strip()}")
            make_sign(line, output_dir=output_path)


def make_signs_from_lines(
    lines: list[str],
    output_dir: str | Path,
    *,
    base_name: str | None = None,
) -> Path | None:
    """
    Generate stage card PDFs for each non-blank line and optionally zip them.

    Args:
        lines: List of name/act title strings.
        output_dir: Directory for output PDFs.
        base_name: If set, create a zip archive of output_dir with this base name.

    Returns:
        Path to the zip file if base_name was set, else None.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    for line in lines:
        if len(line.strip()) < 2:
            print("Skipping blank line.")
            continue
        make_sign(line, output_dir=output_path)

    if base_name:
        return Path(
            shutil.make_archive(
                base_name=base_name,
                format="zip",
                root_dir=output_path,
            )
        )
    return None


if __name__ == "__main__":
    make_from_file()
