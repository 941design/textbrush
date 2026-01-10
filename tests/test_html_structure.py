"""Property-based tests for HTML structure validity.

Tests verify that the HTML structure meets all specification requirements:
- All required element IDs exist and are unique
- CSS files linked in correct order (variables → animations → main)
- Semantic HTML5 structure (main, section elements)
- Button structure with proper subcomponents (icon, label, shortcut)
- Accessibility attributes present (alt, title, aria-*)
- Loading overlay initially hidden
- Proper DOCTYPE and meta tags
"""

from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Tuple

import pytest


# HTML Parser to extract element information
class HTMLStructureParser(HTMLParser):
    """Parse HTML and extract element structure for validation."""

    def __init__(self):
        super().__init__()
        self.elements_by_id: Dict[str, str] = {}
        self.css_links: List[str] = []
        self.script_tags: List[Dict[str, str]] = []
        self.all_elements: List[Tuple[str, Dict[str, str]]] = []
        self.stack: List[str] = []
        self.has_doctype = False

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        attrs_dict = dict(attrs)
        self.all_elements.append((tag, attrs_dict))
        self.stack.append(tag)

        if tag == "link" and attrs_dict.get("rel") == "stylesheet":
            href = attrs_dict.get("href", "")
            self.css_links.append(href)

        if tag == "script":
            self.script_tags.append(attrs_dict)

        if "id" in attrs_dict:
            self.elements_by_id[attrs_dict["id"]] = tag

    def handle_endtag(self, tag: str) -> None:
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()

    def handle_decl(self, decl: str) -> None:
        if decl.lower().startswith("doctype html"):
            self.has_doctype = True


def load_html() -> str:
    """Load HTML file from project."""
    html_path = Path(__file__).parent.parent / "src-tauri" / "ui" / "index.html"
    return html_path.read_text(encoding="utf-8")


def parse_html(html: str) -> HTMLStructureParser:
    """Parse HTML and return parser with extracted information."""
    parser = HTMLStructureParser()
    parser.feed(html)
    return parser


class TestHTMLBasics:
    """Test basic HTML structure requirements."""

    def test_doctype_present(self):
        """DOCTYPE must be present for HTML5 validity."""
        html = load_html()
        assert html.strip().startswith("<!DOCTYPE html>"), "HTML must start with <!DOCTYPE html>"

    def test_html_tag_with_lang_attribute(self):
        """HTML root element should have lang attribute for accessibility."""
        html = load_html()
        parser = parse_html(html)
        assert any(tag == "html" and attrs.get("lang") for tag, attrs in parser.all_elements), (
            "html element must have lang attribute"
        )

    def test_meta_charset_present(self):
        """Meta charset UTF-8 required for proper character encoding."""
        html = load_html()
        parser = parse_html(html)
        has_charset = any(
            tag == "meta" and attrs.get("charset") == "UTF-8" for tag, attrs in parser.all_elements
        )
        assert has_charset, "Meta charset UTF-8 must be present"

    def test_meta_viewport_present(self):
        """Meta viewport required for responsive design."""
        html = load_html()
        parser = parse_html(html)
        has_viewport = any(
            tag == "meta"
            and attrs.get("name") == "viewport"
            and "width=device-width" in (attrs.get("content") or "")
            for tag, attrs in parser.all_elements
        )
        assert has_viewport, "Meta viewport must be present with width=device-width"

    def test_title_is_textbrush(self):
        """Page title must be 'Textbrush' for application identification."""
        html = load_html()
        assert "<title>Textbrush</title>" in html, "Title must be 'Textbrush'"


class TestCSSLinking:
    """Test CSS file linking and order."""

    def test_css_files_linked_in_correct_order(self):
        """CSS files must be linked in exact order: variables → animations → main."""
        html = load_html()
        parser = parse_html(html)

        assert len(parser.css_links) == 3, "Exactly 3 CSS files must be linked"

        expected_order = [
            "/styles/variables.css",
            "/styles/animations.css",
            "/styles/main.css",
        ]

        for i, expected_href in enumerate(expected_order):
            assert parser.css_links[i] == expected_href, (
                f"CSS file {i + 1} must be {expected_href}, got {parser.css_links[i]}"
            )

    def test_script_has_module_type(self):
        """Main script must have type='module' for ES6 module support."""
        html = load_html()
        parser = parse_html(html)

        module_scripts = [s for s in parser.script_tags if s.get("type") == "module"]
        assert len(module_scripts) >= 1, "At least one script with type='module' required"

        # Accept either main.js (development) or bundle.js (production build)
        main_script = next(
            (
                s
                for s in parser.script_tags
                if "main.js" in s.get("src", "") or "bundle.js" in s.get("src", "")
            ),
            None,
        )
        assert main_script is not None, "Script tag for main.js or bundle.js must be present"
        assert main_script.get("type") == "module", "Main script must have type='module'"


