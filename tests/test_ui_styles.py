"""
Property-based CSS testing for main.css

This module verifies CSS implementation against specification invariants:
- All element IDs and classes exist and have proper styling
- All CSS custom properties (variables) are used consistently
- Layout uses proper flexbox properties
- Button states support keyboard and mouse interaction
- Accessibility features (focus-visible) are implemented
"""

import re
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st


class CSSParser:
    """Simple CSS property extractor for verification."""

    def __init__(self, css_content: str):
        self.content = css_content
        self._selectors_cache = None

    @property
    def selectors(self) -> dict:
        """Parse CSS into selector -> properties mapping."""
        if self._selectors_cache is not None:
            return self._selectors_cache

        result = {}
        # Remove comments first
        content_no_comments = re.sub(r"/\*.*?\*/", "", self.content, flags=re.DOTALL)
        # Remove @import statements (they end with ;, not {})
        content_no_imports = re.sub(r"@import\s+[^;]+;", "", content_no_comments)
        # Remove @-rules with bodies (keyframes, media, etc.) - match { } pairs
        parts = content_no_imports.split("@")
        clean_content = parts[0]  # Everything before first @
        for part in parts[1:]:
            # Find the first { to determine if this is a rule with a body
            brace_pos = part.find("{")
            if brace_pos == -1:
                # No rule body, just add it
                clean_content += part
            else:
                # Skip the @rule, add content after its closing brace
                brace_count = 1
                i = brace_pos + 1
                while i < len(part) and brace_count > 0:
                    if part[i] == "{":
                        brace_count += 1
                    elif part[i] == "}":
                        brace_count -= 1
                    i += 1
                if i < len(part):
                    clean_content += part[i:]

        # Use DOTALL to match newlines within groups
        selector_pattern = r"([^{]+?)\s*\{([^}]+)\}"
        for match in re.finditer(selector_pattern, clean_content, re.DOTALL):
            selector_raw = match.group(1).strip()
            # Skip empty selectors
            if not selector_raw:
                continue
            properties_text = match.group(2).strip()

            # Split multiple selectors (comma-separated)
            selectors_list = [s.strip() for s in selector_raw.split(",")]

            properties = {}
            for prop in properties_text.split(";"):
                if ":" in prop:
                    key, value = prop.split(":", 1)
                    properties[key.strip().lower()] = value.strip().lower()

            # Store properties for each selector (merge with existing)
            for sel in selectors_list:
                if sel:
                    if sel in result:
                        result[sel].update(properties)
                    else:
                        result[sel] = properties.copy()

        self._selectors_cache = result
        return result

    def get_selector_properties(self, selector: str) -> dict:
        """Get all properties for a selector."""
        return self.selectors.get(selector, {})

    def has_selector(self, selector: str) -> bool:
        """Check if selector exists."""
        return selector in self.selectors

    def get_all_selectors(self) -> list[str]:
        """Get all selectors in CSS."""
        return list(self.selectors.keys())

    def uses_custom_property(self, property_name: str) -> bool:
        """Check if CSS uses var() for a property across any selector."""
        pattern = rf"--{property_name}"
        return bool(re.search(pattern, self.content))

    def has_keyframe(self, keyframe_name: str) -> bool:
        """Check if @keyframes exists."""
        pattern = rf"@keyframes\s+{keyframe_name}"
        return bool(re.search(pattern, self.content))


def resolve_imports(content: str, base_path: Path) -> str:
    """Resolve @import url('./...') statements by inlining imported files."""
    import_pattern = r"@import\s+url\(['\"](.+?)['\"]\)\s*;"

    def replace_import(match: re.Match) -> str:
        import_path = match.group(1)
        # Resolve relative path
        if import_path.startswith('./'):
            import_path = import_path[2:]
        full_path = base_path / import_path
        if full_path.exists():
            with open(full_path) as f:
                imported_content = f.read()
            # Recursively resolve imports in imported file
            return resolve_imports(imported_content, full_path.parent)
        return ""  # Import not found, remove it

    return re.sub(import_pattern, replace_import, content)


