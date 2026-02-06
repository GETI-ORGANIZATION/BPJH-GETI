"""Tests for EvoScientist/tools.py — only non-API tools."""

from EvoScientist.tools import think_tool, view_image
from EvoScientist.paths import set_active_workspace


class TestThinkTool:
    def test_returns_confirmation(self):
        result = think_tool.invoke({"reflection": "I need more data on topic X"})
        assert isinstance(result, str)
        assert "I need more data on topic X" in result

    def test_reflection_recorded(self):
        result = think_tool.invoke({"reflection": "gap analysis"})
        assert "Reflection recorded" in result

    def test_empty_reflection(self):
        result = think_tool.invoke({"reflection": ""})
        assert "Reflection recorded" in result


class TestViewImage:
    def test_file_not_found(self):
        result = view_image.invoke({"image_path": "/nonexistent/image.png"})
        assert isinstance(result, str)
        assert "not found" in result.lower()

    def test_unsupported_format(self, tmp_path):
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("not an image")
        result = view_image.invoke({"image_path": str(txt_file)})
        assert isinstance(result, str)
        assert "not a supported image" in result.lower()

    def test_valid_png(self, tmp_path):
        # Minimal 1x1 red PNG (67 bytes)
        import base64
        png_b64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
            "2mP8z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="
        )
        png_data = base64.b64decode(png_b64)
        img = tmp_path / "test.png"
        img.write_bytes(png_data)

        result = view_image.invoke({"image_path": str(img)})
        assert isinstance(result, list)
        assert len(result) == 2
        # First block: text info
        assert result[0]["type"] == "text"
        assert "test.png" in result[0]["text"]
        # Second block: image data
        assert result[1]["type"] == "image"
        assert result[1]["mime_type"] == "image/png"
        assert len(result[1]["base64"]) > 0

    def test_valid_jpeg(self, tmp_path):
        # Minimal JPEG (smallest valid JFIF)
        import base64
        jpeg_b64 = (
            "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////"
            "////////////////////////////////////////////////////////////2wBDAf//////////"
            "////////////////////////////////////////////////////////////////////////"
            "wAARCAABAAEDASIAAhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAA"
            "AAD/xAAUAQEAAAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEQMRAD8A"
            "KwA//9k="
        )
        jpeg_data = base64.b64decode(jpeg_b64)
        img = tmp_path / "photo.jpg"
        img.write_bytes(jpeg_data)

        result = view_image.invoke({"image_path": str(img)})
        assert isinstance(result, list)
        assert result[1]["mime_type"] == "image/jpeg"

    def test_file_too_large(self, tmp_path):
        # Create a file that exceeds the 5MB limit
        big_file = tmp_path / "huge.png"
        # Write a minimal PNG header + padding to exceed limit
        big_file.write_bytes(b"\x89PNG" + b"\x00" * (6 * 1024 * 1024))

        result = view_image.invoke({"image_path": str(big_file)})
        assert isinstance(result, str)
        assert "too large" in result.lower()

    def test_virtual_path_resolution(self, tmp_path):
        """Virtual path /image.png resolves to {workspace}/image.png."""
        import base64
        png_b64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
            "2mP8z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg=="
        )
        img = tmp_path / "chart.png"
        img.write_bytes(base64.b64decode(png_b64))

        # Set workspace root to tmp_path
        set_active_workspace(str(tmp_path))

        # Agent uses virtual path /chart.png
        result = view_image.invoke({"image_path": "/chart.png"})
        assert isinstance(result, list)
        assert result[0]["type"] == "text"
        assert "chart.png" in result[0]["text"]
        assert result[1]["type"] == "image"

        # Clean up
        set_active_workspace("")
