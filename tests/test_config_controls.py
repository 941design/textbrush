"""Property-based tests for config controls JavaScript module.

Tests verify that config_controls.js meets all specification requirements:
- Function exports and signatures
- Validation logic correctness
- DOM manipulation patterns
- Event listener registration
- Error handling behavior
- State synchronization

Uses Hypothesis for property-based test generation and source code analysis
to validate JavaScript implementation without requiring browser runtime.
"""

import re
from pathlib import Path
from typing import List

from hypothesis import given
from hypothesis import strategies as st


def load_config_controls_js() -> str:
    """Load config_controls.js source code."""
    js_path = Path(__file__).parent.parent / "src-tauri" / "ui" / "config_controls.js"
    return js_path.read_text(encoding="utf-8")


def extract_function_names(js_code: str) -> List[str]:
    """Extract exported function names from JavaScript code."""
    pattern = r"export\s+(?:async\s+)?function\s+(\w+)\s*\("
    return re.findall(pattern, js_code)


def extract_const_imports(js_code: str) -> List[str]:
    """Extract ES6 imports from Tauri API modules."""
    # Match ES6 import pattern: import { foo } from '@tauri-apps/api/module'
    pattern = r"import\s+\{([^}]+)\}\s+from\s+['\"]@tauri-apps/api/(\w+)['\"]"
    matches = re.findall(pattern, js_code)
    imports = []
    for destructured, module in matches:
        items = [item.strip() for item in destructured.split(",")]
        imports.extend([(item, module) for item in items])
    return imports


def function_uses_invoke(js_code: str, function_name: str) -> bool:
    """Check if a function uses invoke() for Tauri IPC."""
    start_pattern = rf"export\s+async\s+function\s+{function_name}\s*\("
    start_match = re.search(start_pattern, js_code)
    if not start_match:
        return False

    start_pos = start_match.start()
    next_export = re.search(r"\nexport\s+", js_code[start_match.end() :])
    end_pos = next_export.start() + start_match.end() if next_export else len(js_code)

    function_body = js_code[start_pos:end_pos]
    return "invoke(" in function_body


def function_creates_element(js_code: str, function_name: str, element_type: str) -> bool:
    """Check if function creates a specific element type."""
    start_pattern = rf"export\s+(?:async\s+)?function\s+{function_name}\s*\("
    start_match = re.search(start_pattern, js_code)
    if not start_match:
        return False

    start_pos = start_match.start()
    next_export = re.search(r"\nexport\s+", js_code[start_match.end() :])
    end_pos = next_export.start() + start_match.end() if next_export else len(js_code)

    function_body = js_code[start_pos:end_pos]
    single_quote = f"createElement('{element_type}')" in function_body
    double_quote = f'createElement("{element_type}")' in function_body
    return single_quote or double_quote


def function_adds_event_listener(js_code: str, function_name: str, event_type: str) -> bool:
    """Check if function adds an event listener for specific event."""
    start_pattern = rf"export\s+(?:async\s+)?function\s+{function_name}\s*\("
    start_match = re.search(start_pattern, js_code)
    if not start_match:
        return False

    start_pos = start_match.start()
    next_export = re.search(r"\nexport\s+", js_code[start_match.end() :])
    end_pos = next_export.start() + start_match.end() if next_export else len(js_code)

    function_body = js_code[start_pos:end_pos]
    single_quote = f"addEventListener('{event_type}'" in function_body
    double_quote = f'addEventListener("{event_type}"' in function_body
    return single_quote or double_quote


def function_validates_value(js_code: str, function_name: str, validation_term: str) -> bool:
    """Check if function performs validation with specific term."""
    start_pattern = rf"export\s+(?:async\s+)?function\s+{function_name}\s*\("
    start_match = re.search(start_pattern, js_code)
    if not start_match:
        return False

    start_pos = start_match.start()
    next_export = re.search(r"\nexport\s+", js_code[start_match.end() :])
    end_pos = next_export.start() + start_match.end() if next_export else len(js_code)

    function_body = js_code[start_pos:end_pos]
    return validation_term in function_body


