"""The Bluetooth line protocol, with no Bluetooth in it.

One JSON object per line, newline terminated, UTF-8. A request names an operation and
carries an id; the reply echoes that id so a client can match them up:

    -> {"id": 7, "op": "telemetry"}
    <- {"id": 7, "ok": true, "data": {"rpm": 3200, ...}}

    -> {"id": 8, "op": "setting", "name": "shift_rpm", "value": 6800}
    <- {"id": 8, "ok": true, "data": {"success": true, "name": "shift_rpm", ...}}

    -> {"id": 9, "op": "roof.mode", "value": 2}
    <- {"id": 9, "ok": true, "data": {...roof status...}}

Why a line protocol rather than HTTP: `BluetoothPan` is @SystemApi, so there is no free
IP-over-Bluetooth, and RFCOMM/BLE both hand you a byte stream instead. Newline framing
works unchanged over either one, and also over a plain TCP socket, which is what makes
this file testable on a desk with no Bluetooth hardware anywhere near it.

Authentication: the first request must be

    -> {"id": 1, "op": "hello", "token": "<access token>"}

Pairing is not treated as the security boundary, because pairing makes a device trusted
for the profile rather than authorising this application's commands. The token is the
same one the HTTP API uses, so one secret covers both transports.
"""

import json
import logging

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = 1

# A peer that never sends a newline must not be able to grow our buffer without bound.
MAX_LINE_BYTES = 8192

# Bad tokens allowed in a row before the link gives up on the peer.
MAX_AUTH_FAILURES = 5


class LinkProtocol:
    """Turns one request line into one reply line, against a LinkService."""

    def __init__(self, service, token=None, require_token=True):
        self.service = service
        self._token = token
        self._require_token = require_token
        self._authed = False
        self._auth_failures = 0

    @property
    def authenticated(self):
        return self._authed

    def handle_line(self, line):
        """Handle one request line. Returns the reply line, or None to stay silent.

        None is only returned for a blank line, which a peer may send as a keepalive.
        """
        line = line.strip()
        if not line:
            return None

        try:
            request = json.loads(line)
        except ValueError:
            return self._error(None, 'Malformed JSON')
        if not isinstance(request, dict):
            return self._error(None, 'Request must be a JSON object')

        req_id = request.get('id')
        op = request.get('op')
        if not isinstance(op, str) or not op:
            return self._error(req_id, 'Missing op')

        # -- authentication --------------------------------------------------

        if op == 'hello':
            return self._hello(request, req_id)

        if self._require_token and not self._authed:
            self._auth_failures += 1
            return self._error(req_id, 'Not authenticated: send hello first')

        # -- dispatch --------------------------------------------------------

        try:
            data = self._dispatch(op, request)
        except Exception as e:
            logger.exception("Link op %r failed", op)
            return self._error(req_id, str(e) or e.__class__.__name__)

        if data is None:
            return self._error(req_id, 'Unknown op: %s' % op)
        return self._ok(req_id, data)

    def _hello(self, request, req_id):
        """Validate the token and report what this link can do."""
        supplied = request.get('token')
        if self._require_token and not self._token_matches(supplied):
            self._auth_failures += 1
            logger.warning("Link auth failure %d", self._auth_failures)
            return self._error(req_id, 'Bad token')
        self._authed = True
        return self._ok(req_id, {
            'protocol': PROTOCOL_VERSION,
            'authenticated': True,
        })

    def _token_matches(self, supplied):
        if self._token is None or supplied is None:
            return False
        # Constant-time compare, same reasoning as the HTTP bearer check.
        import hmac
        return hmac.compare_digest(str(supplied), str(self._token))

    @property
    def auth_failures(self):
        return self._auth_failures

    def exhausted(self):
        """True once the peer has burned through its bad-token allowance."""
        return self._auth_failures >= MAX_AUTH_FAILURES

    def _dispatch(self, op, request):
        """Map an op onto LinkService. Returns the payload, or None if unknown."""
        s = self.service

        # -- reads
        if op == 'ping':
            return {'pong': True, 'protocol': PROTOCOL_VERSION}
        if op == 'status':
            return s.status()
        if op == 'telemetry':
            return s.telemetry()
        if op == 'roof.status':
            return s.roof_status()

        # -- display and settings. The service returns (payload, http_status); the
        # status is an HTTP detail and is dropped here.
        if op == 'screen':
            payload, _ = s.set_screen(self._int(request.get('value')))
            return payload
        if op == 'screen.next':
            payload, _ = s.next_screen()
            return payload
        if op == 'screen.prev':
            payload, _ = s.prev_screen()
            return payload
        if op == 'setting':
            payload, _ = s.update_setting(request.get('name'), request.get('value'))
            return payload
        if op == 'wake':
            payload, _ = s.wake()
            return payload
        if op == 'sleep':
            payload, _ = s.sleep()
            return payload
        if op == 'calibrate_imu':
            payload, _ = s.calibrate_imu()
            return payload

        # -- roof controller
        if op in ('roof.speed', 'roof.auto', 'roof.mode'):
            payload, _ = s.roof_set(op.split('.', 1)[1], self._int(request.get('value')))
            return payload

        return None

    @staticmethod
    def _int(value):
        """Coerce a JSON value for a numeric op, leaving None alone.

        JSON numbers arrive as int/float already; a client that sends "12" as a string,
        which the HTTP API also tolerated, still works.
        """
        if value is None or isinstance(value, int):
            return value
        try:
            return int(value)
        except (TypeError, ValueError):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

    @staticmethod
    def _ok(req_id, data):
        return json.dumps({'id': req_id, 'ok': True, 'data': data},
                          separators=(',', ':'))

    @staticmethod
    def _error(req_id, message):
        return json.dumps({'id': req_id, 'ok': False, 'error': message},
                          separators=(',', ':'))


