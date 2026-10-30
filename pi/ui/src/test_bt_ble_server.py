#!/usr/bin/env python3
"""Desk test for the BLE transport's bookkeeping, with no Bluetooth and no bless.

Two things about the BLE side are easy to get silently wrong, and both cost the phone a
poll every time they happen:

* a reply is several notifications, so if two replies are ever sent at the same time their
  chunks interleave and the central reads a line that is half one answer and half another;
* a half-received line left behind by a central that vanished is spliced onto the next
  central's first request, which is then consumed as garbage.

Both are timing bugs, so they are pinned here rather than left to a car.

    python3 test_bt_ble_server.py
    pytest test_bt_ble_server.py
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bt_ble_server import (BleServer, MAX_PENDING_REPLIES,  # noqa: E402
                           PEER_GAP_SECONDS)
from link_service import LinkService  # noqa: E402
from test_link_protocol import FakeDisplayApp, TOKEN  # noqa: E402


def _server(**kwargs):
    return BleServer(LinkService(FakeDisplayApp()), token=TOKEN, **kwargs)


def _feed(server, text):
    """Deliver one write to the server the way bless does, returning the replies queued."""
    sent = []
    server._notify_soon = sent.append
    server._on_write(None, text.encode('utf-8') if isinstance(text, str) else text)
    return [json.loads(payload.decode()) for payload in sent]


def _hello(**extra):
    request = {'id': 1, 'op': 'hello', 'token': TOKEN}
    request.update(extra)
    return json.dumps(request) + '\n'


# -- writes and replies -------------------------------------------------------

def test_a_write_is_answered():
    server = _server()
    replies = _feed(server, _hello())
    assert len(replies) == 1
    assert replies[0]['ok'] is True
    assert replies[0]['data']['authenticated'] is True


def test_a_request_split_across_two_writes_is_reassembled():
    """A 40-byte request does not fit one 20-byte write when the MTU is at its floor."""
    server = _server()
    line = _hello()
    half = len(line) // 2
    assert _feed(server, line[:half]) == []
    replies = _feed(server, line[half:])
    assert len(replies) == 1 and replies[0]['ok'] is True


def test_the_writes_counter_is_kept_for_diagnostics():
    server = _server()
    _feed(server, _hello())
    assert server._writes == 1


# -- a fragment left behind by a vanished central -----------------------------

def test_a_fragment_from_a_dead_central_does_not_eat_the_next_request():
    """The old behaviour glued the two halves together and the new request vanished."""
    server = _server()
    _feed(server, '{"id":9,"op":"te')          # a central that then went away

    # Stand in for the silence: the app polls several times a second, so a fragment this
    # old cannot belong to a live request.
    server._last_write -= PEER_GAP_SECONDS + 1

    replies = _feed(server, '{"id":2,"op":"hello","token":"%s"}\n' % TOKEN)
    assert len(replies) == 1, "the stale fragment ate the request"
    assert replies[0]['id'] == 2
    assert replies[0]['ok'] is True


def test_a_fragment_is_kept_within_the_gap():
    """Two halves of one request microseconds apart are normal, and must not be dropped."""
    server = _server()
    line = _hello()
    half = len(line) // 2
    _feed(server, line[:half])
    replies = _feed(server, line[half:])
    assert len(replies) == 1 and replies[0]['ok'] is True


# -- reply ordering -----------------------------------------------------------

def test_replies_are_sent_one_at_a_time_in_order():
    """Chunks of two replies must never interleave, whatever the MTU makes them cost."""
    server = _server()
    log = []

    async def scenario():
        server._loop = asyncio.get_running_loop()
        server._replies = asyncio.Queue(maxsize=MAX_PENDING_REPLIES)

        async def fake_notify(payload):
            log.append(('start', payload))
            await asyncio.sleep(0.01)          # stands in for several chunks
            log.append(('end', payload))

        server._notify = fake_notify
        drain = asyncio.ensure_future(server._drain_replies())
        server._notify_soon(b'first')
        server._notify_soon(b'second')
        for _ in range(200):
            if len(log) >= 4:
                break
            await asyncio.sleep(0.005)
        drain.cancel()

    asyncio.run(scenario())
    assert log == [('start', b'first'), ('end', b'first'),
                   ('start', b'second'), ('end', b'second')], log


def test_a_reply_is_dropped_rather_than_queued_without_bound():
    """A central that stopped reading must not make the queue grow for ever."""
    server = _server()

    async def scenario():
        server._loop = asyncio.get_running_loop()
        server._replies = asyncio.Queue(maxsize=2)
        for payload in (b'a', b'b', b'c'):
            await server._enqueue(payload)
        return server._replies.qsize()

    assert asyncio.run(scenario()) == 2


def test_a_reply_with_no_loop_is_dropped_quietly():
    """The transport can be written to before its loop exists; that must not raise."""
    server = _server()
    server._notify_soon(b'orphan')       # no loop, no queue: a logged drop, not a crash


# -- notification size --------------------------------------------------------

class _Host:
    """Stands in for the bless server and the TX characteristic."""

    def __init__(self, limit):
        self.limit = limit
        self.value = b''
        self.sent = []

    def get_characteristic(self, uuid):
        return self

    def update_value(self, service, uuid):
        if len(self.value) > self.limit:
            raise RuntimeError('notification larger than this MTU allows')
        self.sent.append(bytes(self.value))


def test_a_refused_notification_is_retried_smaller():
    """A phone that did not negotiate a large MTU must still get its reply.

    Nothing in the Python API reports the negotiated MTU, so the only way to find the
    ceiling is to be refused by it.
    """
    server = _server()
    host = _Host(limit=20)               # the floor every phone supports
    server._server = host

    payload = b'{"id":1,"ok":true,"data":{"rpm":3200,"coolant_f":190}}\n'
    asyncio.run(server._notify(payload))

    assert b''.join(host.sent) == payload, "the reply was not delivered whole"
    assert max(len(chunk) for chunk in host.sent) <= 20


def test_a_reply_that_cannot_be_sent_at_all_is_abandoned_quietly():
    """Below 20 bytes there is nothing legal to send, so give up rather than loop."""
    server = _server()
    host = _Host(limit=4)
    server._server = host
    asyncio.run(server._notify(b'x' * 100))
    assert host.sent == []


# -- runner -------------------------------------------------------------------

def main():
    tests = [(name, fn) for name, fn in sorted(globals().items())
             if name.startswith('test_') and callable(fn)]
    failures = []
    for name, fn in tests:
        try:
            fn()
            print("  PASS  %s" % name)
        except Exception as e:
            failures.append(name)
            print("  FAIL  %s: %s: %s" % (name, type(e).__name__, e))
    print("\n%d/%d passed" % (len(tests) - len(failures), len(tests)))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