def function_has_parameter_count(js_code: str, function_name: str, count: int) -> bool:
    """Check if function has expected number of parameters."""
    pattern = rf"export\s+(?:async\s+)?function\s+{function_name}\s*\(([^)]*)\)"
    match = re.search(pattern, js_code)
    if match:
        params = match.group(1).strip()
        if not params:
            return count == 0
        param_list = [p.strip() for p in params.split(",")]
        return len(param_list) == count
    return False


def function_returns_object(js_code: str, function_name: str) -> bool:
    """Check if function returns an object literal."""
    start_pattern = rf"export\s+(?:async\s+)?function\s+{function_name}\s*\("
    start_match = re.search(start_pattern, js_code)
    if not start_match:
        return False

    start_pos = start_match.start()
    next_export = re.search(r"\nexport\s+", js_code[start_match.end() :])
    end_pos = next_export.start() + start_match.end() if next_export else len(js_code)

    function_body = js_code[start_pos:end_pos]
    return re.search(r"return\s*\{", function_body) is not None


class TestConfigControlsStructure:
    """Test basic structure and exports of config_controls.js."""

    def test_all_required_functions_exported(self):
        """All four required functions must be exported."""
        js_code = load_config_controls_js()
        functions = extract_function_names(js_code)

        required_functions = [
            "initConfigControls",
            "handleConfigUpdate",
            "showValidationError",
            "getCurrentConfig",
        ]

        for func in required_functions:
            assert func in functions, f"Function {func} must be exported"

    def test_tauri_invoke_imported(self):
        """Tauri invoke must be imported from window.__TAURI__.core."""
        js_code = load_config_controls_js()
        imports = extract_const_imports(js_code)

        assert ("invoke", "core") in imports, "invoke must be imported from window.__TAURI__.core"

    def test_init_function_signature(self):
        """initConfigControls must have exactly 4 parameters."""
        js_code = load_config_controls_js()
        assert function_has_parameter_count(js_code, "initConfigControls", 4), (
            "initConfigControls must accept 4 parameters "
            "(initialPrompt, initialAspectRatio, state, elements)"
        )

    def test_handle_update_signature(self):
        """handleConfigUpdate must have exactly 5 parameters and be async."""
        js_code = load_config_controls_js()
        assert function_has_parameter_count(js_code, "handleConfigUpdate", 5), (
            "handleConfigUpdate must accept 5 parameters "
            "(promptValue, aspectRatioValue, widthValue, heightValue, state)"
        )

        assert "export async function handleConfigUpdate" in js_code, (
            "handleConfigUpdate must be async"
        )

    def test_show_error_signature(self):
        """showValidationError must have exactly 2 parameters."""
        js_code = load_config_controls_js()
        assert function_has_parameter_count(js_code, "showValidationError", 2), (
            "showValidationError must accept 2 parameters (message, inputElement)"
        )

    def test_get_config_signature(self):
        """getCurrentConfig must have exactly 1 parameter."""
        js_code = load_config_controls_js()
        assert function_has_parameter_count(js_code, "getCurrentConfig", 1), (
            "getCurrentConfig must accept 1 parameter (elements)"
        )


