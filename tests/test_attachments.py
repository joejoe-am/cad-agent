import base64
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from cad_agent.application import attachments as a
from cad_agent.application import workflow as w
from cad_agent.domain.inputs import VisualInput
from cad_agent.integrations.media import normalize_image, sample_video
from cad_agent.integrations.providers.adapters import APIProvider, ProviderConfig, ProviderError
from cad_agent.integrations.solidworks import open_part_copy


class AttachmentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "providers.toml").write_text(
            'default_provider="codex"\n[providers.codex]\nmode="workspace"'
        )
        self.job = w.create_job(self.root, "Model with reference inputs")
        self.picture = self.root / "reference.PNG"
        Image.new("RGBA", (2000, 1000), (200, 100, 50, 100)).save(self.picture)

    def test_image_is_copied_normalized_and_routed_to_codex(self):
        data = a.add_attachments(self.job, [self.picture])
        item = data.attachments[0]
        self.assertEqual(item.kind, "image")
        self.assertEqual(item.metadata["prepared_size"], [1536, 768])
        local = a.contained(self.job, item.images[0].path)
        with Image.open(local) as image:
            self.assertEqual(image.mode, "RGB")
        self.picture.unlink()
        text = w.generate(self.root, self.job).read_text()
        self.assertIn(str(local), text)
        self.assertIn("image viewing tool", text)
        self.assertEqual(a.verify(self.job).attachments[0].sha256, item.sha256)

    def test_text_contents_in_prompt(self):
        source = self.root / "dimensions.txt"
        source.write_text("width=100 mm; height=80 mm", encoding="utf-8")
        a.add_attachments(self.job, [source])
        self.assertIn("width=100 mm", w.generate(self.root, self.job).read_text())

    def test_duplicate_names_have_separate_snapshots(self):
        one = self.root / "one"
        two = self.root / "two"
        one.mkdir()
        two.mkdir()
        (one / "spec.txt").write_text("first")
        (two / "spec.txt").write_text("second")
        data = a.add_attachments(self.job, [one / "spec.txt", two / "spec.txt"])
        self.assertNotEqual(data.attachments[0].path, data.attachments[1].path)

    def test_bad_image_rolls_back_batch_without_losing_previous_manifest(self):
        a.add_attachments(self.job, [self.picture])
        before = (self.job / "attachments.json").read_bytes()
        existing = set((self.job / "inputs").iterdir())
        invalid = self.root / "broken.png"
        invalid.write_bytes(b"not an image")
        with self.assertRaises(OSError):
            a.add_attachments(self.job, [self.picture, invalid])
        self.assertEqual((self.job / "attachments.json").read_bytes(), before)
        self.assertEqual(set((self.job / "inputs").iterdir()), existing)

    def test_corrupt_prepared_image_blocks_generation_before_attempt(self):
        item = a.add_attachments(self.job, [self.picture]).attachments[0]
        a.contained(self.job, item.images[0].path).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "Prepared image changed"):
            w.generate(self.root, self.job)
        self.assertEqual(w.read_json(self.job / "job.json")["attempt"], 0)

    def test_input_mutation_blocks_execution(self):
        item = a.add_attachments(self.job, [self.picture]).attachments[0]
        w.generate(self.root, self.job)
        w.write_json(self.job / "attempt-1/response.json", dict(summary="fixture", code="print('ok')"))
        w.accept(self.job)
        a.contained(self.job, item.path).write_bytes(b"changed")
        with patch.object(w, "run_trusted_script") as runner, self.assertRaises(ValueError):
            w.execute(self.job, reviewed=True)
        runner.assert_not_called()

    def test_deleted_manifest_does_not_silently_drop_job_references(self):
        a.add_attachments(self.job, [self.picture])
        w.generate(self.root, self.job)
        w.write_json(self.job / "attempt-1/response.json", dict(summary="fixture", code="pass"))
        (self.job / "attachments.json").unlink()
        with self.assertRaisesRegex(ValueError, "manifest changed"):
            w.accept(self.job)

    def test_input_corruption_during_execution_is_reported_as_failure(self):
        item = a.add_attachments(self.job, [self.picture]).attachments[0]
        w.generate(self.root, self.job)
        w.write_json(self.job / "attempt-1/response.json", dict(summary="fixture", code="pass"))
        w.accept(self.job)

        def mutate(*args, **kwargs):
            a.contained(self.job, item.path).write_bytes(b"changed")
            return subprocess.CompletedProcess([], 0, "", "")

        with patch.object(w, "run_trusted_script", side_effect=mutate):
            report = w.execute(self.job, reviewed=True)
        self.assertEqual(report["returncode"], 1)
        self.assertIn("integrity check failed", report["stderr"])
        self.assertEqual(w.read_json(self.job / "job.json")["state"], "execution_failed")

    def test_manifest_path_escape_rejected(self):
        a.add_attachments(self.job, [self.picture])
        data = w.read_json(self.job / "attachments.json")
        data["attachments"][0]["path"] = str(self.picture)
        w.write_json(self.job / "attachments.json", data)
        with self.assertRaises(ValueError):
            a.verify(self.job)

    def test_cad_input_is_local_with_copy_editing_instructions(self):
        model = self.root / "part.SLDPRT"
        model.write_bytes(bytes.fromhex("d0cf11e0a1b11ae1") + b"fixture, not a live CAD file")
        a.add_attachments(self.job, [model])
        text, visuals = a.context(self.job)
        self.assertIn("open_part_copy", text)
        self.assertIn("have not seen its geometry", text)
        self.assertEqual(visuals, [])

    def test_assembly_requires_dependency_packaging(self):
        assembly = self.root / "part.SLDASM"
        assembly.write_bytes(b"fixture")
        with self.assertRaisesRegex(ValueError, "dependency packaging"):
            a.add_attachments(self.job, [assembly])

    def test_invalid_native_part_rejected(self):
        model = self.root / "part.SLDPRT"
        model.write_bytes(b"not a native part")
        with self.assertRaisesRegex(ValueError, "native SolidWorks part header"):
            a.add_attachments(self.job, [model])

    def test_compressed_solidworks_storage_supported(self):
        model = self.root / "part.SLDPRT"
        model.write_bytes(bytes.fromhex("fc0ddf8800000004") + b"compressed storage fixture")
        self.assertEqual(a.add_attachments(self.job, [model]).attachments[0].kind, "cad")

    def test_attach_after_generation_rejected(self):
        w.generate(self.root, self.job)
        with self.assertRaisesRegex(ValueError, "before generation"):
            a.add_attachments(self.job, [self.picture])

    def test_provider_receives_visual_input(self):
        (self.root / "providers.toml").write_text(
            'default_provider="openai"\n[providers.openai]\nmodel="fixture"\nsupports_images=true\n'
        )
        other = w.create_job(self.root, "Use photo", attachments=[self.picture])
        with patch.object(
            w.APIProvider, "generate", return_value=w.GeneratedCode(summary="fixture", code="pass")
        ) as gen:
            w.generate(self.root, other)
        self.assertEqual(len(gen.call_args.kwargs["images"]), 1)

    def test_unsupported_vision_configuration_does_not_consume_attempt(self):
        (self.root / "providers.toml").write_text(
            'default_provider="openai"\n[providers.openai]\nmodel="fixture"\n'
        )
        other = w.create_job(self.root, "Use photo", attachments=[self.picture])
        with self.assertRaisesRegex(ValueError, "supports_images"):
            w.generate(self.root, other)
        self.assertEqual(w.read_json(other / "job.json")["attempt"], 0)


class VisualProviderTests(unittest.TestCase):
    def test_all_provider_payloads_include_label_and_actual_image_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            image = Path(temporary) / "reference.jpg"
            image.write_bytes(b"fixture image bytes")
            encoded = base64.b64encode(image.read_bytes()).decode("ascii")
            result = json.dumps(dict(summary="fixture", code="pass"))
            responses = {
                "openai": dict(
                    status="completed",
                    output=[dict(type="message", content=[dict(type="output_text", text=result)])],
                ),
                "anthropic": dict(stop_reason="end_turn", content=[dict(type="text", text=result)]),
                "openrouter": dict(choices=[dict(finish_reason="stop", message=dict(content=result))]),
            }
            for name, response in responses.items():
                with self.subTest(provider=name), patch.dict("os.environ", {"FIXTURE_KEY": "fake"}):
                    calls = []

                    def transport(*args):
                        calls.append(args)
                        return response

                    provider = APIProvider(
                        name,
                        ProviderConfig(model="fixture", api_key_env="FIXTURE_KEY", supports_images=True),
                        transport,
                    )
                    provider.generate(
                        "system", "task", images=[VisualInput(path=image, label="Video near 2 seconds")]
                    )
                    payload = calls[0][2]
                    content = (
                        payload["input"][0]["content"]
                        if name == "openai"
                        else payload["messages"][-1]["content"]
                    )
                    self.assertIn("Video near 2 seconds", json.dumps(content))
                    if name == "anthropic":
                        self.assertEqual(content[-1]["source"]["data"], encoded)
                        self.assertEqual(content[-1]["source"]["media_type"], "image/jpeg")
                    elif name == "openai":
                        self.assertEqual(content[-1]["type"], "input_image")
                        self.assertTrue(content[-1]["image_url"].endswith(encoded))
                    else:
                        self.assertEqual(content[-1]["type"], "image_url")
                        self.assertTrue(content[-1]["image_url"]["url"].endswith(encoded))

    def test_images_never_silently_dropped_for_text_only_model(self):
        provider = APIProvider("openai", ProviderConfig(), lambda *args: self.fail("Network called"))
        with self.assertRaisesRegex(ProviderError, "supports_images"):
            provider.generate(
                "system", "task", images=[VisualInput(path=Path("unread.jpg"), label="fixture")]
            )


