import asyncio
import json

from magenta.models.base import AuditRecord, ModelRequest, ModelResponse, PolicyDecision


class AuditLogger:
    def __init__(
        self,
        enabled: bool = True,
        batch_size: int = 10,
        flush_interval: float = 5.0,
    ):
        self.enabled = enabled
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._buffer: list[AuditRecord] = []
        self._flush_task: asyncio.Task | None = None

    async def start(self) -> None:
        if self.enabled and not self._flush_task:
            self._flush_task = asyncio.create_task(self._periodic_flush())

    async def stop(self) -> None:
        if self._flush_task:
            self._flush_task.cancel()
            self._flush_task = None
        await self.flush()

    async def log(
        self,
        request: ModelRequest,
        response: ModelResponse,
        decision: PolicyDecision,
        fallback_used: bool = False,
        redacted: bool = False,
    ) -> None:
        if not self.enabled:
            return

        record = AuditRecord(
            correlation_id=request.correlation_id,
            task_type=request.task_type,
            sensitivity_level=request.sensitivity_level,
            priority=request.priority,
            provider=response.provider,
            model=response.model,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            latency_ms=response.latency_ms,
            fallback_used=fallback_used,
            redacted=redacted,
            risk_score=self._compute_risk(request, decision),
        )
        self._buffer.append(record)

        if len(self._buffer) >= self.batch_size:
            await self.flush()

    async def flush(self) -> None:
        if not self._buffer:
            return
        batch = self._buffer[:]
        self._buffer.clear()
        await self._write_batch(batch)

    async def _write_batch(self, records: list[AuditRecord]) -> None:
        lines = [json.dumps(self._record_to_dict(r)) for r in records]
        payload = "\n".join(lines)

        for writer in self._writers():
            try:
                await writer(payload, records)
            except Exception:
                pass

    def _writers(self):
        writers = []
        try:
            writers.append(self._elastic_writer)
        except ImportError:
            pass
        writers.append(self._console_writer)
        return writers

    async def _console_writer(self, payload: str, records: list[AuditRecord]) -> None:
        for record in records:
            print(
                f"[AUDIT] {record.correlation_id} | {record.provider}/{record.model} | "
                f"in={record.tokens_in} out={record.tokens_out} "
                f"lat={record.latency_ms:.0f}ms risk={record.risk_score}"
            )

    async def _elastic_writer(self, payload: str, records: list[AuditRecord]) -> None:
        from magenta.adapters.elastic import ElasticAdapter

        adapter = ElasticAdapter()
        for record in records:
            await adapter.index(index="magenta-llm-audit", body=self._record_to_dict(record))

    async def _periodic_flush(self) -> None:
        while True:
            await asyncio.sleep(self.flush_interval)
            await self.flush()

    def _compute_risk(self, request: ModelRequest, decision: PolicyDecision) -> int:
        risk = 0
        if request.sensitivity_level == "high":
            risk += 40
        elif request.sensitivity_level == "medium":
            risk += 20
        if request.priority == "interactive":
            risk += 10
        if decision.provider != "ollama":
            risk += 20
        return risk

    @staticmethod
    def _record_to_dict(r: AuditRecord) -> dict:
        return {
            "correlation_id": r.correlation_id,
            "task_type": r.task_type,
            "sensitivity_level": r.sensitivity_level,
            "priority": r.priority,
            "provider": r.provider,
            "model": r.model,
            "tokens_in": r.tokens_in,
            "tokens_out": r.tokens_out,
            "latency_ms": r.latency_ms,
            "fallback_used": r.fallback_used,
            "redacted": r.redacted,
            "risk_score": r.risk_score,
            "timestamp": r.timestamp,
        }