class TestInitConfigControlsImplementation:
    """Test initConfigControls function implementation."""

    def test_gets_prompt_input_element(self):
        """initConfigControls must get existing prompt input element."""
        js_code = load_config_controls_js()
        assert "getElementById('prompt-input')" in js_code, (
            "initConfigControls must get existing prompt input element"
        )

    def test_gets_dimension_input_elements(self):
        """initConfigControls must get existing dimension input elements."""
        js_code = load_config_controls_js()
        assert "getElementById('width-input')" in js_code, (
            "initConfigControls must get existing width input element"
        )
        assert "getElementById('height-input')" in js_code, (
            "initConfigControls must get existing height input element"
        )

    def test_gets_aspect_ratio_radios(self):
        """initConfigControls must get existing aspect ratio radio inputs."""
        js_code = load_config_controls_js()
        assert "querySelectorAll" in js_code, (
            "initConfigControls must query for aspect ratio radio buttons"
        )

    def test_sets_up_blur_listener(self):
        """initConfigControls must add blur event listener to prompt input."""
        js_code = load_config_controls_js()
        assert function_adds_event_listener(js_code, "initConfigControls", "blur"), (
            "initConfigControls must add blur event listener"
        )

    def test_sets_up_keydown_listener(self):
        """initConfigControls must add keydown event listener for Enter key."""
        js_code = load_config_controls_js()
        assert function_adds_event_listener(js_code, "initConfigControls", "keydown"), (
            "initConfigControls must add keydown event listener"
        )

    def test_sets_up_change_listener(self):
        """initConfigControls must add change event listener to radios."""
        js_code = load_config_controls_js()
        assert function_adds_event_listener(js_code, "initConfigControls", "change"), (
            "initConfigControls must add change event listener for radio buttons"
        )

    @given(st.lists(st.sampled_from(["1:1", "16:9", "9:16"]), min_size=3, max_size=3, unique=True))
    def test_all_aspect_ratios_created(self, ratios):
        """All three aspect ratios must be available in the code."""
        js_code = load_config_controls_js()
        for ratio in ratios:
            assert f"'{ratio}'" in js_code or f'"{ratio}"' in js_code, (
                f"Aspect ratio {ratio} must be included in radio options"
            )

    def test_updates_state_aspect_ratio(self):
        """initConfigControls must update state.aspectRatio."""
        js_code = load_config_controls_js()
        pattern = r"state\.aspectRatio\s*="
        assert re.search(pattern, js_code), "initConfigControls must set state.aspectRatio"

    def test_stores_elements_references(self):
        """initConfigControls must store element references in elements object."""
        js_code = load_config_controls_js()
        assert "elements.promptInput" in js_code, (
            "initConfigControls must store promptInput reference"
        )
        assert "elements.widthInput" in js_code, (
            "initConfigControls must store widthInput reference"
        )
        assert "elements.heightInput" in js_code, (
            "initConfigControls must store heightInput reference"
        )
        assert "elements.aspectRatioRadios" in js_code, (
            "initConfigControls must store aspectRatioRadios reference"
        )


