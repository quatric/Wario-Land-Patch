"""Minimal GDB remote-serial-protocol client for Dolphin's GDB stub."""
import socket
import sys
import time


class Gdb:
    def __init__(self, host='127.0.0.1', port=2163, timeout=15):
        self.s = socket.create_connection((host, port), timeout=timeout)
        self.s.settimeout(timeout)
        self._timeout = timeout
        self.buf = b''

    def _cksum(self, body):
        return sum(body) & 0xFF

    def send(self, body):
        b = body.encode()
        pkt = b'$' + b + b'#' + ('%02x' % self._cksum(b)).encode()
        self.s.sendall(pkt)

    def raw(self, data):
        self.s.sendall(data)

    def recv(self):
        while True:
            while b'$' not in self.buf or b'#' not in self.buf.split(b'$', 1)[1]:
                chunk = self.s.recv(4096)
                if not chunk:
                    raise EOFError('gdb stub closed')
                self.buf += chunk
            pre, rest = self.buf.split(b'$', 1)
            body, rest2 = rest.split(b'#', 1)
            if len(rest2) < 2:
                self.buf += self.s.recv(4096)
                continue
            self.buf = rest2[2:]
            self.s.sendall(b'+')
            return body.decode(errors='replace')

    def cmd(self, body):
        self.send(body)
        return self.recv()

    def drain(self, secs=0.4):
        end = time.time() + secs
        self.s.settimeout(0.2)
        try:
            while time.time() < end:
                try:
                    chunk = self.s.recv(4096)
                    if not chunk:
                        break
                except socket.timeout:
                    break
        finally:
            self.s.settimeout(self._timeout)
        self.buf = b''

    def read_mem(self, addr, length):
        out = b''
        off = 0
        while off < length:
            n = min(256, length - off)
            r = None
            for attempt in range(3):
                r = self.cmd('m%x,%x' % (addr + off, n))
                if r and not r.startswith('E'):
                    break
                time.sleep(0.2)
                self.drain(0.2)
            if not r or r.startswith('E'):
                raise RuntimeError('read %08X+%X failed: %r' % (addr + off, n, r))
            out += bytes.fromhex(r)
            off += n
        return out

    def interrupt(self):
        self.raw(b'\x03')
        time.sleep(0.5)
        try:
            r = self.recv()
        except Exception:
            r = None
        self.drain(0.5)
        return r

    def cont(self):
        self.send('c')

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass
