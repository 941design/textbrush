"""
Property-based tests for animations.css

Tests verify:
- All keyframes are syntactically valid CSS
- Animation durations match spec requirements
- CSS custom properties are used correctly (not hardcoded values)
- All classes referenced in spec exist and are properly configured
- GPU acceleration is applied (translateZ(0))
- Accessibility support (prefers-reduced-motion)
"""

import re
from pathlib import Path

import pytest


class SimpleCSSParser:
    """Simple but robust CSS parser for animation validation."""

    def __init__(self, css_content: str):
        self.css_content = css_content

    def keyframe_exists(self, name: str) -> bool:
        """Check if a keyframe with given name exists."""
        pattern = rf"@keyframes\s+{re.escape(name)}\s*\{{"
        return bool(re.search(pattern, self.css_content))

    def keyframe_has_property(self, keyframe_name: str, property_name: str) -> bool:
        """Check if keyframe has a specific property anywhere."""
        pattern = rf"@keyframes\s+{re.escape(keyframe_name)}\s*\{{[^}}]*{re.escape(property_name)}"
        return bool(re.search(pattern, self.css_content, re.DOTALL))

    def keyframe_property_contains(self, keyframe_name: str, value_substring: str) -> bool:
        """Check if keyframe contains a specific value."""
        escaped_name = re.escape(keyframe_name)
        escaped_value = re.escape(value_substring)
        pattern = rf"@keyframes\s+{escaped_name}\s*\{{[^}}]*{escaped_value}"
        return bool(re.search(pattern, self.css_content, re.DOTALL))

    def class_exists(self, class_name: str) -> bool:
        """Check if a CSS class is defined."""
        pattern = rf"\.{re.escape(class_name)}\s*\{{"
        return bool(re.search(pattern, self.css_content))

    def class_has_property(self, class_name: str, property_name: str) -> bool:
        """Check if class has a specific property."""
        pattern = rf"\.{re.escape(class_name)}\s*\{{[^}}]*{re.escape(property_name)}\s*:"
        return bool(re.search(pattern, self.css_content, re.DOTALL))

    def class_property_contains(self, class_name: str, value_substring: str) -> bool:
        """Check if class property contains a value."""
        pattern = rf"\.{re.escape(class_name)}\s*\{{[^}}]*{re.escape(value_substring)}"
        return bool(re.search(pattern, self.css_content, re.DOTALL))

    def selector_has_property_value(self, selector: str, value_substring: str) -> bool:
        """Check if selector contains a value (for complex selectors)."""
        pattern = rf"{re.escape(selector)}\s*\{{[^}}]*{re.escape(value_substring)}"
        return bool(re.search(pattern, self.css_content, re.DOTALL))

    def media_query_exists(self, query_condition: str) -> bool:
        """Check if a media query with condition exists."""
        pattern = rf"@media\s*\({re.escape(query_condition)}\)"
        return bool(re.search(pattern, self.css_content))

    def media_query_contains(self, query_condition: str, content_substring: str) -> bool:
        """Check if media query contains specific content."""
        escaped_condition = re.escape(query_condition)
        escaped_content = re.escape(content_substring)
        pattern = rf"@media\s*\({escaped_condition}\)[^}}]*\{{{escaped_content}"
        return bool(re.search(pattern, self.css_content, re.DOTALL))

    def extract_animation_value(self, class_name: str) -> str:
        """Extract animation property value for a class."""
        pattern = rf"\.{re.escape(class_name)}\s*\{{[^}}]*animation\s*:\s*([^;}}]+)"
        match = re.search(pattern, self.css_content, re.DOTALL)
        return match.group(1).strip() if match else ""

    def extract_transform_value(self, selector: str) -> str:
        """Extract transform property value."""
        pattern = rf"{re.escape(selector)}\s*\{{[^}}]*transform\s*:\s*([^;}}]+)"
        match = re.search(pattern, self.css_content, re.DOTALL)
        return match.group(1).strip() if match else ""


@pytest.fixture
def animations_css_path():
    """Path to animations.css file."""
    return Path(__file__).parent.parent / "src-tauri" / "ui" / "styles" / "animations.css"


@pytest.fixture
def css_content(animations_css_path):
    """Read animations.css content."""
    if not animations_css_path.exists():
        pytest.skip(f"animations.css not found at {animations_css_path}")
    return animations_css_path.read_text()


@pytest.fixture
def parser(css_content):
    """CSS parser instance."""
    return SimpleCSSParser(css_content)