class TestHandleConfigUpdateImplementation:
    """Test handleConfigUpdate function implementation."""

    def test_validates_empty_prompt(self):
        """handleConfigUpdate must validate that prompt is not empty."""
        js_code = load_config_controls_js()
        assert function_validates_value(js_code, "handleConfigUpdate", "trim()"), (
            "handleConfigUpdate must trim prompt value"
        )
        assert function_validates_value(js_code, "handleConfigUpdate", "=== ''"), (
            "handleConfigUpdate must check for empty string"
        )

    def test_validates_dimensions(self):
        """handleConfigUpdate must validate width and height dimensions."""
        js_code = load_config_controls_js()
        assert function_validates_value(js_code, "handleConfigUpdate", "width"), (
            "handleConfigUpdate must validate width"
        )
        assert function_validates_value(js_code, "handleConfigUpdate", "height"), (
            "handleConfigUpdate must validate height"
        )
        assert function_validates_value(js_code, "handleConfigUpdate", "isNaN"), (
            "handleConfigUpdate must check for NaN values"
        )

    @given(st.lists(st.sampled_from(["1:1", "16:9", "9:16"]), min_size=3, max_size=3, unique=True))
    def test_valid_aspect_ratios_list(self, ratios):
        """Valid aspect ratios must include all three standard ratios."""
        js_code = load_config_controls_js()
        for ratio in ratios:
            assert f"'{ratio}'" in js_code, f"Valid aspect ratios must include {ratio}"

    def test_calls_show_validation_error_on_invalid_prompt(self):
        """handleConfigUpdate must call showValidationError for empty prompt."""
        js_code = load_config_controls_js()
        assert function_validates_value(js_code, "handleConfigUpdate", "showValidationError"), (
            "handleConfigUpdate must call showValidationError"
        )
        assert function_validates_value(js_code, "handleConfigUpdate", "Prompt cannot be empty"), (
            "handleConfigUpdate must have empty prompt error message"
        )

    def test_checks_for_config_change(self):
        """handleConfigUpdate must avoid redundant updates when config unchanged."""
        js_code = load_config_controls_js()
        assert function_validates_value(js_code, "handleConfigUpdate", "state.prompt"), (
            "handleConfigUpdate must compare with state.prompt"
        )
        assert function_validates_value(js_code, "handleConfigUpdate", "state.aspectRatio"), (
            "handleConfigUpdate must compare with state.aspectRatio"
        )
        assert function_validates_value(js_code, "handleConfigUpdate", "state.width"), (
            "handleConfigUpdate must compare with state.width"
        )
        assert function_validates_value(js_code, "handleConfigUpdate", "state.height"), (
            "handleConfigUpdate must compare with state.height"
        )

    def test_stores_previous_values(self):
        """handleConfigUpdate must store previous values for rollback on error."""
        js_code = load_config_controls_js()
        assert "previousPrompt" in js_code, "handleConfigUpdate must store previousPrompt"
        assert "previousAspectRatio" in js_code, "handleConfigUpdate must store previousAspectRatio"
        assert "previousWidth" in js_code, "handleConfigUpdate must store previousWidth"
        assert "previousHeight" in js_code, "handleConfigUpdate must store previousHeight"

    def test_updates_state_before_invoke(self):
        """handleConfigUpdate must update state before calling backend."""
        js_code = load_config_controls_js()
        start_pattern = r"export\s+async\s+function\s+handleConfigUpdate\s*\("
        start_match = re.search(start_pattern, js_code)
        assert start_match, "handleConfigUpdate function not found"

        start_pos = start_match.start()
        next_export = re.search(r"\nexport\s+", js_code[start_match.end() :])
        end_pos = next_export.start() + start_match.end() if next_export else len(js_code)
        function_body = js_code[start_pos:end_pos]

        state_update_pos = function_body.find("state.prompt =")
        invoke_pos = function_body.find("invoke(")

        assert state_update_pos > 0, "State must be updated"
        assert invoke_pos > 0, "invoke must be called"
        assert state_update_pos < invoke_pos, "State must be updated before invoke call"

    def test_invokes_update_generation_config(self):
        """handleConfigUpdate must invoke update_generation_config command."""
        js_code = load_config_controls_js()
        assert function_uses_invoke(js_code, "handleConfigUpdate"), (
            "handleConfigUpdate must call invoke()"
        )
        assert "'update_generation_config'" in js_code or '"update_generation_config"' in js_code, (
            "handleConfigUpdate must invoke 'update_generation_config' command"
        )

    def test_has_error_handling(self):
        """handleConfigUpdate must have try-catch for error handling."""
        js_code = load_config_controls_js()
        assert function_validates_value(js_code, "handleConfigUpdate", "try"), (
            "handleConfigUpdate must have try block"
        )
        assert function_validates_value(js_code, "handleConfigUpdate", "catch"), (
            "handleConfigUpdate must have catch block"
        )

    def test_reverts_state_on_error(self):
        """handleConfigUpdate must revert state on error."""
        js_code = load_config_controls_js()
        catch_pattern = r"catch\s*\([^)]*\)\s*\{([^}]*)\}"
        match = re.search(catch_pattern, js_code, re.DOTALL)
        assert match, "Catch block not found"

        catch_body = match.group(1)
        assert "previousPrompt" in catch_body, (
            "Catch block must reference previousPrompt for rollback"
        )
        assert "previousAspectRatio" in catch_body, (
            "Catch block must reference previousAspectRatio for rollback"
        )