class MediaTests(unittest.TestCase):
    def test_missing_ffmpeg_explains_video_requirement(self):
        with patch("cad_agent.integrations.media.shutil.which", return_value=None):
            with self.assertRaisesRegex(ValueError, "requires FFmpeg"):
                sample_video(Path("fixture.mp4"), Path("unused"))

    def test_video_samples_are_labelled_across_duration(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            calls = []

            def run(args, **kwargs):
                calls.append(args)
                if "-frames:v" not in args:
                    return subprocess.CompletedProcess(args, 1, "", "Duration: 00:00:08.00")
                Image.new("RGB", (80, 40), "green").save(args[-1])
                return subprocess.CompletedProcess(args, 0, "", "")

            with (
                patch("cad_agent.integrations.media.shutil.which", return_value="ffmpeg"),
                patch("cad_agent.integrations.media.subprocess.run", side_effect=run),
            ):
                frames, meta = sample_video(folder / "clip.mp4", folder, count=2)
            self.assertEqual([t for _, t in frames], [2.0, 6.0])
            self.assertFalse(meta["audio_analyzed"])
            self.assertEqual(len(calls), 3)

    def test_corrupt_video_fails_instead_of_claiming_understanding(self):
        with (
            patch("cad_agent.integrations.media.shutil.which", return_value="ffmpeg"),
            patch(
                "cad_agent.integrations.media.subprocess.run",
                return_value=subprocess.CompletedProcess([], 1, "", "Invalid data"),
            ),
        ):
            with self.assertRaisesRegex(ValueError, "duration"):
                sample_video(Path("invalid.mp4"), Path("unused"))

    def test_animation_is_not_silently_reduced_to_one_image(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "animated.png"
            one = Image.new("RGB", (20, 20), "red")
            two = Image.new("RGB", (20, 20), "blue")
            one.save(path, save_all=True, append_images=[two], duration=100, loop=0)
            with self.assertRaisesRegex(ValueError, "Animated images"):
                normalize_image(path, path.with_suffix(".jpg"))


@unittest.skipUnless(sys.platform == "win32", "SolidWorks COM uses Windows variants")
class PartCopyTests(unittest.TestCase):
    def test_edits_open_unique_copy_and_preserve_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.SLDPRT"
            source.write_bytes(b"fixture source bytes")
            output = root / "attempt-1"
            output.mkdir()
            opened = []

            def open_doc(path, *args):
                opened.append(Path(path))
                return SimpleNamespace(GetPathName=path)

            app = SimpleNamespace(OpenDoc6=open_doc)
            document = open_part_copy(source, output, app=app)
            self.assertEqual(source.read_bytes(), b"fixture source bytes")
            self.assertEqual(opened[0].parent, output)
            self.assertNotEqual(opened[0], source)
            self.assertEqual(Path(document.GetPathName), opened[0])
            open_part_copy(source, output, app=app)
            self.assertNotEqual(opened[0], opened[1])

    def test_same_directory_cannot_be_used_for_editable_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.SLDPRT"
            source.write_bytes(b"fixture")
            with self.assertRaises(ValueError):
                open_part_copy(source, root, app=object())