def load_css_file() -> tuple[str, CSSParser]:
    """Load and parse main.css with resolved imports."""
    css_path = Path(__file__).parent.parent / "src-tauri" / "ui" / "styles" / "main.css"
    with open(css_path) as f:
        content = f.read()
    # Resolve @import statements to get complete CSS
    resolved_content = resolve_imports(content, css_path.parent)
    return resolved_content, CSSParser(resolved_content)


# ============================================================================
# TESTS: Global Reset and Body Styles
# ============================================================================


def test_global_reset_universal_selector():
    """All elements should have margin and padding reset."""
    _, parser = load_css_file()
    assert parser.has_selector("*"), "Universal selector * not found"
    props = parser.get_selector_properties("*")
    assert "margin" in props and props["margin"] == "0", "* should have margin: 0"
    assert "padding" in props and props["padding"] == "0", "* should have padding: 0"
    assert "box-sizing" in props and props["box-sizing"] == "border-box", (
        "* should have box-sizing: border-box"
    )


def test_body_dark_theme():
    """Body should use dark theme CSS custom properties."""
    _, parser = load_css_file()
    assert parser.has_selector("body"), "body selector not found"
    props = parser.get_selector_properties("body")
    assert "var(--font-sans)" in props.get("font-family", ""), "body should use var(--font-sans)"
    assert "var(--bg-primary)" in props.get("background", ""), "body should use var(--bg-primary)"
    assert "var(--text-primary)" in props.get("color", ""), "body should use var(--text-primary)"
    assert props.get("overflow") == "hidden", "body should have overflow: hidden"
    assert props.get("user-select") == "none", "body should have user-select: none"


# ============================================================================
# TESTS: Application Layout
# ============================================================================


def test_app_layout_flex_column():
    """#app should be 100vh flexbox column."""
    _, parser = load_css_file()
    assert parser.has_selector("#app"), "#app selector not found"
    props = parser.get_selector_properties("#app")
    assert props.get("display") == "flex", "#app should have display: flex"
    assert props.get("flex-direction") == "column", "#app should have flex-direction: column"


# ============================================================================
# TESTS: Image Viewer Section
# ============================================================================


def test_viewer_section_layout():
    """Viewer section should flex: 1 and center content."""
    _, parser = load_css_file()
    assert parser.has_selector(".viewer"), ".viewer selector not found"
    props = parser.get_selector_properties(".viewer")
    assert "flex" in props and "1" in props["flex"], ".viewer should have flex: 1"
    assert props.get("display") == "flex", ".viewer should have display: flex"
    assert props.get("align-items") == "center", ".viewer should center vertically"
    assert props.get("justify-content") == "center", ".viewer should center horizontally"


# ============================================================================
# TESTS: Image Container and Current Image
# ============================================================================


def test_image_container_positioning():
    """Image container should have relative positioning for overlay."""
    _, parser = load_css_file()
    assert parser.has_selector(".image-container"), ".image-container not found"
    props = parser.get_selector_properties(".image-container")
    assert props.get("position") == "relative", ".image-container should have position: relative"


def test_current_image_object_fit():
    """Current image should maintain aspect ratio."""
    _, parser = load_css_file()
    assert parser.has_selector(".current-image"), ".current-image not found"
    props = parser.get_selector_properties(".current-image")
    assert props.get("object-fit") == "contain", ".current-image should have object-fit: contain"
    assert "var(--shadow-lg)" in props.get("box-shadow", ""), (
        ".current-image should use var(--shadow-lg)"
    )


def test_current_image_loading_state():
    """Current image.loading should reduce opacity."""
    _, parser = load_css_file()
    assert parser.has_selector(".current-image.loading"), ".current-image.loading not found"
    props = parser.get_selector_properties(".current-image.loading")
    assert "opacity" in props and "0.3" in props["opacity"], (
        ".current-image.loading should have opacity 0.3"
    )


# ============================================================================
# TESTS: Loading Overlay and Spinner
# ============================================================================


def test_loading_overlay_absolute_positioning():
    """Loading overlay should absolutely cover image container."""
    _, parser = load_css_file()
    assert parser.has_selector(".loading-overlay"), ".loading-overlay not found"
    props = parser.get_selector_properties(".loading-overlay")
    assert props.get("position") == "absolute", ".loading-overlay should have position: absolute"
    assert props.get("inset") == "0" or "top" in props, (
        ".loading-overlay should use inset or top/left/right/bottom"
    )


def test_loading_overlay_hidden_state():
    """Loading overlay.hidden should have opacity 0."""
    _, parser = load_css_file()
    assert parser.has_selector(".loading-overlay.hidden"), ".loading-overlay.hidden not found"
    props = parser.get_selector_properties(".loading-overlay.hidden")
    assert props.get("opacity") == "0", ".loading-overlay.hidden should have opacity: 0"
    assert props.get("pointer-events") == "none", (
        ".loading-overlay.hidden should have pointer-events: none"
    )


def test_spinner_animation():
    """Spinner should use spin animation."""
    _, parser = load_css_file()
    assert parser.has_selector(".spinner"), ".spinner not found"
    props = parser.get_selector_properties(".spinner")
    assert "40px" in props.get("width", "") and "40px" in props.get("height", ""), (
        ".spinner should be 40px x 40px"
    )
    assert "var(--border-subtle)" in props.get("border", ""), (
        ".spinner should use var(--border-subtle) border"
    )
    assert "var(--accent-primary)" in props.get("border-top-color", ""), (
        ".spinner should use var(--accent-primary) for border-top-color"
    )
    assert "spin" in props.get("animation", ""), ".spinner should use spin animation"


def test_spinner_keyframe_exists():
    """Spin keyframe should exist."""
    _, parser = load_css_file()
    assert parser.has_keyframe("spin"), "spin keyframe not found"


# ============================================================================
# TESTS: Status Bar Section
# ============================================================================


def test_status_bar_layout():
    """Status bar should flex row with space-between."""
    _, parser = load_css_file()
    assert parser.has_selector(".status-bar"), ".status-bar not found"
    props = parser.get_selector_properties(".status-bar")
    assert props.get("display") == "flex", ".status-bar should have display: flex"
    assert props.get("justify-content") == "space-between", (
        ".status-bar should have justify-content: space-between"
    )
    assert "var(--bg-tertiary)" in props.get("background", ""), (
        ".status-bar should use var(--bg-tertiary)"
    )


def test_status_left_and_right_sections():
    """Status left and right sections should exist."""
    _, parser = load_css_file()
    assert parser.has_selector(".status-left"), ".status-left not found"
    assert parser.has_selector(".status-right"), ".status-right not found"
    props_right = parser.get_selector_properties(".status-right")
    assert props_right.get("display") == "flex", ".status-right should use flexbox layout"


def test_prompt_display_monospace():
    """Prompt display should use monospace font."""
    _, parser = load_css_file()
    assert parser.has_selector(".prompt-display"), ".prompt-display not found"
    props = parser.get_selector_properties(".prompt-display")
    assert "var(--font-mono)" in props.get("font-family", ""), (
        ".prompt-display should use var(--font-mono)"
    )
    assert props.get("overflow") == "hidden" and props.get("text-overflow") == "ellipsis", (
        ".prompt-display should handle overflow with ellipsis"
    )


# ============================================================================
# TESTS: Buffer Indicator
# ============================================================================


def test_buffer_indicator_flex_layout():
    """Buffer indicator should use flex layout."""
    _, parser = load_css_file()
    assert parser.has_selector(".buffer-indicator"), ".buffer-indicator not found"
    props = parser.get_selector_properties(".buffer-indicator")
    assert props.get("display") == "flex", ".buffer-indicator should have display: flex"
    assert "center" in props.get("align-items", ""), ".buffer-indicator should center items"


def test_buffer_dots_container():
    """Buffer dots should use flex with 3px gap."""
    _, parser = load_css_file()
    assert parser.has_selector(".buffer-dots"), ".buffer-dots not found"
    props = parser.get_selector_properties(".buffer-dots")
    assert props.get("display") == "flex", ".buffer-dots should have display: flex"
    assert "3px" in props.get("gap", ""), ".buffer-dots should have 3px gap"


def test_buffer_dot_styling():
    """Individual buffer dots should be 6px circles."""
    _, parser = load_css_file()
    assert parser.has_selector(".buffer-dot"), ".buffer-dot not found"
    props = parser.get_selector_properties(".buffer-dot")
    assert "6px" in props.get("width", "") and "6px" in props.get("height", ""), (
        ".buffer-dot should be 6px x 6px"
    )
    assert "50%" in props.get("border-radius", ""), (
        ".buffer-dot should be circular (border-radius: 50%)"
    )
    assert "var(--border-subtle)" in props.get("background", ""), (
        ".buffer-dot should use var(--border-subtle)"
    )


def test_buffer_dot_filled_state():
    """Filled buffer dots should use accent color."""
    _, parser = load_css_file()
    assert parser.has_selector(".buffer-dot.filled"), ".buffer-dot.filled not found"
    props = parser.get_selector_properties(".buffer-dot.filled")
    assert "var(--accent-primary)" in props.get("background", ""), (
        ".buffer-dot.filled should use var(--accent-primary)"
    )


def test_buffer_generating_animation():
    """Buffer indicator with buffer-generating should pulse last dot."""
    _, parser = load_css_file()
    selectors = parser.get_all_selectors()
    generating_selector = [s for s in selectors if "buffer-generating" in s and "buffer-dot" in s]
    assert len(generating_selector) > 0, (
        "Should have selector for buffer-generating buffer-dot animation"
    )


def test_pulse_keyframe_exists():
    """Pulse keyframe should exist for buffer animation."""
    _, parser = load_css_file()
    assert parser.has_keyframe("pulse"), "pulse keyframe not found"


# ============================================================================
# TESTS: Controls Section
# ============================================================================


def test_controls_section_layout():
    """Controls should be centered flex row."""
    _, parser = load_css_file()
    assert parser.has_selector(".controls"), ".controls not found"
    props = parser.get_selector_properties(".controls")
    assert props.get("display") == "flex", ".controls should have display: flex"
    assert props.get("justify-content") == "center", ".controls should center buttons horizontally"


# ============================================================================
# TESTS: Control Button Base Styles
# ============================================================================


def test_control_btn_base_layout():
    """Control buttons should be vertical flex with proper spacing."""
    _, parser = load_css_file()
    assert parser.has_selector(".control-btn"), ".control-btn not found"
    props = parser.get_selector_properties(".control-btn")
    assert props.get("display") == "flex", ".control-btn should have display: flex"
    assert props.get("flex-direction") == "column", (
        ".control-btn should have flex-direction: column"
    )
    assert props.get("cursor") == "pointer", ".control-btn should have cursor: pointer"


def test_control_btn_hover_state():
    """Control buttons should change on hover."""
    _, parser = load_css_file()
    assert parser.has_selector(".control-btn:hover"), ".control-btn:hover not found"
    props = parser.get_selector_properties(".control-btn:hover")
    assert "var(--bg-tertiary)" in props.get("background", ""), (
        ".control-btn:hover should use var(--bg-tertiary)"
    )


def test_control_btn_active_state():
    """Control buttons should scale on active."""
    _, parser = load_css_file()
    assert parser.has_selector(".control-btn:active"), ".control-btn:active not found"
    props = parser.get_selector_properties(".control-btn:active")
    assert "0.98" in props.get("transform", ""), ".control-btn:active should have scale(0.98)"


