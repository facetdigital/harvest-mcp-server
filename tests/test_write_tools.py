"""Tests for write gating, request routing, and response passthrough.

Run with:  uv run python -m unittest discover -s tests -v

No external test dependencies: stdlib unittest only. The server module is
loaded fresh per environment configuration because HARVEST_READ_ONLY and
HARVEST_WRITE_TOOLS are read at import time.
"""

import ast
import importlib.util
import json
import os
import unittest
from pathlib import Path

SERVER_PATH = Path(__file__).resolve().parent.parent / "harvest-mcp-server.py"

BASE_ENV = {
    "HARVEST_ACCOUNT_ID": "111111",
    "HARVEST_API_KEY": "test-key-not-real",
}


def load_server(**extra_env):
    """Import the server module fresh under a controlled environment."""
    saved = {}
    keys = set(BASE_ENV) | {"HARVEST_READ_ONLY", "HARVEST_WRITE_TOOLS"} | set(
        extra_env
    )
    for key in keys:
        saved[key] = os.environ.pop(key, None)
    os.environ.update(BASE_ENV)
    os.environ.update(extra_env)
    try:
        spec = importlib.util.spec_from_file_location(
            "harvest_mcp_server_under_test", SERVER_PATH
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class RecordingStub:
    """Replaces harvest_request; records calls and returns a canned payload."""

    def __init__(self, payload=None):
        self.calls = []
        self.payload = payload if payload is not None else {"ok": True}

    async def __call__(self, path, params=None, method="GET"):
        self.calls.append({"path": path, "params": params, "method": method})
        return self.payload


class FakeResponse:
    def __init__(self, status_code, content=b"", json_data=None, text=""):
        self.status_code = status_code
        self.content = content
        self.text = text
        self._json = json_data

    def json(self):
        return self._json


class FakeAsyncClient:
    """Stands in for httpx.AsyncClient; returns a preconfigured response."""

    response = FakeResponse(200, content=b"{}", json_data={})
    requests_made = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, headers=None, params=None):
        FakeAsyncClient.requests_made.append(("GET", url))
        return FakeAsyncClient.response

    async def request(self, method, url, headers=None, json=None):
        FakeAsyncClient.requests_made.append((method, url))
        return FakeAsyncClient.response


class FakeHttpx:
    AsyncClient = FakeAsyncClient


class GuardStructureTest(unittest.TestCase):
    """Every tool that issues a non-GET request must be a guarded write tool."""

    def setUp(self):
        self.source = SERVER_PATH.read_text()
        self.tree = ast.parse(self.source)
        self.module = load_server()

    def tool_functions(self):
        for node in self.tree.body:
            if isinstance(node, ast.AsyncFunctionDef):
                yield node

    @staticmethod
    def non_get_methods(node):
        methods = []
        for call in ast.walk(node):
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "harvest_request"
            ):
                method = "GET"
                for keyword in call.keywords:
                    if keyword.arg == "method" and isinstance(
                        keyword.value, ast.Constant
                    ):
                        method = keyword.value.value
                if method != "GET":
                    methods.append(method)
        return methods

    def test_every_writing_tool_is_listed_and_guarded(self):
        for node in self.tool_functions():
            if not self.non_get_methods(node):
                continue
            with self.subTest(tool=node.name):
                self.assertIn(node.name, self.module.WRITE_TOOLS)
                segment = ast.get_source_segment(self.source, node)
                self.assertIn(f'write_refusal("{node.name}")', segment)
                self.assertLess(
                    segment.index("write_refusal("),
                    segment.index("harvest_request"),
                    "guard must precede the request",
                )

    def test_every_listed_write_tool_exists(self):
        names = {node.name for node in self.tool_functions()}
        for tool in self.module.WRITE_TOOLS:
            with self.subTest(tool=tool):
                self.assertIn(tool, names)

    def test_read_tools_are_not_listed(self):
        for node in self.tool_functions():
            if self.non_get_methods(node):
                continue
            with self.subTest(tool=node.name):
                self.assertNotIn(node.name, self.module.WRITE_TOOLS)


class ReadOnlyModeTest(unittest.IsolatedAsyncioTestCase):
    async def test_write_tools_refuse_without_network(self):
        module = load_server(HARVEST_READ_ONLY="true")
        stub = RecordingStub()
        module.harvest_request = stub

        for call in (
            lambda: module.update_time_entry(1, hours=2.0),
            lambda: module.delete_time_entry(1),
            lambda: module.create_time_entry(1, 2, "2026-08-06", 1.0),
        ):
            result = json.loads(await call())
            self.assertEqual(result["error"], "read_only_mode")
        self.assertEqual(stub.calls, [])

    async def test_refusal_covers_every_write_tool_name(self):
        module = load_server(HARVEST_READ_ONLY="true")
        for tool in module.WRITE_TOOLS:
            with self.subTest(tool=tool):
                self.assertEqual(
                    module.write_refusal(tool), module.READ_ONLY_MESSAGE
                )

    async def test_central_guard_blocks_unguarded_writes(self):
        module = load_server(HARVEST_READ_ONLY="true")
        FakeAsyncClient.requests_made = []
        module.httpx = FakeHttpx
        with self.assertRaises(Exception) as ctx:
            await module.harvest_request("time_entries", {}, method="POST")
        self.assertIn("HARVEST_READ_ONLY", str(ctx.exception))
        self.assertEqual(FakeAsyncClient.requests_made, [])

    async def test_central_guard_allows_reads(self):
        module = load_server(HARVEST_READ_ONLY="true")
        FakeAsyncClient.requests_made = []
        FakeAsyncClient.response = FakeResponse(
            200, content=b'{"users": []}', json_data={"users": []}
        )
        module.httpx = FakeHttpx
        result = await module.harvest_request("users")
        self.assertEqual(result, {"users": []})
        self.assertEqual(len(FakeAsyncClient.requests_made), 1)


