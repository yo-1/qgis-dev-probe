import socket
import threading
import time
import unittest

from qgis_dev_probe.core.config import MODE_READONLY, ProbeConfig
from qgis_dev_probe.core.dispatcher import Dispatcher
from qgis_dev_probe.core.jobqueue import JobQueue
from qgis_dev_probe.core.server import ProbeServer

from .helpers import TOKEN, ProbeFixture, call, read_response, send_line


def _handlers():
    state = {"thread_ids": {}}

    def ping(args):
        state["thread_ids"]["ping"] = threading.get_ident()
        return {"pong": True}

    def echo(args):
        return {"echo": args}

    def boom(args):
        raise RuntimeError("kaboom")

    def slow(args):
        time.sleep(0.4)
        return "late"

    def huge(args):
        return ["x" * 20000 for _ in range(1000)]  # JSON 化すると 8 MiB を超える

    def read_log(args):  # main_thread=False のツール
        state["thread_ids"]["read_log"] = threading.get_ident()
        return {"entries": []}

    def set_widget(args):
        return {"set": args.get("value")}

    return state, {
        "ping": ping,
        "list_layers": echo,
        "inspect_layer": boom,
        "get_info": slow,
        "list_plugins": huge,
        "read_log": read_log,
        "set_widget": set_widget,
    }