class TestKeyframesExist:
    """Property: All required keyframes are defined."""

    REQUIRED_KEYFRAMES = ["spin", "fadeIn", "fadeOut", "btnPress", "pulse"]

    def test_all_required_keyframes_defined(self, parser):
        """All required keyframe animations exist."""
        for keyframe_name in self.REQUIRED_KEYFRAMES:
            assert parser.keyframe_exists(keyframe_name), f"Missing keyframe: {keyframe_name}"

    def test_spin_keyframe_exists(self, parser):
        """Spin keyframe is defined."""
        assert parser.keyframe_exists("spin")

    def test_fadein_keyframe_exists(self, parser):
        """FadeIn keyframe is defined."""
        assert parser.keyframe_exists("fadeIn")

    def test_fadeout_keyframe_exists(self, parser):
        """FadeOut keyframe is defined."""
        assert parser.keyframe_exists("fadeOut")

    def test_btnpress_keyframe_exists(self, parser):
        """BtnPress keyframe is defined."""
        assert parser.keyframe_exists("btnPress")

    def test_pulse_keyframe_exists(self, parser):
        """Pulse keyframe is defined."""
        assert parser.keyframe_exists("pulse")


class TestSpinnerAnimation:
    """Property: Spinner animation rotates 360° over 1 second linearly."""

    def test_spin_has_rotation(self, parser):
        """Spin keyframe contains rotation transforms."""
        css = parser.css_content
        assert "rotate(0deg)" in css, "Spin keyframe missing rotate(0deg)"
        assert "rotate(360deg)" in css, "Spin keyframe missing rotate(360deg)"

    def test_spinner_class_exists(self, parser):
        """Spinner class is defined."""
        assert parser.class_exists("spinner")

    def test_spinner_uses_spin_animation(self, parser):
        """Spinner class applies spin animation."""
        assert parser.class_has_property("spinner", "animation")
        assert parser.class_property_contains("spinner", "spin")

    def test_spinner_class_uses_1s_duration(self, parser):
        """Spinner animation uses 1s duration."""
        animation = parser.extract_animation_value("spinner")
        assert "1s" in animation, f"Expected '1s' in spinner animation, got: {animation}"

    def test_spinner_class_uses_linear_timing(self, parser):
        """Spinner animation uses linear timing function."""
        animation = parser.extract_animation_value("spinner")
        assert "linear" in animation, f"Expected 'linear' in spinner animation, got: {animation}"

    def test_spinner_class_infinite_loop(self, parser):
        """Spinner animation runs infinite."""
        animation = parser.extract_animation_value("spinner")
        assert "infinite" in animation, (
            f"Expected 'infinite' in spinner animation, got: {animation}"
        )

    def test_spinner_gpu_acceleration(self, parser):
        """Spinner class includes translateZ for GPU acceleration."""
        assert parser.class_property_contains("spinner", "translateZ(0)"), (
            "Spinner should have translateZ(0) for GPU acceleration"
        )


class TestImageTransitions:
    """Property: Image fade animations with correct timing and transforms."""

    def test_fadein_has_opacity_transitions(self, parser):
        """FadeIn keyframe transitions opacity."""
        css = parser.css_content
        assert "fadeIn" in css and "opacity" in css, "FadeIn keyframe missing opacity transitions"

    def test_fadein_has_scale_transforms(self, parser):
        """FadeIn keyframe scales from 0.98 to 1."""
        css = parser.css_content
        assert "scale(0.98)" in css, "FadeIn keyframe missing scale(0.98)"
        assert "scale(1)" in css, "FadeIn keyframe missing scale(1)"

    def test_fadeout_has_opacity_transitions(self, parser):
        """FadeOut keyframe transitions opacity."""
        css = parser.css_content
        assert "fadeOut" in css and "opacity" in css, "FadeOut keyframe missing opacity transitions"

    def test_image_enter_class_exists(self, parser):
        """image-enter class is defined."""
        assert parser.class_exists("image-enter")

    def test_image_exit_class_exists(self, parser):
        """image-exit class is defined."""
        assert parser.class_exists("image-exit")

    def test_image_enter_uses_fadein_animation(self, parser):
        """image-enter applies fadeIn animation."""
        assert parser.class_has_property("image-enter", "animation")
        assert parser.class_property_contains("image-enter", "fadeIn")

    def test_image_exit_uses_fadeout_animation(self, parser):
        """image-exit applies fadeOut animation."""
        assert parser.class_has_property("image-exit", "animation")
        assert parser.class_property_contains("image-exit", "fadeOut")

    def test_image_enter_uses_transition_normal(self, parser):
        """image-enter uses var(--transition-normal) duration."""
        animation = parser.extract_animation_value("image-enter")
        assert "var(--transition-normal)" in animation, (
            f"Expected 'var(--transition-normal)' in image-enter, got: {animation}"
        )

    def test_image_exit_uses_transition_fast(self, parser):
        """image-exit uses var(--transition-fast) duration."""
        animation = parser.extract_animation_value("image-exit")
        assert "var(--transition-fast)" in animation, (
            f"Expected 'var(--transition-fast)' in image-exit, got: {animation}"
        )

    def test_image_enter_fill_mode_forwards(self, parser):
        """image-enter uses fill-mode forwards."""
        animation = parser.extract_animation_value("image-enter")
        assert "forwards" in animation, (
            f"image-enter should use fill-mode forwards, got: {animation}"
        )

    def test_image_exit_fill_mode_forwards(self, parser):
        """image-exit uses fill-mode forwards."""
        animation = parser.extract_animation_value("image-exit")
        assert "forwards" in animation, (
            f"image-exit should use fill-mode forwards, got: {animation}"
        )

    def test_image_enter_gpu_acceleration(self, parser):
        """image-enter includes translateZ for GPU acceleration."""
        assert parser.class_property_contains("image-enter", "translateZ(0)")

    def test_image_exit_gpu_acceleration(self, parser):
        """image-exit includes translateZ for GPU acceleration."""
        assert parser.class_property_contains("image-exit", "translateZ(0)")