class WriteAllowlistTest(unittest.IsolatedAsyncioTestCase):
    ALLOW = "create_time_entry,update_time_entry,delete_time_entry"

    async def test_unlisted_tool_refuses_and_echoes_allowlist(self):
        module = load_server(HARVEST_WRITE_TOOLS=self.ALLOW)
        stub = RecordingStub()
        module.harvest_request = stub

        result = json.loads(await module.delete_project(42))
        self.assertEqual(result["error"], "write_not_allowed")
        for allowed_name in self.ALLOW.split(","):
            self.assertIn(allowed_name, result["message"])
        self.assertEqual(stub.calls, [])

    async def test_listed_tool_proceeds(self):
        module = load_server(HARVEST_WRITE_TOOLS=self.ALLOW)
        stub = RecordingStub()
        module.harvest_request = stub

        await module.update_time_entry(7, hours=1.5)
        self.assertEqual(len(stub.calls), 1)

    async def test_read_only_wins_over_allowlist(self):
        module = load_server(
            HARVEST_WRITE_TOOLS=self.ALLOW, HARVEST_READ_ONLY="true"
        )
        result = json.loads(await module.update_time_entry(7, hours=1.5))
        self.assertEqual(result["error"], "read_only_mode")

    def test_unknown_name_is_a_startup_error(self):
        with self.assertRaises(ValueError) as ctx:
            load_server(HARVEST_WRITE_TOOLS="update_time_entry,not_a_tool")
        self.assertIn("not_a_tool", str(ctx.exception))

    def test_whitespace_and_empty_items_tolerated(self):
        module = load_server(
            HARVEST_WRITE_TOOLS=" update_time_entry , delete_time_entry ,"
        )
        self.assertEqual(
            module.HARVEST_ALLOWED_WRITE_TOOLS,
            frozenset({"update_time_entry", "delete_time_entry"}),
        )


class TimeEntryRoutingTest(unittest.IsolatedAsyncioTestCase):
    async def test_update_sends_only_provided_fields(self):
        module = load_server()
        stub = RecordingStub()
        module.harvest_request = stub

        await module.update_time_entry(31, hours=2.25, notes="standup")
        call = stub.calls[0]
        self.assertEqual(call["path"], "time_entries/31")
        self.assertEqual(call["method"], "PATCH")
        self.assertEqual(call["params"], {"hours": 2.25, "notes": "standup"})

    async def test_update_with_only_task_id_sends_exactly_that_field(self):
        module = load_server()
        stub = RecordingStub()
        module.harvest_request = stub

        await module.update_time_entry(31, task_id=9)
        self.assertEqual(stub.calls[0]["params"], {"task_id": 9})

    async def test_update_coerces_integer_notes(self):
        module = load_server()
        stub = RecordingStub()
        module.harvest_request = stub

        await module.update_time_entry(31, notes=12345)
        self.assertEqual(stub.calls[0]["params"], {"notes": "12345"})

    async def test_delete_routes_to_delete(self):
        module = load_server()
        stub = RecordingStub(payload={"status": "ok"})
        module.harvest_request = stub

        result = json.loads(await module.delete_time_entry(31))
        call = stub.calls[0]
        self.assertEqual(call["path"], "time_entries/31")
        self.assertEqual(call["method"], "DELETE")
        self.assertIsNone(call["params"])
        self.assertEqual(result, {"status": "ok"})


class HarvestRequestTest(unittest.IsolatedAsyncioTestCase):
    async def test_204_empty_delete_returns_ok(self):
        module = load_server()
        module.httpx = FakeHttpx
        FakeAsyncClient.response = FakeResponse(204, content=b"")
        result = await module.harvest_request("time_entries/31", method="DELETE")
        self.assertEqual(result, {"status": "ok"})

    async def test_200_empty_delete_returns_ok(self):
        module = load_server()
        module.httpx = FakeHttpx
        FakeAsyncClient.response = FakeResponse(200, content=b"")
        result = await module.harvest_request("time_entries/31", method="DELETE")
        self.assertEqual(result, {"status": "ok"})

    async def test_error_status_raises(self):
        module = load_server()
        module.httpx = FakeHttpx
        FakeAsyncClient.response = FakeResponse(
            422, content=b"x", text="Unprocessable"
        )
        with self.assertRaises(Exception) as ctx:
            await module.harvest_request("time_entries/31", method="DELETE")
        self.assertIn("422", str(ctx.exception))


class ResponsePassthroughTest(unittest.IsolatedAsyncioTestCase):
    async def test_list_time_entries_preserves_lock_fields(self):
        module = load_server()
        payload = {
            "time_entries": [
                {
                    "id": 1,
                    "hours": 2.0,
                    "is_locked": True,
                    "is_billed": False,
                    "locked_reason": "Item Invoiced and Approved",
                },
                {"id": 2, "hours": 1.0, "is_locked": False, "is_billed": True},
            ],
            "per_page": 2000,
        }
        module.harvest_request = RecordingStub(payload=payload)

        result = json.loads(await module.list_time_entries())
        self.assertEqual(result, payload)
        for entry in result["time_entries"]:
            self.assertIn("is_locked", entry)
            self.assertIn("is_billed", entry)


if __name__ == "__main__":
    unittest.main()
