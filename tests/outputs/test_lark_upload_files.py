"""Tests for Lark Drive file upload functionality."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from lore.outputs.lark_doc import LarkDocOutput


@pytest.fixture
def lark_output():
    """Create a LarkDocOutput instance for testing."""
    return LarkDocOutput(
        app_id="test_app_id",
        app_secret="test_secret",
        folder_token="test_folder_token",
        parent_doc_id="test_parent_doc_id"
    )


@pytest.fixture
def mock_auth():
    """Mock tenant token authentication."""
    with patch('lore.outputs.lark_doc._get_tenant_token') as mock:
        mock.return_value = "test_tenant_token"
        yield mock


def test_upload_file_to_folder_uploads_png(lark_output, mock_auth):
    """Test uploading PNG file to a specific folder."""
    image_bytes = b"fake_png_data"

    with patch('lore.outputs.lark_doc.httpx.post') as mock_post:
        # Mock successful upload response
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "data": {"file_token": "uploaded_file_token"}
        }
        mock_post.return_value = mock_response

        file_token = lark_output.upload_file_to_folder(
            file_bytes=image_bytes,
            filename="test.png",
            folder_token="image_folder_token",
            file_type="image/png"
        )

        assert file_token == "uploaded_file_token"
        assert mock_post.called

        # Verify multipart form-data structure
        call_kwargs = mock_post.call_args[1]
        assert "files" in call_kwargs
        files = call_kwargs["files"]
        assert files["file_name"] == (None, "test.png")
        assert files["parent_node"] == (None, "image_folder_token")


def test_upload_file_to_folder_uploads_mmd(lark_output, mock_auth):
    """Test uploading .mmd text file to a specific folder."""
    mmd_content = "erDiagram\n  users {\n    int id\n  }"
    mmd_bytes = mmd_content.encode('utf-8')

    with patch('lore.outputs.lark_doc.httpx.post') as mock_post:
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "data": {"file_token": "mmd_file_token"}
        }
        mock_post.return_value = mock_response

        file_token = lark_output.upload_file_to_folder(
            file_bytes=mmd_bytes,
            filename="wallet.mmd",
            folder_token="code_folder_token",
            file_type="text/plain"
        )

        assert file_token == "mmd_file_token"

        # Verify file content
        call_kwargs = mock_post.call_args[1]
        files = call_kwargs["files"]
        assert files["file"][0] == "wallet.mmd"
        assert files["file"][2] == "text/plain"


def test_upload_file_to_folder_handles_error(lark_output, mock_auth):
    """Test error handling when upload fails."""
    with patch('lore.outputs.lark_doc.httpx.post') as mock_post:
        # Mock error response (code != 0)
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 1001,
            "msg": "Invalid folder token"
        }
        mock_post.return_value = mock_response

        with pytest.raises(RuntimeError, match="Lark file upload failed"):
            lark_output.upload_file_to_folder(
                file_bytes=b"data",
                filename="test.png",
                folder_token="invalid_token",
                file_type="image/png"
            )


def test_upload_erd_files_to_folders_creates_both_formats(lark_output, mock_auth):
    """Test dual upload creates PNG and .mmd files."""
    erd_map = {
        "wallet": "erDiagram\n  wallet { int id }",  # Small ERD (<5KB)
    }

    with patch('lore.outputs.lark_doc.httpx.post') as mock_post, \
         patch('lore.mermaid_renderer.MermaidRenderer') as mock_renderer_class:

        # Mock image rendering
        mock_renderer = Mock()
        mock_renderer.render.return_value = b"fake_png_data"
        mock_renderer_class.return_value = mock_renderer

        # Mock successful uploads
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "data": {"file_token": "test_token"}
        }
        mock_post.return_value = mock_response

        uploaded_pngs, uploaded_mmds = lark_output.upload_erd_files_to_folders(
            erd_map=erd_map,
            image_folder_token="img_folder",
            code_folder_token="code_folder"
        )

        assert len(uploaded_pngs) == 1
        assert uploaded_pngs[0] == "wallet.png"
        assert len(uploaded_mmds) == 1
        assert uploaded_mmds[0] == "wallet.mmd"

        # Verify both PNG and .mmd were uploaded
        assert mock_post.call_count == 2


def test_upload_erd_files_to_folders_skips_large_erds(lark_output, mock_auth):
    """Test that ERDs >15KB are skipped."""
    large_erd = "erDiagram\n" + "x" * 20000  # >15KB
    erd_map = {
        "large_category": large_erd,
    }

    uploaded_pngs, uploaded_mmds = lark_output.upload_erd_files_to_folders(
        erd_map=erd_map,
        image_folder_token="img_folder",
        code_folder_token="code_folder"
    )

    # Should skip oversized ERDs
    assert len(uploaded_pngs) == 0
    assert len(uploaded_mmds) == 0


def test_upload_erd_files_to_folders_skips_png_for_large_erd(lark_output, mock_auth):
    """Test that PNG is skipped but .mmd is uploaded for ERDs >5KB but <15KB."""
    medium_erd = "erDiagram\n" + "x" * 7000  # >5KB but <15KB
    erd_map = {
        "medium": medium_erd,
    }

    with patch('lore.outputs.lark_doc.httpx.post') as mock_post:
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "data": {"file_token": "test_token"}
        }
        mock_post.return_value = mock_response

        uploaded_pngs, uploaded_mmds = lark_output.upload_erd_files_to_folders(
            erd_map=erd_map,
            image_folder_token="img_folder",
            code_folder_token="code_folder"
        )

        # PNG skipped, only .mmd uploaded
        assert len(uploaded_pngs) == 0
        assert len(uploaded_mmds) == 1
        assert uploaded_mmds[0] == "medium.mmd"


def test_upload_erd_files_to_folders_handles_render_failure(lark_output, mock_auth):
    """Test graceful handling when image rendering fails."""
    erd_map = {
        "failing": "erDiagram\n  users { int id }",
    }

    with patch('lore.outputs.lark_doc.httpx.post') as mock_post, \
         patch('lore.mermaid_renderer.MermaidRenderer') as mock_renderer_class:

        # Mock renderer to raise exception
        mock_renderer = Mock()
        mock_renderer.render.side_effect = RuntimeError("Rendering failed")
        mock_renderer_class.return_value = mock_renderer

        # Mock successful .mmd upload
        mock_response = Mock()
        mock_response.json.return_value = {
            "code": 0,
            "data": {"file_token": "test_token"}
        }
        mock_post.return_value = mock_response

        uploaded_pngs, uploaded_mmds = lark_output.upload_erd_files_to_folders(
            erd_map=erd_map,
            image_folder_token="img_folder",
            code_folder_token="code_folder"
        )

        # PNG failed, but .mmd still uploaded
        assert len(uploaded_pngs) == 0
        assert len(uploaded_mmds) == 1


def test_upload_erd_files_to_folders_requires_both_folders(lark_output):
    """Test validation requires both folder tokens."""
    erd_map = {"test": "erDiagram"}

    with pytest.raises(ValueError, match="Both image_folder_token and code_folder_token are required"):
        lark_output.upload_erd_files_to_folders(
            erd_map=erd_map,
            image_folder_token="img_folder",
            code_folder_token=None  # Missing code folder
        )