class ServerEndToEndTests(unittest.TestCase):
    def test_ping_runs_on_main_thread_and_returns_result(self):
        state, handlers = _handlers()
        with ProbeFixture(handlers) as fx, fx.connect() as sock:
            resp = call(sock, "ping")
            self.assertEqual(resp, {"id": 1, "ok": True, "result": {"pong": True}})
            self.assertEqual(state["thread_ids"]["ping"], fx.main.thread_id)

    def test_thread_safe_tool_runs_off_main_thread(self):
        state, handlers = _handlers()
        with ProbeFixture(handlers) as fx, fx.connect() as sock:
            self.assertTrue(call(sock, "read_log")["ok"])
            self.assertNotEqual(state["thread_ids"]["read_log"], fx.main.thread_id)

    def test_multiple_requests_on_one_connection_and_japanese(self):
        _, handlers = _handlers()
        with ProbeFixture(handlers) as fx, fx.connect() as sock:
            for i in range(20):
                resp = call(sock, "list_layers", {"名前": f"山梨県{i}"})
                self.assertEqual(resp["result"]["echo"], {"名前": f"山梨県{i}"})

    def test_invalid_token_is_rejected_and_connection_closed(self):
        _, handlers = _handlers()
        with ProbeFixture(handlers) as fx, fx.connect() as sock:
            resp = call(sock, "ping", token="wrong")
            self.assertEqual(resp["error"]["code"], "auth_failed")
            self.assertEqual(sock.recv(10), b"")  # サーバーが接続を閉じる

    def test_missing_token_is_rejected(self):
        _, handlers = _handlers()
        with ProbeFixture(handlers) as fx, fx.connect() as sock:
            resp = send_line(sock, {"id": 1, "tool": "ping"})
            self.assertEqual(resp["error"]["code"], "auth_failed")

    def test_bad_json_does_not_kill_connection(self):
        _, handlers = _handlers()
        with ProbeFixture(handlers) as fx, fx.connect() as sock:
            resp = send_line(sock, b"this is not json\n")
            self.assertEqual(resp["error"]["code"], "bad_request")
            self.assertTrue(call(sock, "ping")["ok"])

    def test_oversized_request_is_rejected(self):
        _, handlers = _handlers()
        with ProbeFixture(handlers) as fx, fx.connect() as sock:
            sock.sendall(b"x" * (1_048_576 + 10))
            resp = read_response(sock)
            self.assertEqual(resp["error"]["code"], "bad_request")

    def test_unknown_tool_lists_available(self):
        _, handlers = _handlers()
        with ProbeFixture(handlers) as fx, fx.connect() as sock:
            resp = call(sock, "format_disk")
            self.assertEqual(resp["error"]["code"], "unknown_tool")
            self.assertIn("ping", resp["error"]["details"]["available"])

    def test_known_tool_without_handler_is_reported(self):
        with ProbeFixture({}) as fx, fx.connect() as sock:
            resp = call(sock, "ping")
            self.assertEqual(resp["error"]["code"], "unknown_tool")
            self.assertIn("not implemented", resp["error"]["message"])

    def test_readonly_mode_blocks_act_tools(self):
        _, handlers = _handlers()
        with ProbeFixture(handlers, mode=MODE_READONLY) as fx, fx.connect() as sock:
            self.assertTrue(call(sock, "ping")["ok"])
            resp = call(sock, "set_widget", {"value": 1})
            self.assertEqual(resp["error"]["code"], "policy_denied")

    def test_mode_change_takes_effect_without_restart(self):
        _, handlers = _handlers()
        with ProbeFixture(handlers, mode=MODE_READONLY) as fx, fx.connect() as sock:
            self.assertEqual(call(sock, "set_widget")["error"]["code"], "policy_denied")
            fx.config.mode = "interactive"
            self.assertTrue(call(sock, "set_widget", {"value": 2})["ok"])

    def test_execute_code_denied_unless_explicitly_allowed(self):
        handlers = {"execute_code": lambda args: {"ran": True}}
        with ProbeFixture(handlers) as fx, fx.connect() as sock:
            self.assertEqual(call(sock, "execute_code", {"code": "1"})["error"]["code"], "policy_denied")
            fx.config.allow_exec = True
            self.assertTrue(call(sock, "execute_code", {"code": "1"})["ok"])

    def test_handler_exception_becomes_handler_error_with_traceback(self):
        _, handlers = _handlers()
        with ProbeFixture(handlers) as fx, fx.connect() as sock:
            resp = call(sock, "inspect_layer")
            self.assertEqual(resp["error"]["code"], "handler_error")
            self.assertIn("kaboom", resp["error"]["message"])
            self.assertIn("RuntimeError", resp["error"]["details"]["traceback"])
            self.assertTrue(call(sock, "ping")["ok"])  # 失敗後も継続して動く

    def test_per_request_timeout(self):
        _, handlers = _handlers()
        with ProbeFixture(handlers) as fx, fx.connect() as sock:
            resp = call(sock, "get_info", timeout_s=0.1)
            self.assertEqual(resp["error"]["code"], "timeout")
            self.assertEqual(resp["error"]["details"], {"started": True})
            time.sleep(0.5)  # 遅いジョブの完走を待つ
            self.assertTrue(call(sock, "ping")["ok"])

    def test_oversized_response_is_replaced_by_error(self):
        _, handlers = _handlers()
        with ProbeFixture(handlers) as fx, fx.connect() as sock:
            resp = call(sock, "list_plugins")
            self.assertEqual(resp["error"]["code"], "response_too_large")

    def test_activity_log_records_calls_without_arguments(self):
        _, handlers = _handlers()
        with ProbeFixture(handlers) as fx, fx.connect() as sock:
            call(sock, "list_layers", {"secret": "do-not-log"})
            call(sock, "ping")
            entries = list(fx.dispatcher.activity)
            self.assertEqual([e["tool"] for e in entries], ["list_layers", "ping"])
            self.assertTrue(all(e["ok"] for e in entries))
            self.assertNotIn("do-not-log", repr(entries))

    def test_concurrent_clients(self):
        _, handlers = _handlers()
        with ProbeFixture(handlers) as fx:
            results = []

            def worker(n):
                with fx.connect() as sock:
                    for i in range(10):
                        results.append(call(sock, "list_layers", {"n": n, "i": i})["ok"])

            threads = [threading.Thread(target=worker, args=(n,)) for n in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(10)
            self.assertEqual(len(results), 50)
            self.assertTrue(all(results))

    def test_connection_limit(self):
        _, handlers = _handlers()
        config = ProbeConfig().validate()
        queue = JobQueue()
        server = ProbeServer(Dispatcher(handlers, config, queue), TOKEN, max_connections=1, idle_timeout_s=5)
        port = server.start()
        try:
            first = socket.create_connection(("127.0.0.1", port), timeout=5)
            time.sleep(0.1)
            second = socket.create_connection(("127.0.0.1", port), timeout=5)
            self.assertEqual(read_response(second)["error"]["code"], "busy")
            first.close()
            second.close()
        finally:
            server.stop()

    def test_stop_closes_connections_and_listener(self):
        _, handlers = _handlers()
        with ProbeFixture(handlers) as fx:
            sock = fx.connect()
            self.assertTrue(call(sock, "ping")["ok"])
            port = fx.port
            fx.server.stop()
            self.assertFalse(fx.server.running)
            self.assertEqual(sock.recv(10), b"")
            sock.close()
            with self.assertRaises(OSError):
                socket.create_connection(("127.0.0.1", port), timeout=1)


class ServerSafetyTests(unittest.TestCase):
    def test_refuses_non_loopback_bind(self):
        config = ProbeConfig().validate()
        dispatcher = Dispatcher({}, config, JobQueue())
        for host in ("0.0.0.0", "192.168.0.5", ""):
            with self.subTest(host=host), self.assertRaises(ValueError):
                ProbeServer(dispatcher, TOKEN, host=host)

    def test_refuses_empty_token(self):
        with self.assertRaises(ValueError):
            ProbeServer(Dispatcher({}, ProbeConfig().validate(), JobQueue()), "")

    def test_listens_on_loopback_only(self):
        with ProbeFixture({}) as fx:
            host, _port = fx.server._listener.getsockname()[:2]
            self.assertEqual(host, "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
