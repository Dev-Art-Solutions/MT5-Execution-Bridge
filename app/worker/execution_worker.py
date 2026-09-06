from __future__ import annotations

import asyncio
import logging

from app.services.execution_service import ExecutionService
from app.storage.database import Database

logger = logging.getLogger("mt5_bridge.worker")

POLL_INTERVAL_SECONDS = 1.0


class ExecutionWorker:
    """Single-consumer worker draining PENDING signals from the durable queue.

    A single asyncio task claims work atomically via Database.claim_next_pending,
    so a second worker path (or a second instance of this task) can never process
    the same signal twice.
    """

    def __init__(self, db: Database, execution_service: ExecutionService) -> None:
        self._db = db
        self._execution_service = execution_service
        self._task: asyncio.Task | None = None
        self._running = False

    def recover_on_startup(self) -> None:
        """Signals left in PROCESSING after a crash are never auto-resent."""
        for row in self._db.find_stuck_processing():
            logger.warning("STARTUP_RECOVERY signal_id=%s", row["signal_id"])
            self._execution_service.reconcile_stuck_signal(row)

    async def start(self) -> None:
        self.recover_on_startup()
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    @property
    def running(self) -> bool:
        return self._running

    async def _run_loop(self) -> None:
        while self._running:
            try:
                claimed = self._db.claim_next_pending()
                if claimed is None:
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
                    continue
                logger.info("SIGNAL_QUEUED signal_id=%s -> EXECUTION_STARTED", claimed["signal_id"])
                await asyncio.to_thread(self._execution_service.process_signal, claimed)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("WORKER_LOOP_ERROR")
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