def test_control_btn_disabled_state():
    """Disabled buttons should be reduced opacity."""
    _, parser = load_css_file()
    assert parser.has_selector(".control-btn:disabled"), ".control-btn:disabled not found"
    props = parser.get_selector_properties(".control-btn:disabled")
    assert "0.5" in props.get("opacity", ""), ".control-btn:disabled should have opacity: 0.5"


def test_control_btn_focus_visible_keyboard():
    """Control buttons should have visible focus for keyboard navigation."""
    _, parser = load_css_file()
    assert parser.has_selector(".control-btn:focus-visible"), ".control-btn:focus-visible not found"
    props = parser.get_selector_properties(".control-btn:focus-visible")
    assert "outline" in props and "var(--accent-primary)" in props.get("outline", ""), (
        ".control-btn:focus-visible should have outline with accent color"
    )


# ============================================================================
# TESTS: Button Variants
# ============================================================================


def test_btn_accept_variant():
    """Accept button should have green hover state."""
    _, parser = load_css_file()
    assert parser.has_selector(".btn-accept:hover"), ".btn-accept:hover not found"
    props = parser.get_selector_properties(".btn-accept:hover")
    assert "var(--accent-success)" in props.get("border-color", ""), (
        ".btn-accept:hover should use var(--accent-success)"
    )


def test_btn_abort_variant():
    """Abort button should have red hover state."""
    _, parser = load_css_file()
    assert parser.has_selector(".btn-abort:hover"), ".btn-abort:hover not found"
    props = parser.get_selector_properties(".btn-abort:hover")
    assert "var(--accent-danger)" in props.get("border-color", ""), (
        ".btn-abort:hover should use var(--accent-danger)"
    )


def test_btn_skip_variant():
    """Skip button should exist with proper styling."""
    _, parser = load_css_file()
    assert parser.has_selector(".btn-skip:hover"), ".btn-skip:hover not found"


# ============================================================================
# TESTS: Button Component Parts
# ============================================================================


def test_btn_icon_sizing():
    """Button icons should be 20px."""
    _, parser = load_css_file()
    assert parser.has_selector(".btn-icon"), ".btn-icon not found"
    props = parser.get_selector_properties(".btn-icon")
    assert "20px" in props.get("font-size", ""), ".btn-icon should have font-size: 20px"


def test_btn_label_styling():
    """Button labels should have 13px font-weight 500."""
    _, parser = load_css_file()
    assert parser.has_selector(".btn-label"), ".btn-label not found"
    props = parser.get_selector_properties(".btn-label")
    assert "13px" in props.get("font-size", ""), ".btn-label should have font-size: 13px"
    assert props.get("font-weight") == "500", ".btn-label should have font-weight: 500"


def test_btn_shortcut_styling():
    """Button shortcuts should be monospace 10px."""
    _, parser = load_css_file()
    assert parser.has_selector(".btn-shortcut"), ".btn-shortcut not found"
    props = parser.get_selector_properties(".btn-shortcut")
    assert "10px" in props.get("font-size", ""), ".btn-shortcut should have font-size: 10px"
    assert "var(--font-mono)" in props.get("font-family", ""), (
        ".btn-shortcut should use var(--font-mono)"
    )


# ============================================================================
# TESTS: CSS Custom Property Usage (Invariant Checks)
# ============================================================================


@given(
    color_property=st.sampled_from(
        [
            "bg-primary",
            "bg-secondary",
            "bg-tertiary",
            "text-primary",
            "text-secondary",
            "text-muted",
            "accent-primary",
            "accent-success",
            "accent-danger",
            "border-subtle",
            "border-focus",
        ]
    )
)
def test_all_color_variables_used(color_property: str):
    """All color variables should be used in CSS."""
    _, parser = load_css_file()
    pattern = f"--{color_property}\\b"
    matches = re.findall(pattern, parser.content)
    assert len(matches) > 0, f"CSS custom property --{color_property} not used"