class TestRequiredElementIDs:
    """Test that all required element IDs exist and are unique."""

    REQUIRED_IDS = {
        "app": "main",
        "current-image": "img",
        "loading-overlay": "div",
        "prompt-display": "div",
        "prev-btn": "button",
        "pause-btn": "button",
        "next-btn": "button",
        "delete-btn": "button",
        "accept-btn": "button",
        "abort-btn": "button",
    }

    def test_all_required_ids_exist(self):
        """All specified element IDs must be present in HTML."""
        html = load_html()
        parser = parse_html(html)

        for element_id, expected_tag in self.REQUIRED_IDS.items():
            assert element_id in parser.elements_by_id, f"Element with id '{element_id}' not found"

    def test_all_ids_are_unique(self):
        """All element IDs must be unique (no duplicates)."""
        html = load_html()
        parser = parse_html(html)

        id_count = {}
        for tag, attrs in parser.all_elements:
            if "id" in attrs:
                element_id = attrs["id"]
                id_count[element_id] = id_count.get(element_id, 0) + 1

        duplicates = {id_val: count for id_val, count in id_count.items() if count > 1}
        assert not duplicates, f"Duplicate IDs found: {duplicates}"

    def test_element_ids_have_correct_tags(self):
        """Element IDs must be on elements of the correct type."""
        html = load_html()
        parser = parse_html(html)

        for element_id, expected_tag in self.REQUIRED_IDS.items():
            actual_tag = parser.elements_by_id.get(element_id)
            assert actual_tag == expected_tag, (
                f"Element #{element_id} must be <{expected_tag}>, got <{actual_tag}>"
            )


class TestSemanticHTML:
    """Test semantic HTML5 structure."""

    def test_main_element_present(self):
        """Main element required for semantic structure."""
        html = load_html()
        assert "<main" in html, "Page must contain a <main> element"

    def test_sections_present(self):
        """Section elements required for content organization."""
        html = load_html()
        parser = parse_html(html)

        section_count = sum(1 for tag, _ in parser.all_elements if tag == "section")
        assert section_count >= 3, (
            "At least 3 <section> elements required (viewer, status-bar, controls)"
        )

    def test_section_classes_present(self):
        """Sections must have identifying classes."""
        html = load_html()
        parser = parse_html(html)

        section_elements = [(tag, attrs) for tag, attrs in parser.all_elements if tag == "section"]
        classes = {attrs.get("class", "") for _, attrs in section_elements}

        required_classes = {"viewer", "status-bar", "controls"}
        found_classes = {cls for cls in classes if any(req in cls for req in required_classes)}

        assert len(found_classes) >= 3, f"Must have sections with classes: {required_classes}"


