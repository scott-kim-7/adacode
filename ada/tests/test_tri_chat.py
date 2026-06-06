from unittest.mock import MagicMock, patch

from ada.llm import ChatMessage
from ada.registry import load_registry
from ada.tri_chat import TriChatSession


def test_tri_chat_run_turn_three_participants():
	reg = load_registry()
	session = TriChatSession.from_registry(reg)

	mock_local = MagicMock()
	mock_local.chat.return_value = "Local says hi"
	mock_external = MagicMock()
	mock_external.chat.return_value = "External says hi"
	session.local_client = mock_local
	session.external_client = mock_external

	replies = session.run_turn("Hello everyone")

	assert len(replies) == 2
	assert replies[0].speaker == session.local_label
	assert replies[1].speaker == session.external_label
	assert len(session.history) == 3  # user + local + external
	assert session.history[0].speaker == "User"
	mock_local.chat.assert_called_once()
	mock_external.chat.assert_called_once()
	session.close()