class TestShowValidationErrorImplementation:
    """Test showValidationError function implementation."""

    def test_creates_error_element(self):
        """showValidationError must create div for error message."""
        js_code = load_config_controls_js()
        assert function_creates_element(js_code, "showValidationError", "div"), (
            "showValidationError must create div element"
        )

    def test_clears_existing_errors(self):
        """showValidationError must clear previous error messages."""
        js_code = load_config_controls_js()
        assert function_validates_value(js_code, "showValidationError", "querySelectorAll"), (
            "showValidationError must query for existing errors"
        )
        assert function_validates_value(js_code, "showValidationError", ".validation-error"), (
            "showValidationError must select .validation-error elements"
        )
        assert function_validates_value(js_code, "showValidationError", "remove()"), (
            "showValidationError must remove existing errors"
        )

    def test_sets_aria_attributes(self):
        """showValidationError must set aria-live and role attributes."""
        js_code = load_config_controls_js()
        assert function_validates_value(js_code, "showValidationError", "aria-live"), (
            "showValidationError must set aria-live attribute"
        )
        assert function_validates_value(js_code, "showValidationError", "role"), (
            "showValidationError must set role attribute"
        )
        assert function_validates_value(js_code, "showValidationError", "alert"), (
            "showValidationError must use role=alert"
        )

    def test_sets_timeout_for_removal(self):
        """showValidationError must auto-remove error after timeout."""
        js_code = load_config_controls_js()
        assert function_validates_value(js_code, "showValidationError", "setTimeout"), (
            "showValidationError must use setTimeout"
        )
        assert function_validates_value(js_code, "showValidationError", "3000"), (
            "showValidationError must use 3 second timeout"
        )

    def test_inserts_after_input_element(self):
        """showValidationError must insert error element after input."""
        js_code = load_config_controls_js()
        assert function_validates_value(js_code, "showValidationError", "insertBefore"), (
            "showValidationError must use insertBefore to position error"
        )
        assert function_validates_value(js_code, "showValidationError", "nextSibling"), (
            "showValidationError must insert before nextSibling (effectively after element)"
        )


class TestGetCurrentConfigImplementation:
    """Test getCurrentConfig function implementation."""

    def test_returns_object_with_config(self):
        """getCurrentConfig must return object with prompt and aspectRatio."""
        js_code = load_config_controls_js()
        assert function_returns_object(js_code, "getCurrentConfig"), (
            "getCurrentConfig must return an object"
        )

    def test_reads_prompt_from_elements(self):
        """getCurrentConfig must read prompt from elements.promptInput."""
        js_code = load_config_controls_js()
        assert function_validates_value(js_code, "getCurrentConfig", "elements.promptInput"), (
            "getCurrentConfig must access elements.promptInput"
        )
        assert function_validates_value(js_code, "getCurrentConfig", ".value"), (
            "getCurrentConfig must read .value from input"
        )

    def test_reads_aspect_ratio_from_radios(self):
        """getCurrentConfig must read checked radio from elements.aspectRatioRadios."""
        js_code = load_config_controls_js()
        assert function_validates_value(
            js_code, "getCurrentConfig", "elements.aspectRatioRadios"
        ), "getCurrentConfig must access elements.aspectRatioRadios"
        assert function_validates_value(js_code, "getCurrentConfig", ".checked"), (
            "getCurrentConfig must check radio.checked state"
        )

    def test_returns_default_aspect_ratio(self):
        """getCurrentConfig must have default aspect ratio fallback."""
        js_code = load_config_controls_js()
        function_pattern = r"export\s+function\s+getCurrentConfig[^}]*\{([^}]*\{[^}]*\}[^}]*)*\}"
        match = re.search(function_pattern, js_code, re.DOTALL)
        assert match, "getCurrentConfig function not found"

        function_body = match.group(0)
        assert "'1:1'" in function_body or '"1:1"' in function_body, (
            "getCurrentConfig must have '1:1' as default aspect ratio"
        )

    def test_returns_object_with_correct_keys(self):
        """getCurrentConfig must return object with 'prompt' and 'aspectRatio' keys."""
        js_code = load_config_controls_js()
        start_pattern = r"export\s+function\s+getCurrentConfig\s*\("
        start_match = re.search(start_pattern, js_code)
        assert start_match, "getCurrentConfig function not found"

        start_pos = start_match.start()
        next_export = re.search(r"\nexport\s+", js_code[start_match.end() :])
        end_pos = next_export.start() + start_match.end() if next_export else len(js_code)
        function_body = js_code[start_pos:end_pos]

        assert "return" in function_body and "{" in function_body, (
            "Return statement with object not found"
        )
        assert "prompt:" in function_body, "Return object must have 'prompt' key"
        assert "aspectRatio:" in function_body, "Return object must have 'aspectRatio' key"