class TestButtonStructure:
    """Test button component structure with icon, label, and shortcut."""

    BUTTON_IDS = ["prev-btn", "pause-btn", "next-btn", "delete-btn", "accept-btn", "abort-btn"]
    REQUIRED_CHILD_CLASSES = ["btn-icon", "btn-label", "btn-shortcut"]

    def test_all_buttons_present(self):
        """All three control buttons must be present."""
        html = load_html()
        parser = parse_html(html)

        for btn_id in self.BUTTON_IDS:
            assert btn_id in parser.elements_by_id, f"Button with id '{btn_id}' not found"

    def test_buttons_are_button_elements(self):
        """Control buttons must be <button> elements."""
        html = load_html()
        parser = parse_html(html)

        for btn_id in self.BUTTON_IDS:
            tag = parser.elements_by_id.get(btn_id)
            assert tag == "button", f"#{btn_id} must be <button>, got <{tag}>"

    def test_buttons_have_type_button(self):
        """Buttons must have type='button' attribute."""
        html = load_html()
        parser = parse_html(html)

        for btn_id in self.BUTTON_IDS:
            button_attrs = next(
                (
                    attrs
                    for tag, attrs in parser.all_elements
                    if tag == "button" and attrs.get("id") == btn_id
                ),
                None,
            )
            assert button_attrs is not None, f"Button #{btn_id} not found"
            assert button_attrs.get("type") == "button", f"#{btn_id} must have type='button'"

    def test_button_structure_has_required_children(self):
        """Each button must contain icon, label, and shortcut spans."""
        html = load_html()

        class ButtonExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.buttons = {}
                self.current_button = None
                self.current_content = []
                self.depth = 0

            def handle_starttag(self, tag, attrs):
                attrs_dict = dict(attrs)
                if tag == "button":
                    self.current_button = attrs_dict.get("id")
                    self.depth = 1
                elif self.current_button and self.depth > 0:
                    self.depth += 1
                    if tag == "span":
                        class_attr = attrs_dict.get("class", "")
                        self.current_content.append(("start", tag, class_attr))

            def handle_endtag(self, tag):
                if self.current_button and tag == "button":
                    self.buttons[self.current_button] = self.current_content
                    self.current_button = None
                    self.current_content = []
                    self.depth = 0
                elif self.current_button and self.depth > 1:
                    self.depth -= 1

        extractor = ButtonExtractor()
        extractor.feed(html)

        for btn_id in self.BUTTON_IDS:
            assert btn_id in extractor.buttons, f"Button #{btn_id} structure not found"

            content = extractor.buttons[btn_id]
            classes_found = {item[2] for item in content if len(item) > 2}

            for required_class in self.REQUIRED_CHILD_CLASSES:
                assert any(required_class in cls for cls in classes_found), (
                    f"Button #{btn_id} missing class '{required_class}'"
                )


class TestAccessibility:
    """Test accessibility attributes and ARIA support."""

    def test_image_has_alt_text(self):
        """Image element must have alt attribute for screen readers."""
        html = load_html()
        parser = parse_html(html)

        img_attrs = next(
            (
                attrs
                for tag, attrs in parser.all_elements
                if tag == "img" and attrs.get("id") == "current-image"
            ),
            None,
        )
        assert img_attrs is not None, "Image #current-image not found"
        assert "alt" in img_attrs, "Image must have alt attribute"
        assert img_attrs["alt"], "Image alt attribute must not be empty"

    def test_buttons_have_aria_labels(self):
        """Buttons should have aria-label for accessibility."""
        html = load_html()
        parser = parse_html(html)

        btn_ids = [
            "prev-btn",
            "pause-btn",
            "next-btn",
            "delete-btn",
            "accept-btn",
            "abort-btn",
        ]
        for btn_id in btn_ids:
            button_attrs = next(
                (
                    attrs
                    for tag, attrs in parser.all_elements
                    if tag == "button" and attrs.get("id") == btn_id
                ),
                None,
            )
            assert button_attrs is not None, f"Button #{btn_id} not found"
            assert "aria-label" in button_attrs, f"Button #{btn_id} missing aria-label"

    def test_loading_overlay_has_aria_live(self):
        """Loading overlay should have aria-live='polite' for status updates."""
        html = load_html()
        parser = parse_html(html)

        overlay_attrs = next(
            (
                attrs
                for tag, attrs in parser.all_elements
                if tag == "div" and attrs.get("id") == "loading-overlay"
            ),
            None,
        )
        assert overlay_attrs is not None, "Loading overlay not found"
        assert overlay_attrs.get("aria-live") == "polite", (
            "Loading overlay must have aria-live='polite'"
        )


class TestLoadingOverlay:
    """Test loading overlay initial state."""

    def test_loading_overlay_initially_visible(self):
        """Loading overlay must be visible initially (waiting for backend state)."""
        html = load_html()
        parser = parse_html(html)

        overlay_attrs = next(
            (
                attrs
                for tag, attrs in parser.all_elements
                if tag == "div" and attrs.get("id") == "loading-overlay"
            ),
            None,
        )
        assert overlay_attrs is not None, "Loading overlay not found"
        classes = overlay_attrs.get("class", "").split()
        assert "hidden" not in classes, (
            "Loading overlay must NOT have 'hidden' class (shows 'waiting for backend')"
        )

    def test_loading_overlay_contains_spinner(self):
        """Loading overlay must contain a spinner element."""
        html = load_html()
        parser = parse_html(html)

        spinners = [
            tag
            for tag, attrs in parser.all_elements
            if tag == "div" and "spinner" in attrs.get("class", "")
        ]
        assert len(spinners) > 0, "Spinner element not found in loading overlay"

    def test_loading_overlay_contains_loading_caption(self):
        """Loading overlay must contain loading caption element."""
        html = load_html()
        parser = parse_html(html)

        caption_attrs = next(
            (
                attrs
                for tag, attrs in parser.all_elements
                if tag == "div" and "loading-caption" in attrs.get("class", "")
            ),
            None,
        )
        assert caption_attrs is not None, "Loading caption not found in overlay"


