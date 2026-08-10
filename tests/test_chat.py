from pathlib import Path

from components import chat


def test_chat_autoscroll_component_tracks_streamed_content() -> None:
    source = Path(chat.__file__).read_text()

    assert "MutationObserver" in source
    assert "ResizeObserver" in source
    assert "transcript.scrollTop = transcript.scrollHeight" in source
    assert "mutationObserver.disconnect()" in source
    assert "resizeObserver.disconnect()" in source
