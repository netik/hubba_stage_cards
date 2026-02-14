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

# Spacing: extra mm between lines (intra-line spacing)
LEADING_MM = 5

# Multiplier on metric-based line height to avoid clipping (e.g. two-word names)
LINE_HEIGHT_SAFETY = 1.10
# Connector/lead-in lines use smaller safety so they take less vertical room → main text can be bigger
LINE_HEIGHT_SAFETY_CONNECTOR = 1.08

# Debug: print layout info (segments, heights, font metrics) to the console
DEBUG = True
# Debug: draw bounding boxes on the PDF (red margin, cyan text block, magenta per-line, yellow page)
DEBUG_BOUNDING = False

# Content area margins (mm); text is sized and drawn within this box
CONTENT_MARGIN_MM = 10
# Extra mm subtracted from content width when sizing and drawing (keeps text off edges)
WIDTH_SAFETY_MM = 12.0

# Vertical position: fraction of (available_height - total_height) above the block.
# For short blocks (1–2 lines) use smaller ratio so text starts higher.
VERTICAL_CENTER_RATIO = 0.5
VERTICAL_CENTER_RATIO_SHORT = 0.28  # when 1–2 lines

# Font units per em (PDF/TTF typically 1000). Used with Ascent/Descent for line height.
FONT_UNITS_PER_EM = 1000

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

# Long main text: max words per line (chunked); lead-in words get a smaller line
MAX_WORDS_PER_LINE = 3
LEAD_IN_WORDS: frozenset[str] = frozenset({"the", "a", "an"})


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


def expand_segments_to_lines(segments: list[Segment]) -> list[Segment]:
    """
    Expand long main segments into multiple lines (word limit + optional lead-in).

    - Main segments with more than MAX_WORDS_PER_LINE words are chunked into
      lines of at most that many words.
    - If a main segment starts with a lead-in word ("the", "a", "an") and has
      more than one word, that word is emitted as a connector-sized line, then
      the rest is chunked by MAX_WORDS_PER_LINE as above.

    Args:
        segments: Output of parse_into_segments.

    Returns:
        New list of segments (each main chunk is one segment; lead-in is one
        connector segment) for layout.
    """
    result: list[Segment] = []
    for seg in segments:
        if seg["type"] == "connector":
            result.append(seg)
            continue
        words = seg["text"].split()
        if not words:
            continue
        # Lead-in: "the infamously long..." -> "the" (small) + "infamously long named" / "luma jaguar"
        if words[0].lower() in LEAD_IN_WORDS and len(words) > 1:
            result.append({"type": "connector", "text": words[0]})
            rest_words = words[1:]
            for i in range(0, len(rest_words), MAX_WORDS_PER_LINE):
                chunk = rest_words[i : i + MAX_WORDS_PER_LINE]
                result.append({"type": "main", "text": " ".join(chunk)})
        elif len(words) > MAX_WORDS_PER_LINE:
            for i in range(0, len(words), MAX_WORDS_PER_LINE):
                chunk = words[i : i + MAX_WORDS_PER_LINE]
                result.append({"type": "main", "text": " ".join(chunk)})
        else:
            result.append(seg)
    return result


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
        Uses coarse step then binary search for exact maximum.
        """
        # Coarse step to find upper bound
        font_size = FONT_MIN
        while font_size <= FONT_MAX:
            self.set_font(self.FONT_FAMILY, "", font_size)
            if self.get_string_width(text) > max_width_mm:
                font_size -= FONT_STEP
                break
            font_size += FONT_STEP
        font_size = max(FONT_MIN, min(FONT_MAX, font_size))
        low, high = max(FONT_MIN, font_size - FONT_STEP), min(FONT_MAX, font_size + 1)
        # Binary search for exact max
        while low < high:
            mid = (low + high + 1) // 2
            self.set_font(self.FONT_FAMILY, "", mid)
            if self.get_string_width(text) <= max_width_mm:
                low = mid
            else:
                high = mid - 1
        font_size = low
        self.set_font(self.FONT_FAMILY, "", font_size)
        return font_size

    def _get_font_height_scale(self) -> tuple[float, dict]:
        """
        Height scale (font units per em) from current font. Prefers FontBBox over
        Ascent/Descent so glyphs that extend beyond the OS/2 metrics don't clip.
        Returns (scale, {"scale": float, "source": "FontBBox"|"AscentDescent", ...}).
        """
        desc = getattr(self, "current_font", None) and self.current_font.get("desc")
        if isinstance(desc, dict):
            # FontBBox is the actual glyph bounding box [llx, lly, urx, ury]
            bbox = desc.get("FontBBox")
            if bbox:
                if isinstance(bbox, str):
                    parts = bbox.replace("[", "").replace("]", "").split()
                    if len(parts) >= 4:
                        lly = float(parts[1])
                        ury = float(parts[3])
                        height_units = ury - lly
                        scale = height_units / FONT_UNITS_PER_EM
                        return scale, {
                            "scale": scale,
                            "source": "FontBBox",
                            "bbox_lly": lly,
                            "bbox_ury": ury,
                        }
                elif isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                    lly, ury = float(bbox[1]), float(bbox[3])
                    scale = (ury - lly) / FONT_UNITS_PER_EM
                    return scale, {"scale": scale, "source": "FontBBox"}
            ascent = desc.get("Ascent", 750)
            descent = desc.get("Descent", -250)
            font_height_units = ascent + abs(descent)
            scale = font_height_units / FONT_UNITS_PER_EM
            return scale, {
                "scale": scale,
                "source": "AscentDescent",
                "ascent": ascent,
                "descent": descent,
            }
        return 0.92, {"scale": 0.92, "source": "fallback"}

    def _get_line_height_mm(self, font_pt: float, *, is_connector: bool = False) -> float:
        """
        Line height in mm from the current font's metrics.

        Prefers FontBBox (actual glyph bounds) over Ascent/Descent. Connector
        lines use a smaller safety so they take less vertical room and main text
        can be larger.
        """
        self.set_font(self.FONT_FAMILY, "", font_pt)
        scale, _ = self._get_font_height_scale()
        safety = LINE_HEIGHT_SAFETY_CONNECTOR if is_connector else LINE_HEIGHT_SAFETY
        glyph_height_mm = font_pt * PT_TO_MM * scale * safety
        return glyph_height_mm + LEADING_MM

    def _get_line_height_and_metrics(
        self, font_pt: float, *, is_connector: bool = False
    ) -> tuple[float, dict]:
        """
        Same as _get_line_height_mm but also return metrics dict for debugging.
        """
        self.set_font(self.FONT_FAMILY, "", font_pt)
        scale, scale_info = self._get_font_height_scale()
        safety = LINE_HEIGHT_SAFETY_CONNECTOR if is_connector else LINE_HEIGHT_SAFETY
        glyph_height_mm = font_pt * PT_TO_MM * scale * safety
        line_height_mm = glyph_height_mm + LEADING_MM
        desc = getattr(self, "current_font", None) and self.current_font.get("desc")
        ascent = desc.get("Ascent", 750) if isinstance(desc, dict) else 750
        descent = desc.get("Descent", -250) if isinstance(desc, dict) else -250
        metrics = {
            "ascent": ascent,
            "descent": descent,
            "scale": scale,
            "source": scale_info.get("source", "?"),
            "glyph_height_mm": glyph_height_mm,
            "line_height_mm": line_height_mm,
        }
        return line_height_mm, metrics

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
        segments = expand_segments_to_lines(parse_into_segments(text))
        available_width = max(
            10.0,
            self.w - self.l_margin - self.r_margin - WIDTH_SAFETY_MM,
        )
        available_height = self.h - self.t_margin - self.b_margin

        if not segments:
            return [], 0.0

        if len(segments) == 1 and segments[0]["type"] == "main":
            text_only = segments[0]["text"]
            width_max = self._get_max_font_for_width(text_only, available_width)
            # Max font that fits height (exact from line-height formula)
            self.set_font(self.FONT_FAMILY, "", width_max)
            scale, _ = self._get_font_height_scale()
            height_max_pt = (available_height - LEADING_MM) / (
                PT_TO_MM * scale * LINE_HEIGHT_SAFETY
            )
            font_size = min(width_max, int(height_max_pt))
            font_size = max(FONT_MIN, min(FONT_MAX, font_size))
            while (
                self._get_line_height_mm(font_size, is_connector=False) > available_height
                and font_size > FONT_MIN
            ):
                font_size -= 1
            line_height_mm = self._get_line_height_mm(font_size, is_connector=False)
            return [(text_only, font_size, False)], line_height_mm

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

        lines: list[tuple[str, int, bool]] = []
        total_height = 0.0
        for seg in segments:
            font_pt = main_font if seg["type"] == "main" else connector_font
            is_conn = seg["type"] == "connector"
            lines.append((seg["text"], font_pt, is_conn))
            total_height += self._get_line_height_mm(font_pt, is_connector=is_conn)

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
                is_conn = seg["type"] == "connector"
                lines.append((seg["text"], font_pt, is_conn))
                total_height += self._get_line_height_mm(font_pt, is_connector=is_conn)

        return lines, total_height

    def _scale_lines_to_fit_vertical(
        self,
        lines: list[tuple[str, int, bool]],
        available_vertical: float,
    ) -> tuple[list[tuple[str, int, bool]], float]:
        """
        Scale down font sizes until total line height fits in available_vertical.
        Returns (scaled lines, new total_height). Preserves is_connector per line.
        """
        if not lines:
            return [], 0.0
        total_height = sum(
            self._get_line_height_mm(font_pt, is_connector=ic)
            for _, font_pt, ic in lines
        )
        max_iter = 25
        while total_height > available_vertical and total_height > 0 and max_iter > 0:
            max_iter -= 1
            prev_fonts = tuple(font_pt for _, font_pt, _ in lines)
            scale = (available_vertical * 0.99) / total_height
            new_lines: list[tuple[str, int, bool]] = []
            for text, font_pt, is_conn in lines:
                new_pt = max(FONT_MIN, int(font_pt * scale))
                new_lines.append((text, new_pt, is_conn))
            new_total = sum(
                self._get_line_height_mm(font_pt, is_connector=ic)
                for _, font_pt, ic in new_lines
            )
            lines = new_lines
            total_height = new_total
            if total_height <= available_vertical:
                break
            if tuple(font_pt for _, font_pt, _ in lines) == prev_fonts:
                break
        return lines, total_height

    def _draw_debug_line(  # pylint: disable=too-many-arguments
        self,
        y_mm: float,
        red: int,
        green: int,
        blue: int,
        label: str,
    ) -> None:
        """Draw a horizontal dashed line with a small label (DEBUG_BOUNDING only)."""
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
        # No cell padding so full width is for text (avoids wrap from c_margin)
        self.c_margin = 0

        lines, total_height = self.get_segment_layout(text)
        available_vertical = self.h - self.t_margin - self.b_margin
        content_width = self.w - self.l_margin - self.r_margin
        # Use same width for drawing as for layout (keeps words from being cut off)
        draw_width = max(10.0, content_width - WIDTH_SAFETY_MM)
        draw_width = min(draw_width, content_width)  # never exceed content
        content_right = self.w - self.r_margin
        content_bottom = self.h - self.b_margin
        # Red margin rect (DEBUG_BOUNDING) uses h - 2*t_margin height, so its bottom is h - t_margin
        content_bottom_inside_red = self.h - self.t_margin
        # Center the text block horizontally; clamp so block stays inside red margin
        x_start = self.l_margin + max(0, (content_width - draw_width) / 2)
        x_start = max(self.l_margin, min(x_start, self.w - self.r_margin - draw_width))

        # Safety: ensure text block never exceeds page (scale down until it fits)
        if total_height > available_vertical:
            lines, total_height = self._scale_lines_to_fit_vertical(
                lines, available_vertical
            )

        # Short blocks (1–2 lines) start higher; multi-line stays centered
        n_lines = len(lines)
        ratio = (
            VERTICAL_CENTER_RATIO_SHORT
            if n_lines <= 2
            else VERTICAL_CENTER_RATIO
        )
        y_offset = self.t_margin + (available_vertical - total_height) * ratio
        y_offset = min(y_offset, self.h - self.b_margin - total_height)
        y_offset = max(self.t_margin, y_offset)

        if DEBUG:
            block_fits = (
                total_height <= available_vertical
                and content_width <= (self.w - self.l_margin - self.r_margin)
                and (y_offset + total_height) <= content_bottom
                and self.l_margin >= 0
                and y_offset >= self.t_margin
            )
            if block_fits:
                print(f"   [OK] text block fits within page")
            else:
                print(
                    f"   [WARNING] text block would exceed page "
                    f"(total_h={total_height:.1f} available={available_vertical:.1f} "
                    f"y_end={y_offset + total_height:.1f} content_bottom={content_bottom:.1f})"
                )
            print(f"   segments: {len(lines)}")
            print(f"   total_height: {total_height:.2f} mm")
            print(f"   y_offset: {y_offset:.2f} draw_width: {draw_width:.2f} x_start: {x_start:.2f} mm")
            print(f"   page: w={self.w:.1f} h={self.h:.1f} content_bottom={content_bottom:.1f}")

        if DEBUG_BOUNDING:
            self._draw_debug_line(self.t_margin, 255, 0, 0, "MARGIN")
            self._draw_debug_line(y_offset, 0, 255, 0, "YOFFSET")
            cyan_x = max(self.l_margin, min(x_start, self.w - self.r_margin - 1))
            cyan_y = max(self.t_margin, min(y_offset, content_bottom_inside_red - 1))
            cyan_w = min(draw_width, self.w - self.r_margin - cyan_x)
            cyan_h = min(total_height, max(0, content_bottom_inside_red - cyan_y))
            self.set_draw_color(0, 200, 255)
            self.set_line_width(0.5)
            self.rect(cyan_x, cyan_y, cyan_w, cyan_h, "D")
            self.set_line_width(0.2)

        self.set_fill_color(0, 0, 0)
        self.set_text_color(0, 0, 0)

        current_y = y_offset
        for i, (line_text, font_pt, is_connector) in enumerate(lines):
            line_height_mm, metrics = self._get_line_height_and_metrics(
                font_pt, is_connector=is_connector
            )
            if DEBUG:
                print(
                    f"   line {i + 1}: {font_pt:.0f} pt "
                    f"| {metrics.get('source', '?')} scale={metrics['scale']:.3f} "
                    f"| glyph_h={metrics['glyph_height_mm']:.2f} mm "
                    f"line_h={metrics['line_height_mm']:.2f} mm "
                    f"| '{line_text}'"
                )
            self.set_xy(x_start, current_y)
            self.set_font(self.FONT_FAMILY, "", font_pt)
            w_cell = min(draw_width, self.w - self.r_margin - x_start)
            border = 1 if DEBUG_BOUNDING else 0
            if DEBUG_BOUNDING:
                self.set_draw_color(255, 0, 255)  # magenta per-line box
            self.multi_cell(
                w=w_cell,
                h=line_height_mm,
                align="C",
                txt=line_text,
                border=border,
            )
            current_y += line_height_mm


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
    pdf.set_margins(CONTENT_MARGIN_MM, CONTENT_MARGIN_MM)

    if DEBUG:
        print(f"\npage WIDTH: {pdf.w:.2f} mm  height: {pdf.h:.2f} mm")
        print(
            f"margin L: {pdf.l_margin:.2f} R: {pdf.r_margin:.2f} "
            f"T: {pdf.t_margin:.2f} B: {pdf.b_margin:.2f}"
        )
    if DEBUG_BOUNDING:
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
