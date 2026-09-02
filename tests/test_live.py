import pytest

from sportsbot.config import Settings
from sportsbot.live import LiveTradingDisabled, require_live


def test_live_requires_explicit_enable(tmp_path):
    with pytest.raises(LiveTradingDisabled):
        require_live(Settings(data_dir=tmp_path, live_enabled=False))
    with pytest.raises(LiveTradingDisabled):
        require_live(Settings(data_dir=tmp_path, live_enabled=True, kalshi_api_key_id="", kalshi_private_key_path=""))