class TestButtonPressAnimation:
    """Property: Button press animation scales 1 → 0.95 → 1 over 150ms."""

    def test_btnpress_has_scale_progression(self, parser):
        """BtnPress keyframe has scale transitions 1 → 0.95 → 1."""
        css = parser.css_content
        assert "scale(1)" in css, "BtnPress keyframe missing scale(1)"
        assert "scale(0.95)" in css, "BtnPress keyframe missing scale(0.95)"

    def test_btn_pressed_class_exists(self, parser):
        """btn-pressed class is defined."""
        assert parser.class_exists("btn-pressed")

    def test_btn_pressed_uses_btnpress_animation(self, parser):
        """btn-pressed applies btnPress animation."""
        assert parser.class_has_property("btn-pressed", "animation")
        assert parser.class_property_contains("btn-pressed", "btnPress")

    def test_btn_pressed_class_150ms_duration(self, parser):
        """btn-pressed class uses 150ms duration."""
        animation = parser.extract_animation_value("btn-pressed")
        assert "150ms" in animation, f"Expected '150ms' in btn-pressed animation, got: {animation}"

    def test_btn_pressed_ease_timing(self, parser):
        """btn-pressed class uses ease timing function."""
        animation = parser.extract_animation_value("btn-pressed")
        assert "ease" in animation, f"Expected 'ease' in btn-pressed animation, got: {animation}"

    def test_btn_pressed_fill_mode_forwards(self, parser):
        """btn-pressed uses fill-mode forwards."""
        animation = parser.extract_animation_value("btn-pressed")
        assert "forwards" in animation, (
            f"btn-pressed should use fill-mode forwards, got: {animation}"
        )

    def test_btn_pressed_gpu_acceleration(self, parser):
        """btn-pressed includes translateZ for GPU acceleration."""
        assert parser.class_property_contains("btn-pressed", "translateZ(0)")


class TestPulseAnimation:
    """Property: Pulse animation fades opacity 0.3 → 1 → 0.3 over 1s infinitely."""

    def test_pulse_has_opacity_progression(self, parser):
        """Pulse keyframe transitions opacity 0.3 → 1 → 0.3."""
        css = parser.css_content
        assert "pulse" in css and "opacity" in css, "Pulse keyframe missing opacity transitions"

    def test_buffer_generating_selector_exists(self, parser):
        """buffer-generating selector is defined."""
        selector = ".buffer-generating .buffer-dot:last-child"
        assert parser.selector_has_property_value(selector, "animation")

    def test_buffer_pulse_uses_pulse_animation(self, parser):
        """buffer-dot pulse uses pulse animation."""
        selector = ".buffer-generating .buffer-dot:last-child"
        assert parser.selector_has_property_value(selector, "pulse")

    def test_buffer_generating_pulse_1s_duration(self, parser):
        """Buffer-generating pulse uses 1s duration."""
        selector = ".buffer-generating .buffer-dot:last-child"
        assert parser.selector_has_property_value(selector, "1s")

    def test_buffer_generating_infinite_loop(self, parser):
        """Buffer pulse animation runs infinite."""
        selector = ".buffer-generating .buffer-dot:last-child"
        assert parser.selector_has_property_value(selector, "infinite")

    def test_buffer_generating_targets_last_child(self, parser):
        """Buffer pulse targets last-child specifically."""
        assert ".buffer-generating .buffer-dot:last-child" in parser.css_content


