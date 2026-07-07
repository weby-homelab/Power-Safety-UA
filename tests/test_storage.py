import pytest
import os
import json
from app.storage import StorageUtils, SafeStateContextAsync


@pytest.fixture
def temp_json_file(tmp_path):
    file_path = tmp_path / "test.json"
    data = {"key": "value"}
    with open(file_path, "w") as f:
        json.dump(data, f)
    return str(file_path)


@pytest.mark.anyio
async def test_load_json_async(temp_json_file):
    data = await StorageUtils.load_json_async(temp_json_file)
    assert data == {"key": "value"}


@pytest.mark.anyio
async def test_load_json_async_missing():
    data = await StorageUtils.load_json_async(
        "nonexistent.json", default={"default": 1}
    )
    assert data == {"default": 1}


@pytest.mark.anyio
async def test_save_json_async(tmp_path):
    file_path = str(tmp_path / "save.json")
    success = await StorageUtils.save_json_async(file_path, {"saved": True})
    assert success is True

    with open(file_path, "r") as f:
        data = json.load(f)
    assert data == {"saved": True}


def test_load_json_sync(temp_json_file):
    data = StorageUtils.load_json_sync(temp_json_file)
    assert data == {"key": "value"}


def test_load_json_sync_missing():
    data = StorageUtils.load_json_sync("nonexistent.json", default={"default": 1})
    assert data == {"default": 1}


def test_save_json_sync(tmp_path):
    file_path = str(tmp_path / "save_sync.json")
    success = StorageUtils.save_json_sync(file_path, {"saved": True})
    assert success is True

    with open(file_path, "r") as f:
        data = json.load(f)
    assert data == {"saved": True}


@pytest.mark.anyio
async def test_safe_state_context_async(tmp_path):
    lock_file = str(tmp_path / "test.lock")
    ctx = SafeStateContextAsync(lock_file)

    async with ctx:
        assert os.path.exists(lock_file)
        # Check reentrancy
        async with ctx:
            assert ctx._counter == 2
        assert ctx._counter == 1

    assert ctx._counter == 0