class LinkSession:
    """One connected peer: buffers bytes, splits lines, feeds the protocol.

    The transport only has to move bytes and call feed() with them; it does not need to
    understand the protocol, and this does not need to know which transport it is.
    """

    def __init__(self, protocol):
        self._protocol = protocol
        self._buf = bytearray()
        self.closed = False
        self.close_reason = None

    def feed(self, chunk):
        """Accept received bytes. Returns a list of reply lines to send, in order."""
        if self.closed:
            return []

        self._buf.extend(chunk)

        replies = []
        while b'\n' in self._buf:
            line, _, rest = self._buf.partition(b'\n')
            self._buf = bytearray(rest)

            if len(line) > MAX_LINE_BYTES:
                # Drop the oversized line rather than the connection: a desynced peer
                # usually recovers on the next newline.
                replies.append(json.dumps(
                    {'id': None, 'ok': False, 'error': 'Line too long'},
                    separators=(',', ':')))
                continue

            reply = self._protocol.handle_line(line.decode('utf-8', 'replace'))
            if reply:
                replies.append(reply)

            if self._protocol.exhausted():
                self.closed = True
                self.close_reason = 'Too many authentication failures'
                break

        return replies

    def pending_bytes(self):
        """Bytes buffered without a newline yet, for a transport that wants to warn."""
        return len(self._buf)

    def reset(self):
        """Forget a partial line, for a transport that reconnects on the same session."""
        self._buf = bytearray()


class StreamLink:
    """Runs the protocol over any duplex byte stream, one peer at a time.

    SPP hands us a socket, BLE hands us chunks from a characteristic write, and a test
    hands us a TCP connection. All three are just "bytes in, bytes out", so all three go
    through this, and the only transport-specific code left is whatever moves the bytes.

    A peer that disconnects resets the session, so the next peer has to authenticate
    again rather than inheriting its predecessor's authentication.
    """

    def __init__(self, service, token=None, require_token=True, label='link'):
        self.service = service
        self.token = token
        self.require_token = require_token
        self.label = label
        self.closed_reason = None
        self.session = None
        self._new_session()

    def _new_session(self):
        self.protocol = LinkProtocol(self.service, self.token, self.require_token)
        self.session = LinkSession(self.protocol)

    def on_bytes(self, data):
        """Feed received bytes. Returns the bytes to send back, newline terminated."""
        if not data:
            return b''
        replies = self.session.feed(data)
        if self.session.closed:
            self.closed_reason = self.session.close_reason
        return b''.join(r.encode('utf-8') + b'\n' for r in replies)

    @property
    def closed(self):
        return self.session.closed

    def reset(self):
        """A peer disconnected: the next one starts unauthenticated."""
        self.closed_reason = None
        self._new_session()