class TestImageContainer:
    """Test image container structure."""

    def test_image_container_has_correct_class(self):
        """Image container must have 'image-container' class."""
        html = load_html()
        parser = parse_html(html)

        container_attrs = next(
            (
                attrs
                for tag, attrs in parser.all_elements
                if tag == "div" and "image-container" in attrs.get("class", "")
            ),
            None,
        )
        assert container_attrs is not None, "Image container not found"

    def test_current_image_has_correct_class(self):
        """Current image must have 'current-image' class."""
        html = load_html()
        parser = parse_html(html)

        img_attrs = next(
            (
                attrs
                for tag, attrs in parser.all_elements
                if tag == "img" and "current-image" in attrs.get("class", "")
            ),
            None,
        )
        assert img_attrs is not None, "Current image not found"

    def test_current_image_has_id(self):
        """Current image must have id='current-image'."""
        html = load_html()
        parser = parse_html(html)

        img_attrs = next(
            (
                attrs
                for tag, attrs in parser.all_elements
                if tag == "img" and attrs.get("id") == "current-image"
            ),
            None,
        )
        assert img_attrs is not None, "Image with id='current-image' not found"


class TestCSSClassesUsed:
    """Test that HTML uses expected CSS classes."""

    EXPECTED_CLASSES = {
        "viewer",
        "image-container",
        "current-image",
        "loading-overlay",
        "hidden",
        "spinner",
        "loading-caption",
        "loading-label",
        "loading-prompt",
        "status-bar",
        "status-left",
        "prompt-display",
        "controls",
        "control-btn",
        "btn-prev",
        "btn-pause",
        "btn-next",
        "btn-delete",
        "btn-accept",
        "btn-abort",
        "btn-icon",
        "btn-label",
        "btn-shortcut",
    }

    def test_all_expected_classes_used(self):
        """HTML should use all expected CSS classes."""
        html = load_html()
        parser = parse_html(html)

        all_classes = set()
        for tag, attrs in parser.all_elements:
            class_str = attrs.get("class", "")
            if class_str:
                all_classes.update(class_str.split())

        for expected_class in self.EXPECTED_CLASSES:
            assert expected_class in all_classes, (
                f"Expected class '{expected_class}' not found in HTML"
            )


class TestStatusBarStructure:
    """Test status bar layout and content."""

    def test_status_bar_has_status_left(self):
        """Status bar must contain status-left div."""
        html = load_html()
        parser = parse_html(html)

        left_attrs = next(
            (
                attrs
                for tag, attrs in parser.all_elements
                if tag == "div" and "status-left" in attrs.get("class", "")
            ),
            None,
        )
        assert left_attrs is not None, "Status bar left section not found"

    def test_prompt_display_present(self):
        """Prompt display element must be present."""
        html = load_html()
        parser = parse_html(html)

        prompt_attrs = next(
            (
                attrs
                for tag, attrs in parser.all_elements
                if tag == "div" and attrs.get("id") == "prompt-display"
            ),
            None,
        )
        assert prompt_attrs is not None, "Prompt display not found"

    def test_metadata_panel_present(self):
        """Metadata panel must be present (seed now displayed in metadata panel)."""
        html = load_html()
        parser = parse_html(html)

        metadata_panel = next(
            (
                attrs
                for tag, attrs in parser.all_elements
                if tag == "aside" and attrs.get("id") == "metadata-panel"
            ),
            None,
        )
        assert metadata_panel is not None, "Metadata panel not found"

        metadata_seed = next(
            (
                attrs
                for tag, attrs in parser.all_elements
                if tag == "dd" and attrs.get("id") == "metadata-seed"
            ),
            None,
        )
        assert metadata_seed is not None, "Metadata seed element not found"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