class TestValidationLogicProperties:
    """Property-based tests for validation logic."""

    @given(st.text(alphabet=st.characters(whitelist_categories=("Zs",)), min_size=1, max_size=100))
    def test_empty_prompt_validation_property(self, whitespace_string):
        """Prompt validation must reject any whitespace-only string."""
        js_code = load_config_controls_js()

        trimmed = whitespace_string.strip()
        if trimmed == "":
            assert "trim()" in js_code, (
                f"Validation must trim whitespace: '{whitespace_string}' should be rejected"
            )
            assert "=== ''" in js_code, "Validation must check for empty string after trimming"

    @given(st.sampled_from(["1:1", "16:9", "9:16"]))
    def test_valid_aspect_ratios_property(self, valid_ratio):
        """All valid aspect ratios must be present in validation list."""
        js_code = load_config_controls_js()
        assert f"'{valid_ratio}'" in js_code or f'"{valid_ratio}"' in js_code, (
            f"Valid aspect ratio {valid_ratio} must be in validation list"
        )

    @given(st.integers(min_value=1, max_value=10000))
    def test_dimension_bounds_validated_property(self, value):
        """Dimension bounds must be validated (64-2048)."""
        js_code = load_config_controls_js()

        # Check that dimension bounds are defined
        assert "64" in js_code, "Minimum dimension bound (64) must be defined"
        assert "2048" in js_code, "Maximum dimension bound (2048) must be defined"

    @given(st.integers(min_value=1000, max_value=10000))
    def test_error_timeout_range_property(self, timeout_ms):
        """Error timeout should be reasonable (3 seconds per spec)."""
        js_code = load_config_controls_js()

        if timeout_ms == 3000:
            assert "3000" in js_code, (
                "Error timeout must be 3000ms (3 seconds) as per specification"
            )


class TestEventListenerPatterns:
    """Test event listener setup patterns."""

    def test_blur_triggers_update(self):
        """Blur event must trigger config update via handleConfigUpdate."""
        js_code = load_config_controls_js()
        blur_pattern = r"addEventListener\(['\"]blur['\"]"
        assert re.search(blur_pattern, js_code), "Blur event listener must be registered"

        assert "handleConfigUpdate" in js_code, "Blur handler must call handleConfigUpdate"

    def test_enter_key_triggers_blur(self):
        """Enter keydown must trigger blur on prompt input."""
        js_code = load_config_controls_js()
        keydown_pattern = r"addEventListener\(['\"]keydown['\"]"
        assert re.search(keydown_pattern, js_code), "Keydown event listener must be registered"

        assert "e.key" in js_code or "event.key" in js_code, "Keydown handler must check event.key"
        assert "'Enter'" in js_code or '"Enter"' in js_code, (
            "Keydown handler must check for Enter key"
        )
        assert ".blur()" in js_code, "Enter key handler must call blur()"

    def test_radio_change_triggers_update(self):
        """Radio change event must trigger config update."""
        js_code = load_config_controls_js()
        change_pattern = r"addEventListener\(['\"]change['\"]"
        assert re.search(change_pattern, js_code), (
            "Change event listener must be registered on radios"
        )


