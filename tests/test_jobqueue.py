import threading
import time
import unittest

from qgis_dev_probe.core.errors import Busy, JobTimeout
from qgis_dev_probe.core.jobqueue import JobQueue


class _MainThreadSimulator:
    """メインスレッドの QTimer を模して pump() を繰り返し呼ぶスレッド。"""

    def __init__(self, queue: JobQueue):
        self.queue = queue
        self.thread_id = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        self.thread_id = threading.get_ident()
        while not self._stop.is_set():
            self.queue.pump()
            time.sleep(0.005)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=2)


class JobQueueTests(unittest.TestCase):
    def test_job_runs_on_pumping_thread_and_returns_result(self):
        queue = JobQueue()
        with _MainThreadSimulator(queue) as main:
            result = queue.submit(lambda: threading.get_ident(), 2.0)
        self.assertEqual(result, main.thread_id)
        self.assertNotEqual(result, threading.get_ident())

    def test_exception_is_propagated_to_submitter(self):
        queue = JobQueue()

        def boom():
            raise ValueError("bad value")

        with _MainThreadSimulator(queue), self.assertRaisesRegex(ValueError, "bad value"):
            queue.submit(boom, 2.0)

    def test_timeout_before_start_cancels_job(self):
        queue = JobQueue()
        ran = []
        with self.assertRaises(JobTimeout) as ctx:
            queue.submit(lambda: ran.append(1), 0.05)  # pump していない
        self.assertEqual(ctx.exception.details, {"started": False})
        # その後 pump しても、キャンセル済みのジョブは実行されない
        self.assertEqual(queue.pump(), 0)
        self.assertEqual(ran, [])

    def test_timeout_while_running_reports_not_cancelled(self):
        queue = JobQueue()
        release = threading.Event()
        finished = threading.Event()

        def slow():
            release.wait(2)
            finished.set()
            return "done"

        with _MainThreadSimulator(queue):
            with self.assertRaises(JobTimeout) as ctx:
                queue.submit(slow, 0.1)
            self.assertEqual(ctx.exception.details, {"started": True})
            release.set()
            self.assertTrue(finished.wait(2))  # ジョブ自体は完走する

    def test_busy_when_queue_is_full(self):
        queue = JobQueue(max_pending=2)
        errors = []

        def submit_quick():
            try:
                queue.submit(lambda: None, 0.3)
            except (Busy, JobTimeout) as exc:
                errors.append(exc)

        threads = [threading.Thread(target=submit_quick) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertTrue(any(isinstance(e, Busy) for e in errors))

    def test_pump_is_not_reentrant(self):
        queue = JobQueue()
        inner_results = []

        def job():
            inner_results.append(queue.pump())  # 実行中の再入は 0 を返す
            return "ok"

        holder = {}

        def submit():
            holder["r"] = queue.submit(job, 2.0)

        t = threading.Thread(target=submit)
        t.start()
        deadline = time.monotonic() + 2
        while queue.pending_count == 0 and time.monotonic() < deadline:
            time.sleep(0.001)
        queue.pump()
        t.join(2)
        self.assertEqual(holder["r"], "ok")
        self.assertEqual(inner_results, [0])

    def test_jobs_run_in_submission_order(self):
        queue = JobQueue()
        order = []
        with _MainThreadSimulator(queue):
            threads = []
            for i in range(5):
                t = threading.Thread(target=lambda i=i: queue.submit(lambda: order.append(i), 2.0))
                threads.append(t)
                t.start()
                time.sleep(0.01)
            for t in threads:
                t.join()
        self.assertEqual(order, [0, 1, 2, 3, 4])


if __name__ == "__main__":
    unittest.main()