@given(
    spacing_property=st.sampled_from(
        ["spacing-xs", "spacing-sm", "spacing-md", "spacing-lg", "spacing-xl"]
    )
)
def test_all_spacing_variables_used(spacing_property: str):
    """All spacing variables should be used in CSS."""
    _, parser = load_css_file()
    pattern = f"--{spacing_property}\\b"
    matches = re.findall(pattern, parser.content)
    assert len(matches) > 0, f"CSS custom property --{spacing_property} not used"


@given(transition_property=st.sampled_from(["transition-fast", "transition-normal"]))
def test_all_transition_variables_used(transition_property: str):
    """Required transition variables should be used in CSS."""
    _, parser = load_css_file()
    pattern = f"--{transition_property}\\b"
    matches = re.findall(pattern, parser.content)
    assert len(matches) > 0, f"CSS custom property --{transition_property} not used"


# ============================================================================
# TESTS: No Hardcoded Values (Invariant Check)
# ============================================================================


def test_no_hardcoded_colors():
    """CSS should not contain hardcoded color values (use var() instead).

    Note: This only checks main.css and animations.css, not variables.css
    which legitimately defines the actual color values for CSS custom properties.
    """
    # Load only main.css and animations.css (exclude variables.css)
    css_path = Path(__file__).parent.parent / "src-tauri" / "ui" / "styles" / "main.css"
    with open(css_path) as f:
        main_content = f.read()
    animations_path = css_path.parent / "animations.css"
    with open(animations_path) as f:
        animations_content = f.read()
    combined = main_content + animations_content

    hex_pattern = r"#[0-9a-fA-F]{3,6}"
    content_without_comments = re.sub(r"/\*.*?\*/", "", combined, flags=re.DOTALL)
    hex_matches = re.findall(hex_pattern, content_without_comments)
    assert len(hex_matches) == 0, f"Found hardcoded hex colors (use CSS variables): {hex_matches}"


# ============================================================================
# TESTS: Z-Index Layering
# ============================================================================


def test_loading_overlay_z_index():
    """Loading overlay should be above image (via positioning)."""
    _, parser = load_css_file()
    overlay_props = parser.get_selector_properties(".loading-overlay")
    container_props = parser.get_selector_properties(".image-container")
    assert overlay_props.get("position") == "absolute", (
        "Loading overlay should be absolutely positioned"
    )
    assert container_props.get("position") == "relative", (
        "Image container should be relatively positioned"
    )


# ============================================================================
# TESTS: Accessibility Features
# ============================================================================


def test_accessible_focus_indicators():
    """Focus indicators should use outline, not border."""
    _, parser = load_css_file()
    focus_props = parser.get_selector_properties(".control-btn:focus-visible")
    assert "outline" in focus_props, "Focus state should use outline for accessibility"
    assert "var(--accent-primary)" in focus_props.get("outline", ""), (
        "Focus outline should use custom color variable"
    )


def test_user_select_none_on_body():
    """UI should prevent text selection (user-select: none)."""
    _, parser = load_css_file()
    body_props = parser.get_selector_properties("body")
    assert body_props.get("user-select") == "none", "body should have user-select: none"


# ============================================================================
# TESTS: Complete Element and Class Coverage
# ============================================================================


@given(
    css_class=st.sampled_from(
        [
            ".viewer",
            ".image-container",
            ".current-image",
            ".loading-overlay",
            ".spinner",
            ".loading-text",
            ".status-bar",
            ".status-left",
            ".status-right",
            ".prompt-display",
            ".buffer-indicator",
            ".buffer-dots",
            ".buffer-dot",
            ".buffer-text",
            ".seed-display",
            ".controls",
            ".control-btn",
            ".btn-icon",
            ".btn-label",
            ".btn-shortcut",
            ".btn-accept",
            ".btn-abort",
            ".btn-skip",
        ]
    )
)
def test_all_required_css_classes_exist(css_class: str):
    """All CSS classes from spec should be defined."""
    _, parser = load_css_file()
    selectors = parser.get_all_selectors()
    class_exists = any(css_class in sel for sel in selectors)
    assert class_exists, f"CSS class {css_class} not found in stylesheet"
