import asyncio
import os
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def reset_global_semaphores():
    """Clear global tracking between tests."""
    from specweaver.infrastructure.llm.adapters._rate_limit import _PROVIDER_SEMAPHORES
    _PROVIDER_SEMAPHORES.clear()
    yield
    _PROVIDER_SEMAPHORES.clear()


@pytest.fixture()
def db(tmp_path):
    """Fresh database with schema."""
    from specweaver.core.config.database import Database
    return Database(tmp_path / ".specweaver" / "specweaver.db")


@pytest.mark.asyncio
async def test_factory_allocates_shared_semaphore_pool(db):
    """
    Proves that N simultaneous factory invocations (like fan_out)
    all bind to the exact same globally addressed asyncio.Semaphore pool.
    """
    from specweaver.infrastructure.llm.factory import create_llm_adapter
    from specweaver.infrastructure.llm.adapters._rate_limit import _PROVIDER_SEMAPHORES

    db.register_project("test-proj", "/tmp/test")
    db.set_active_project("test-proj")

    def spawn_adapter():
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-1234"}):
            _settings, adapter, _config = create_llm_adapter(db, telemetry_project=None)
            return adapter

    # Spawn 5 completely independent adapters (like 5 parallel runners)
    adapters = [spawn_adapter() for _ in range(5)]
    
    assert len(adapters) == 5
    adapter_A = adapters[0]
    adapter_B = adapters[1]

    # By default, limit is 3. We prove they look at the exact same bound pool.
    latch_A = await adapter_A._wait_for_lock()
    latch_B = await adapter_B._wait_for_lock()

    assert len(_PROVIDER_SEMAPHORES) == 1
    
    # 2 are held. 1 remaining globally.
    pool = _PROVIDER_SEMAPHORES["gemini"]
    assert pool._value == 1  # 3 - 2 = 1 left
    
    # Prove they point to the exact same address
    assert adapter_A._get_semaphore() is adapter_B._get_semaphore()
    assert adapter_A._get_semaphore() is pool
    
    # Release safely
    latch_A.release()
    latch_B.release()
    
    assert pool._value == 3
