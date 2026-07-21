"""Tests fuer den RateLimiter (Drosselung ausgehender Requests)."""

from __future__ import annotations

import asyncio
import time

from console_error_scanner.services.rate_limit import RateLimiter


def _elapsed(coro_factory) -> float:  # type: ignore[no-untyped-def]
    """Misst die Laufzeit einer Coroutine in Sekunden."""
    start = time.monotonic()
    asyncio.run(coro_factory())
    return time.monotonic() - start


class TestRateLimiter:
    def test_disabled_when_rate_is_zero(self) -> None:
        assert RateLimiter(0).enabled is False

    def test_disabled_when_rate_is_negative(self) -> None:
        assert RateLimiter(-5).enabled is False

    def test_enabled_when_rate_is_positive(self) -> None:
        assert RateLimiter(60).enabled is True

    def test_disabled_limiter_does_not_wait(self) -> None:
        async def run() -> None:
            limiter = RateLimiter(0)
            for _ in range(50):
                await limiter.acquire()

        assert _elapsed(run) < 0.2

    def test_sequential_calls_are_spaced(self) -> None:
        """1200/Minute = 50 ms Abstand; 5 Aufrufe warten also 4 Intervalle (rund 200 ms)."""

        async def run() -> None:
            limiter = RateLimiter(1200)
            for _ in range(5):
                await limiter.acquire()

        # Nur die untere Schranke pruefen, und mit Abstand zum Sollwert: die
        # Timeraufloesung unter Windows liegt bei rund 15 ms, ein Test auf exakt
        # 200 ms waere flaky. Ohne Limiter laeuft dieselbe Schleife in Mikrosekunden.
        assert _elapsed(run) >= 0.15

    def test_first_call_is_immediate(self) -> None:
        """Der erste Request darf nicht kuenstlich verzoegert werden."""

        async def run() -> None:
            await RateLimiter(60).acquire()

        assert _elapsed(run) < 0.2

    def test_concurrent_calls_are_serialised(self) -> None:
        """Auch gleichzeitig gestartete Aufrufe teilen sich die Zeitschlitze."""

        async def run() -> None:
            limiter = RateLimiter(1200)
            await asyncio.gather(*(limiter.acquire() for _ in range(5)))

        assert _elapsed(run) >= 0.15

    def test_pause_does_not_create_a_burst(self) -> None:
        """Nach einer Pause startet die Taktung neu, statt Slots nachzuholen."""

        async def run() -> None:
            limiter = RateLimiter(600)  # 100 ms Abstand
            await limiter.acquire()
            await asyncio.sleep(0.35)  # laenger als drei Intervalle untaetig
            start = asyncio.get_running_loop().time()
            await limiter.acquire()
            await limiter.acquire()
            # Ohne Burst-Schutz waere der erste Aufruf sofort UND der zweite auch;
            # korrekt ist: erster sofort, zweiter nach einem vollen Intervall.
            assert asyncio.get_running_loop().time() - start >= 0.07

        asyncio.run(run())
