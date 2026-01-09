"""Property-based tests for config controls integration.

Tests verify that config controls are properly integrated into the UI:
- HTML structure includes all required input elements
- JavaScript properly imports and initializes config controls module
- CSS styling rules exist for all config control classes
- State management includes aspectRatio property
- Element caching includes new config control references
"""

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Tuple


class HTMLStructureParser(HTMLParser):
    """Parse HTML and extract element structure for validation."""

    def __init__(self):
        super().__init__()
        self.elements_by_id: Dict[str, str] = {}
        self.elements_by_class: Dict[str, List[Tuple[str, Dict[str, str]]]] = {}
        self.all_elements: List[Tuple[str, Dict[str, str]]] = []
        self.input_elements: List[Dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        attrs_dict = dict(attrs)
        self.all_elements.append((tag, attrs_dict))

        if "id" in attrs_dict:
            self.elements_by_id[attrs_dict["id"]] = tag

        if "class" in attrs_dict:
            classes = attrs_dict["class"].split()
            for cls in classes:
                if cls not in self.elements_by_class:
                    self.elements_by_class[cls] = []
                self.elements_by_class[cls].append((tag, attrs_dict))

        if tag == "input":
            self.input_elements.append(attrs_dict)


def load_html() -> str:
    """Load HTML file from project."""
    html_path = Path(__file__).parent.parent / "src-tauri" / "ui" / "index.html"
    return html_path.read_text(encoding="utf-8")


def parse_html(html: str) -> HTMLStructureParser:
    """Parse HTML and return parser with extracted information."""
    parser = HTMLStructureParser()
    parser.feed(html)
    return parser


def load_javascript() -> str:
    """Load main.js file from project."""
    js_path = Path(__file__).parent.parent / "src-tauri" / "ui" / "main.js"
    return js_path.read_text(encoding="utf-8")


def load_css() -> str:
    """Load main.css file from project."""
    css_path = Path(__file__).parent.parent / "src-tauri" / "ui" / "styles" / "main.css"
    return css_path.read_text(encoding="utf-8")


def load_config_controls_javascript() -> str:
    """Load config_controls.js file from project."""
    js_path = Path(__file__).parent.parent / "src-tauri" / "ui" / "config_controls.js"
    return js_path.read_text(encoding="utf-8")


class TestHTMLConfigControls:
    """Test HTML structure for config controls."""

    def test_prompt_input_element_exists(self):
        """Prompt input field must exist with correct ID and attributes."""
        html = load_html()
        parser = parse_html(html)

        assert "prompt-input" in parser.elements_by_id, "prompt-input element must exist"
        assert parser.elements_by_id["prompt-input"] == "input", (
            "prompt-input must be an input element"
        )

        prompt_input = next(
            (attrs for tag, attrs in parser.all_elements if attrs.get("id") == "prompt-input"),
            None,
        )
        assert prompt_input is not None
        assert prompt_input.get("type") == "text", "prompt-input must be type=text"
        assert "prompt-input" in prompt_input.get("class", ""), "prompt-input must have class"
        assert "placeholder" in prompt_input, "prompt-input should have placeholder"
        assert "aria-label" in prompt_input, "prompt-input must have aria-label for accessibility"

    def test_aspect_ratio_radio_buttons_exist(self):
        """Aspect ratio radio buttons must exist for all six preset values."""
        html = load_html()
        parser = parse_html(html)

        radio_inputs = [
            attrs
            for attrs in parser.input_elements
            if attrs.get("type") == "radio" and attrs.get("name") == "aspect-ratio"
        ]

        assert len(radio_inputs) == 6, "Must have exactly 6 aspect ratio radio buttons"

        values = [attrs.get("value") for attrs in radio_inputs]
        assert "1:1" in values, "Must have 1:1 aspect ratio option"
        assert "16:9" in values, "Must have 16:9 aspect ratio option"
        assert "3:1" in values, "Must have 3:1 aspect ratio option"
        assert "4:1" in values, "Must have 4:1 aspect ratio option"
        assert "4:5" in values, "Must have 4:5 aspect ratio option"
        assert "9:16" in values, "Must have 9:16 aspect ratio option"

        checked_radios = [attrs for attrs in radio_inputs if "checked" in attrs]
        assert len(checked_radios) == 1, "Exactly one radio button should be checked by default"
        assert checked_radios[0].get("value") == "1:1", "1:1 should be checked by default"

    def test_validation_error_element_exists(self):
        """Validation error display element must exist."""
        html = load_html()
        parser = parse_html(html)

        assert "validation-error" in parser.elements_by_id, "validation-error element must exist"

        error_elem = next(
            (attrs for tag, attrs in parser.all_elements if attrs.get("id") == "validation-error"),
            None,
        )
        assert error_elem is not None
        assert "hidden" in error_elem.get("class", ""), (
            "validation-error should be hidden by default"
        )
        assert error_elem.get("role") == "alert", "validation-error must have role=alert"
        assert error_elem.get("aria-live") == "polite", "validation-error must have aria-live"

    def test_config_controls_container_exists(self):
        """Config controls container must exist with proper structure."""
        html = load_html()
        parser = parse_html(html)

        assert "config-controls" in parser.elements_by_class, "config-controls container must exist"

    def test_control_labels_exist(self):
        """Control labels must exist for prompt and ratio."""
        html = load_html()

        label_texts_in_html = []
        html_lower = html.lower()
        if "prompt:" in html_lower:
            label_texts_in_html.append("prompt")
        # The HTML uses shortened "Ratio:" label instead of "Aspect Ratio:"
        if "ratio:" in html_lower:
            label_texts_in_html.append("ratio")

        assert len(label_texts_in_html) >= 2, "Must have labels for prompt and ratio"

    def test_legacy_prompt_display_hidden(self):
        """Legacy prompt-display should be hidden for backward compatibility."""
        html = load_html()
        parser = parse_html(html)

        assert "prompt-display" in parser.elements_by_id, (
            "prompt-display should still exist for compatibility"
        )

        prompt_display = next(
            (attrs for tag, attrs in parser.all_elements if attrs.get("id") == "prompt-display"),
            None,
        )
        style = prompt_display.get("style", "")
        assert "display" in style and "none" in style, (
            "prompt-display should be hidden via inline style"
        )


class TestJavaScriptIntegration:
    """Test JavaScript integration of config controls."""

    def test_config_controls_module_imported(self):
        """Config controls module must be imported at top of main.js."""
        js = load_javascript()
        assert "import" in js, "main.js must use ES6 imports"
        assert "ConfigControls" in js, "ConfigControls must be imported"
        # TypeScript may omit .js extension
        assert "from './config_controls.js'" in js or "from './config_controls'" in js, (
            "Must import from config_controls module"
        )

        import_lines = [
            line for line in js.split("\n") if "import" in line and "ConfigControls" in line
        ]
        assert len(import_lines) > 0, "Must have import statement"

    def test_state_includes_aspect_ratio(self):
        """State object must include aspectRatio property."""
        js = load_javascript()

        state_match = re.search(r"const state = \{([^}]+)\}", js, re.DOTALL)
        assert state_match, "State object must exist"

        state_content = state_match.group(1)
        assert "aspectRatio" in state_content, "State must include aspectRatio property"
        assert "'1:1'" in state_content or '"1:1"' in state_content, (
            "aspectRatio should default to '1:1'"
        )

    def test_elements_object_includes_config_controls(self):
        """Elements object must include references to config control elements."""
        js = load_javascript()

        elements_match = re.search(r"const elements = \{([^}]+)\}", js, re.DOTALL)
        assert elements_match, "Elements object must exist"

        elements_content = elements_match.group(1)
        assert "promptInput" in elements_content, "Elements must include promptInput"
        assert "aspectRatioRadios" in elements_content, "Elements must include aspectRatioRadios"
        assert "validationError" in elements_content, "Elements must include validationError"

    def test_cache_elements_includes_new_controls(self):
        """cacheElements function must cache new config control elements."""
        js = load_javascript()

        cache_func_match = re.search(r"function cacheElements\(\) \{([^}]+)\}", js, re.DOTALL)
        assert cache_func_match, "cacheElements function must exist"

        cache_content = cache_func_match.group(1)
        assert "getElementById('prompt-input')" in cache_content, "Must cache prompt-input"
        assert (
            "querySelectorAll('input[name=\"aspect-ratio\"]')" in cache_content
            or 'querySelectorAll("input[name=\\"aspect-ratio\\"]")' in cache_content
        ), "Must cache aspect-ratio radio buttons"
        assert "getElementById('validation-error')" in cache_content, "Must cache validation-error"

    def test_init_function_initializes_aspect_ratio(self):
        """init function must initialize aspectRatio from launch args."""
        js = load_javascript()

        init_func = re.search(r"async function init\(\) \{(.+?)^}", js, re.DOTALL | re.MULTILINE)
        assert init_func, "init function must exist"

        init_content = init_func.group(1)
        assert "state.aspectRatio" in init_content, "init must set state.aspectRatio"
        assert "launchArgs.aspect_ratio" in init_content, "Must read aspect_ratio from launch args"

    def test_init_function_calls_init_config_controls(self):
        """init function must call ConfigControls.initConfigControls."""
        js = load_javascript()

        init_func = re.search(r"async function init\(\) \{(.+?)^}", js, re.DOTALL | re.MULTILINE)
        assert init_func, "init function must exist"

        init_content = init_func.group(1)
        assert "ConfigControls.initConfigControls" in init_content, "Must call initConfigControls"
        assert "elements" in init_content and "state" in init_content, (
            "Must pass elements and state"
        )

    def test_update_generation_config_invoked_in_config_controls(self):
        """config_controls.js must invoke update_generation_config with correct parameters."""
        js = load_config_controls_javascript()

        # Must have invoke call to update_generation_config
        assert "update_generation_config" in js, "Must invoke update_generation_config"
        assert "invoke" in js, "Must use invoke to call backend"

        # Check that aspectRatio uses camelCase (Tauri converts to snake_case for Rust)
        assert "aspectRatio:" in js, "Must use camelCase aspectRatio for Tauri invoke"

        # Verify the invoke call pattern
        invoke_match = re.search(
            r"invoke\(['\"]update_generation_config['\"],\s*\{([^}]+)\}", js, re.DOTALL
        )
        assert invoke_match, "Must call invoke with update_generation_config command"

        invoke_params = invoke_match.group(1)
        assert "prompt" in invoke_params, "Must pass prompt parameter"
        assert "aspectRatio" in invoke_params, "Must pass aspectRatio parameter (camelCase)"

    def test_keyboard_listeners_ignore_input_focus(self):
        """Keyboard listeners must ignore events when user is typing in input fields."""
        js = load_javascript()

        keyboard_func = re.search(
            r"function setupKeyboardListeners\(\) \{(.+?)^}", js, re.DOTALL | re.MULTILINE
        )
        assert keyboard_func, "setupKeyboardListeners function must exist"

        keyboard_content = keyboard_func.group(1)
        # Check for target.tagName pattern (may use e.target or const target = e.target)
        has_target_check = (
            "e.target.tagName" in keyboard_content
            or "e.target.type" in keyboard_content
            or "target.tagName" in keyboard_content
            or "target.type" in keyboard_content
        )
        assert has_target_check, "Must check event target to avoid conflicts with input"
        assert "INPUT" in keyboard_content, "Must specifically check for INPUT elements"
        assert "return" in keyboard_content, "Must return early when typing in input"


class TestCSSStyles:
    """Test CSS styling for config controls."""

    def test_config_controls_styles_exist(self):
        """CSS must include styles for config-controls class."""
        css = load_css()
        assert ".config-controls" in css, "Must have styles for .config-controls"

    def test_prompt_input_styles_exist(self):
        """CSS must include styles for prompt-input class."""
        css = load_css()
        assert ".prompt-input" in css, "Must have styles for .prompt-input"

        prompt_input_styles = re.search(r"\.prompt-input \{([^}]+)\}", css, re.DOTALL)
        assert prompt_input_styles, "prompt-input must have style block"

        styles = prompt_input_styles.group(1)
        assert "background" in styles or "color" in styles, "prompt-input should have color styling"
        assert "border" in styles, "prompt-input should have border styling"
        assert "font-family" in styles, "prompt-input should have font styling"

    def test_prompt_input_focus_styles_exist(self):
        """CSS must include focus styles for prompt-input."""
        css = load_css()
        assert ".prompt-input:focus" in css, "Must have :focus styles for prompt-input"

    def test_aspect_ratio_group_styles_exist(self):
        """CSS must include styles for aspect-ratio-group."""
        css = load_css()
        assert ".aspect-ratio-group" in css, "Must have styles for .aspect-ratio-group"

    def test_radio_label_styles_exist(self):
        """CSS must include styles for radio-label class."""
        css = load_css()
        assert ".radio-label" in css, "Must have styles for .radio-label"

    def test_validation_error_styles_exist(self):
        """CSS must include styles for validation-error class."""
        css = load_css()
        assert ".validation-error" in css, "Must have styles for .validation-error"

        validation_styles = re.search(r"\.validation-error \{([^}]+)\}", css, re.DOTALL)
        assert validation_styles, "validation-error must have style block"

        styles = validation_styles.group(1)
        assert "color" in styles, "validation-error should have color styling"
        assert "var(--accent-danger)" in styles or "danger" in styles, (
            "validation-error should use danger/error color"
        )

    def test_validation_error_hidden_styles_exist(self):
        """CSS must include hidden state styles for validation-error."""
        css = load_css()
        assert ".validation-error.hidden" in css, "Must have .hidden modifier for validation-error"

    def test_control_label_styles_exist(self):
        """CSS must include styles for control-label class."""
        css = load_css()
        assert ".control-label" in css, "Must have styles for .control-label"

    def test_uses_css_variables(self):
        """Config control styles must use CSS custom properties."""
        css = load_css()

        config_section = css[css.find(".config-controls") :]

        assert "var(--" in config_section, "Must use CSS variables"
        assert "var(--spacing-" in config_section, "Must use spacing variables"
        assert "var(--bg-" in config_section or "var(--text-" in config_section, (
            "Must use color variables"
        )


class TestIntegrationProperties:
    """Property-based tests for integration behavior."""

    def test_all_html_ids_have_corresponding_javascript_cache(self):
        """Every ID in HTML should be cached in JavaScript elements object."""
        html = load_html()
        js = load_javascript()
        parser = parse_html(html)

        required_ids = {"prompt-input", "validation-error"}

        for elem_id in required_ids:
            assert elem_id in parser.elements_by_id, f"HTML must contain element with id={elem_id}"
            assert f"getElementById('{elem_id}')" in js or f'getElementById("{elem_id}")' in js, (
                f"JavaScript must cache element with id={elem_id}"
            )

    def test_all_css_classes_have_corresponding_html_elements(self):
        """Every CSS class for config controls should have corresponding HTML elements."""
        html = load_html()
        css = load_css()
        parser = parse_html(html)

        config_css_classes = [
            "config-controls",
            "prompt-control",
            "prompt-input",
            "aspect-ratio-control",
            "aspect-ratio-group",
            "radio-label",
            "control-label",
            "validation-error",
        ]

        for css_class in config_css_classes:
            assert f".{css_class}" in css, f"CSS must define styles for .{css_class}"
            assert css_class in parser.elements_by_class or css_class in html, (
                f"HTML must contain element with class={css_class}"
            )

    def test_state_properties_match_launch_args(self):
        """State properties must match launch args used in init_generation."""
        js = load_javascript()

        init_func = re.search(r"async function init\(\) \{(.+?)^}", js, re.DOTALL | re.MULTILINE)
        init_content = init_func.group(1)

        init_generation_match = re.search(
            r"invoke\('init_generation',\s*\{([^}]+)\}", init_content, re.DOTALL
        )
        assert init_generation_match, "Must call init_generation in init function"

        init_gen_params = init_generation_match.group(1)
        assert "prompt:" in init_gen_params, "init_generation must include prompt"
        assert "aspectRatio:" in init_gen_params, "init_generation must include aspectRatio"

        assert "state.prompt" in init_gen_params, "Must pass state.prompt to init_generation"
        assert (
            "state.aspectRatio" not in init_gen_params or "launchArgs.aspect_ratio" in init_content
        ), "aspectRatio must come from launch args"
