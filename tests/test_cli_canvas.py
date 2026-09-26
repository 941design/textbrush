"""Launch canvases reach inference and reference normalization unchanged."""

import threading
from unittest.mock import Mock, patch

import pytest
from PIL import Image

from tests.mocks import MockInferenceEngine
from textbrush.cli import main
from textbrush.inference.flux import FluxInferenceEngine
from textbrush.ipc.handler import MessageHandler
from textbrush.model.registry import AvailabilityReport

CASES = [
    ([], "1:1", (256, 256)),
    (["--aspect-ratio", "16:9"], "16:9", (640, 360)),
    (["--aspect-ratio", "9:16"], "9:16", (360, 640)),
    (["--preset", "portrait-medium"], "3:4", (576, 768)),
]


@pytest.mark.parametrize(
    "model,reference_count",
    [
        ("flux1-schnell", 0),
        ("flux1-kontext-dev", 1),
        ("flux2-klein-4b", 0),
        ("flux2-klein-4b", 2),
    ],
)
@pytest.mark.parametrize("size_args,ratio,canvas", CASES)
@pytest.mark.parametrize("entry", ["headless", "desktop_init"])
def test_launch_canvas_and_normalized_pixels(
    tmp_path, sample_config, model, reference_count, size_args, ratio, canvas, entry
):
    if model == "flux1-schnell" and size_args[:1] == ["--preset"]:
        pytest.skip("Named editing presets require a reference-capable model")
    paths = []
    for i in range(reference_count):
        path = tmp_path / f"ref {i}.png"
        Image.new("RGB", (57, 39), (i * 100, 40, 60)).save(path)
        paths.append(path)
    # Exercise production reference sizing (including FLUX's multiple-of-16
    # rounding), without importing model dependencies or loading weights.
    sizing = FluxInferenceEngine(model)
    engine = MockInferenceEngine(reference_canvas=sizing.reference_input_size)
    engine.model_id = model
    generated = threading.Event()
    seen = []
    original_generate = engine.generate

    def generate(prompt, options):
        seen.append(
            (
                options.width,
                options.height,
                options.aspect_ratio,
                [ref.pixel_data.size for ref in options.references],
            )
        )
        result = original_generate(prompt, options)
        generated.set()
        return result

    engine.generate = generate
    sample_config.editing.default_preset = "landscape-large"
    handler = None
    with (
        patch("textbrush.cli.load_config", return_value=sample_config),
        patch(
            "textbrush.cli.check_model_availability", return_value=AvailabilityReport(True, None)
        ),
        patch("textbrush.backend.create_engine", return_value=engine),
        patch(
            "textbrush.ipc.handler.check_model_availability",
            return_value=AvailabilityReport(True, None),
        ),
    ):
        try:
            if entry == "headless":
                argv = [
                    "--headless",
                    "--prompt",
                    "canvas",
                    "--model",
                    model,
                    "--out",
                    str(tmp_path / "out.png"),
                    *size_args,
                ]
                for path in paths:
                    argv.extend(["--reference", str(path)])
                with pytest.raises(SystemExit) as result:
                    main(argv)
                assert result.value.code == 0
            else:
                # Native parsing and frontend serialization have separate Rust/JS
                # coverage. Exercise their resulting INIT payload through the real
                # backend, normalizer, worker and inference-options boundary.
                handler = MessageHandler(sample_config)
                handler._start_image_delivery = Mock()
                parked = threading.Event()
                server = Mock()
                server.send.side_effect = lambda msg: (
                    parked.set() if msg.payload.get("state") == "paused" else None
                )
                handler.handle_init(
                    {
                        "prompt": "canvas",
                        "model_id": model,
                        "seed": 0,
                        "references": [str(p) for p in paths],
                        "preset": size_args[1] if size_args[:1] == ["--preset"] else None,
                        "aspect_ratio": ratio,
                        "width": canvas[0],
                        "height": canvas[1],
                    },
                    server,
                )
                assert parked.wait(3), "desktop INIT never reached paused state"
                handler.handle_pause(server)
                assert generated.wait(3), "desktop INIT never reached inference"
            assert seen
            expected_ref = sizing.reference_input_size(*canvas)
            assert seen[0] == (*canvas, ratio, [expected_ref] * reference_count)
        finally:
            if handler:
                handler.shutdown()


@pytest.mark.parametrize("headless", [False, True])
def test_conflicting_size_options_fail_before_dispatch(headless):
    with (
        patch("textbrush.backend.create_engine") as engine,
        patch("textbrush.desktop.run_desktop") as desktop,
        pytest.raises(SystemExit) as result,
    ):
        main(
            ["--prompt", "test", "--preset", "portrait-medium", "--aspect-ratio", "16:9"]
            + (["--headless"] if headless else [])
        )
    assert result.value.code == 2
    engine.assert_not_called()
    desktop.assert_not_called()