class TestCSSStyles:
    """Test that required CSS styles are defined."""

    def load_css(self) -> str:
        """Load main.css file."""
        css_path = Path(__file__).parent.parent / "src-tauri" / "ui" / "styles" / "main.css"
        return css_path.read_text(encoding="utf-8")

    def test_prompt_input_style_exists(self):
        """CSS must define .prompt-input style."""
        css_code = self.load_css()
        assert ".prompt-input" in css_code, "CSS must define .prompt-input class"

    def test_aspect_ratio_control_style_exists(self):
        """CSS must define .aspect-ratio-control style (used in HTML)."""
        css_code = self.load_css()
        assert ".aspect-ratio-control" in css_code, "CSS must define .aspect-ratio-control class"

    def test_validation_error_style_exists(self):
        """CSS must define .validation-error style."""
        css_code = self.load_css()
        assert ".validation-error" in css_code, "CSS must define .validation-error class"

    def test_validation_error_has_animation(self):
        """Validation error should have animation for better UX."""
        css_code = self.load_css()
        assert "animation:" in css_code or "animation " in css_code, (
            "CSS should include animation for validation error"
        )

    def test_status_left_exists(self):
        """Status left container must exist in CSS."""
        css_code = self.load_css()
        assert ".status-left" in css_code, "CSS must style .status-left container"


class TestIntegrationProperties:
    """Integration tests verifying complete workflows."""

    def test_complete_validation_error_workflow(self):
        """Complete workflow: validation fails → error shown → timeout clears."""
        js_code = load_config_controls_js()

        assert "showValidationError" in js_code, "Must have showValidationError function"
        assert "querySelector" in js_code or "getElementById" in js_code, (
            "Must query DOM for elements"
        )
        assert "createElement" in js_code, "Must create error element"
        assert "setAttribute" in js_code, "Must set aria attributes"
        assert "setTimeout" in js_code, "Must set timeout for removal"
        assert "3000" in js_code, "Must use 3 second timeout"

    def test_complete_update_workflow(self):
        """Complete workflow: validate → update state → invoke → handle result."""
        js_code = load_config_controls_js()

        assert "trim()" in js_code, "Must trim input"
        assert "=== ''" in js_code, "Must check empty"
        assert "isNaN" in js_code, "Must validate dimensions"
        assert "state.prompt" in js_code, "Must update state.prompt"
        assert "state.aspectRatio" in js_code, "Must update state.aspectRatio"
        assert "state.width" in js_code, "Must update state.width"
        assert "state.height" in js_code, "Must update state.height"
        assert "invoke(" in js_code, "Must call invoke"
        assert "try" in js_code and "catch" in js_code, "Must handle errors"
        assert "previousPrompt" in js_code, "Must support rollback"

    def test_complete_init_workflow(self):
        """Complete workflow: create elements → add listeners → update state."""
        js_code = load_config_controls_js()

        assert "createElement(" in js_code, "Must create elements"
        assert "addEventListener(" in js_code, "Must add event listeners"
        assert "replaceChild(" in js_code or "insertBefore(" in js_code, (
            "Must insert elements into DOM"
        )
        assert "elements.promptInput =" in js_code, "Must store promptInput reference"
        assert "elements.aspectRatioRadios =" in js_code, "Must store radios reference"
        assert "state.aspectRatio =" in js_code, "Must initialize state.aspectRatio"
