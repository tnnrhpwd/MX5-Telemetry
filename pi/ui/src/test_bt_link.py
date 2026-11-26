#!/usr/bin/env python3
"""Desk test for Bluetooth supervision: a transport that failed must come back.

The link used to be started exactly once, at boot. On the car that is the worst possible
moment: systemd starts this service and bluetoothd, the USB dongle, or the adapter's own
power-on can easily be a few seconds behind it. A single failed `start()` left
`spp`/`ble` as None and nothing ever tried again, so the Pi answered on the USB tether and
silently had no Bluetooth for the rest of the drive. Recovery depended on `mx5-bt-agent`
waiting 90s and restarting the whole service, taking CAN and the display down with it.

These tests pin the replacement contract with fake transports, so no radio is needed:

    python3 test_bt_link.py
    pytest test_bt_link.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bt_link import BtLink  # noqa: E402


# -- fakes ------------------------------------------------------------------

class FakeTransport:
    """The slice of a transport interface BtLink uses: start/stop/is_alive."""

    def __init__(self, fail_times=0):
        self.started = False
        self.stopped = False
        self.alive = False
        self.fail_times = fail_times

    def start(self):
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError('no adapter')
        self.started = True
        self.alive = True

    def stop(self):
        self.stopped = True
        self.alive = False

    def is_alive(self):
        return self.alive

    def describe(self):
        return {'transport': 'fake', 'listening': self.alive}


class Factory:
    """Hands out FakeTransports, remembering every one it made.

    `fail_times` is the number of *starts* that fail before the radio comes up, so
    `Factory(fail_times=2)` models a boot where the first two attempts are too early.
    """

    def __init__(self, fail_times=0, fail_forever=False):
        self.calls = 0
        self.made = []
        self.remaining_failures = fail_times
        self.fail_forever = fail_forever

    def __call__(self, **kwargs):
        self.calls += 1
        if self.fail_forever:
            raise RuntimeError('no adapter')
        transport = FakeTransport(fail_times=1 if self.remaining_failures > 0 else 0)
        if self.remaining_failures > 0:
            self.remaining_failures -= 1
        self.made.append(transport)
        return transport

    @property
    def last(self):
        return self.made[-1]


def make_link(mode='spp', spp_factory=None, ble_factory=None, tick=0.01,
              retry_initial=0.01, retry_max=0.02):
    """A BtLink with a token (so it will start) and test-sized timings."""
    return BtLink(object(), mode=mode, token='secret',
                  spp_factory=spp_factory or Factory(),
                  ble_factory=ble_factory or Factory(),
                  supervisor_tick=tick, retry_initial=retry_initial,
                  retry_max=retry_max)


def wait_for(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


# -- tests ------------------------------------------------------------------

def test_retries_until_the_radio_appears():
    factory = Factory(fail_times=2)
    link = make_link(spp_factory=factory)
    try:
        assert link.start() is False, 'the first start must report failure, not lie'
        assert link.status()['failed_attempts'].get('spp') == 1

        assert wait_for(lambda: link._spp is not None), 'the link never retried'
        assert factory.calls == 3, f'expected 2 retries, saw {factory.calls - 1}'
        assert link._spp.alive and 'spp' not in link.errors
        assert link.status()['supervising'] is True
    finally:
        link.stop()


def test_backoff_grows_then_caps():
    factory = Factory(fail_forever=True)
    link = make_link(spp_factory=factory, retry_initial=1.0, retry_max=4.0)
    # Drive _ensure directly so the assertion is about the schedule, not the clock.
    seen = []
    for _ in range(5):
        link._retry_at.pop('spp', None)     # pretend the scheduled time has arrived
        before = time.monotonic()
        link._ensure('spp', link._start_spp)
        seen.append(round(link._retry_at['spp'] - before, 1))
    assert seen == [1.0, 2.0, 4.0, 4.0, 4.0], f'backoff was {seen}'


def test_dead_transport_is_restarted():
    factory = Factory()
    link = make_link(spp_factory=factory)
    try:
        assert link.start() is True
        first = link._spp
        assert first.alive

        # The radio was reset / bluetoothd restarted: the loop is gone but the object
        # looks fine. This is the case `start()` alone can never catch.
        first.alive = False
        link._repair()

        assert first.stopped, 'the dead transport must be closed before replacing it'
        assert factory.calls == 2, 'the transport was not reopened'
        assert link._spp is not first and link._spp.alive
    finally:
        link.stop()


def test_healthy_transport_is_left_alone():
    factory = Factory()
    link = make_link(spp_factory=factory)
    try:
        link.start()
        for _ in range(3):
            link._repair()
        assert factory.calls == 1, 'a live transport must not be restarted'
    finally:
        link.stop()


def test_refused_without_token_starts_nothing():
    factory = Factory()
    link = BtLink(object(), mode='spp', token='', spp_factory=factory,
                  supervisor_tick=0.01, retry_initial=0.01, retry_max=0.02)
    # allow_no_token only comes from the environment; make sure it is not set here.
    link.allow_no_token = False
    link.refused_reason = 'no token configured'

    assert link.start() is False
    assert factory.calls == 0, 'an unauthenticated link must not open a radio'
    assert link.status().get('refused')

    # And the supervisor must not be a back door around that refusal.
    link._repair()
    assert factory.calls == 0


def test_stop_ends_the_supervisor():
    factory = Factory(fail_forever=True)
    link = make_link(spp_factory=factory)
    link.start()
    assert wait_for(lambda: factory.calls >= 2), 'the supervisor never ticked'

    link.stop()
    assert link.status()['supervising'] is False
    calls_at_stop = factory.calls
    time.sleep(0.1)             # ten ticks' worth
    assert factory.calls == calls_at_stop, 'the supervisor kept retrying after stop()'
    assert link._spp is None and link._ble is None


def test_start_after_stop_is_immediate_and_works():
    """A restart must not inherit the previous run's backoff or stop flag."""
    factory = Factory()
    link = make_link(spp_factory=factory, retry_initial=30.0, retry_max=60.0)
    try:
        assert link.start() is True
        link.stop()
        assert link._spp is None

        # 30s of backoff is pending only if the state was not cleared, and the stop flag
        # would close the transport the moment it came up.
        started = link.start()
        assert started is True, 'the link refused to come back after stop()'
        assert link._spp is not None and link._spp.alive
        assert factory.calls == 2
    finally:
        link.stop()


def test_a_stop_while_starting_adopts_nothing():
    """stop() can land while the BLE start is still waiting for its advertisement."""
    factory = Factory()

    class SlowTransport(FakeTransport):
        def start(self):
            time.sleep(0.05)
            self.alive = True

    slow = SlowTransport()
    link = make_link(spp_factory=lambda **kw: slow)
    link._stop.set()                     # as if stop() ran mid-start
    assert link._start_spp() is False
    assert slow.stopped, 'a transport adopted after stop() would never be closed'
    assert link._spp is None


# -- runner -----------------------------------------------------------------

def main():
    tests = [(name, fn) for name, fn in sorted(globals().items())
             if name.startswith('test_') and callable(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f'  PASS  {name}')
        except AssertionError as e:
            failed += 1
            print(f'  FAIL  {name}: {e}')
        except Exception as e:                       # noqa: BLE001
            failed += 1
            print(f'  ERROR {name}: {type(e).__name__}: {e}')
    print(f'\n{len(tests) - failed}/{len(tests)} passed')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