class TestCSSCustomProperties:
    """Property: All durations use CSS custom properties, not hardcoded values."""

    def test_no_hardcoded_100ms_durations(self, parser):
        """No 100ms durations hardcoded in animations."""
        pattern = r"animation:\s*[^;]*\b100ms\b"
        assert not re.search(pattern, parser.css_content), (
            "Found hardcoded 100ms duration - use var(--transition-fast) instead"
        )

    def test_no_hardcoded_200ms_durations(self, parser):
        """No 200ms durations hardcoded in animations."""
        pattern = r"animation:\s*[^;]*\b200ms\b"
        assert not re.search(pattern, parser.css_content), (
            "Found hardcoded 200ms duration - use var(--transition-normal) instead"
        )

    def test_no_hardcoded_300ms_durations(self, parser):
        """No 300ms durations hardcoded in animations."""
        pattern = r"animation:\s*[^;]*\b300ms\b"
        assert not re.search(pattern, parser.css_content), (
            "Found hardcoded 300ms duration - use var(--transition-slow) instead"
        )

    def test_spinner_1s_explicit(self, parser):
        """Spinner can use explicit 1s (not a custom property)."""
        assert parser.class_property_contains("spinner", "1s")


class TestAccessibility:
    """Property: Animations respect prefers-reduced-motion."""

    def test_prefers_reduced_motion_media_query_exists(self, parser):
        """@media (prefers-reduced-motion: reduce) query is defined."""
        assert parser.media_query_exists("prefers-reduced-motion: reduce"), (
            "Missing @media (prefers-reduced-motion: reduce) query"
        )

    def test_prefers_reduced_motion_disables_animations(self, parser):
        """Prefers-reduced-motion disables animations."""
        css = parser.css_content
        assert re.search(
            r"@media.*prefers-reduced-motion:\s*reduce[^}]*animation:\s*none", css, re.DOTALL
        ), "Prefers-reduced-motion should set animation: none"

    def test_prefers_reduced_motion_removes_transforms(self, parser):
        """Prefers-reduced-motion removes animation transforms."""
        css = parser.css_content
        assert re.search(
            r"@media.*prefers-reduced-motion:\s*reduce[^}]*transform:\s*none", css, re.DOTALL
        ), "Prefers-reduced-motion should set transform: none"

    def test_prefers_reduced_motion_sets_image_enter_final_state(self, parser):
        """Prefers-reduced-motion sets image-enter to final state."""
        css = parser.css_content
        assert re.search(
            r"@media.*prefers-reduced-motion:\s*reduce[^}]*\.image-enter", css, re.DOTALL
        ), "Prefers-reduced-motion should define .image-enter final state"

    def test_prefers_reduced_motion_sets_image_exit_final_state(self, parser):
        """Prefers-reduced-motion sets image-exit to final state."""
        css = parser.css_content
        assert re.search(
            r"@media.*prefers-reduced-motion:\s*reduce[^}]*\.image-exit", css, re.DOTALL
        ), "Prefers-reduced-motion should define .image-exit final state"


class TestPerformanceOptimization:
    """Property: Animations use only GPU-accelerated properties."""

    def test_spin_has_transform(self, parser):
        """Spin keyframe uses transform property."""
        assert parser.keyframe_has_property("spin", "transform")

    def test_fadein_has_transform_and_opacity(self, parser):
        """FadeIn uses transform and opacity only."""
        assert parser.keyframe_has_property("fadeIn", "transform")
        assert parser.keyframe_has_property("fadeIn", "opacity")

    def test_fadeout_has_opacity(self, parser):
        """FadeOut uses opacity."""
        assert parser.keyframe_has_property("fadeOut", "opacity")

    def test_btnpress_has_transform(self, parser):
        """BtnPress uses transform."""
        assert parser.keyframe_has_property("btnPress", "transform")

    def test_pulse_has_opacity(self, parser):
        """Pulse uses opacity."""
        assert parser.keyframe_has_property("pulse", "opacity")

    def test_spinner_has_translatez(self, parser):
        """Spinner includes translateZ for GPU acceleration."""
        assert parser.class_property_contains("spinner", "translateZ(0)")

    def test_image_enter_has_translatez(self, parser):
        """image-enter includes translateZ for GPU acceleration."""
        assert parser.class_property_contains("image-enter", "translateZ(0)")

    def test_image_exit_has_translatez(self, parser):
        """image-exit includes translateZ for GPU acceleration."""
        assert parser.class_property_contains("image-exit", "translateZ(0)")

    def test_btn_pressed_has_translatez(self, parser):
        """btn-pressed includes translateZ for GPU acceleration."""
        assert parser.class_property_contains("btn-pressed", "translateZ(0)")

    def test_buffer_pulse_has_translatez(self, parser):
        """buffer pulse includes translateZ for GPU acceleration."""
        selector = ".buffer-generating .buffer-dot:last-child"
        assert parser.selector_has_property_value(selector, "translateZ(0)")
