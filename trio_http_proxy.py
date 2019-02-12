#!/usr/bin/env python3

# Copyright 2018-2019 Joshua Bronson. All Rights Reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from functools import partial
from itertools import count
from os import getenv
from textwrap import indent
from traceback import format_exc

from contextvars import ContextVar
from trio import open_nursery, open_tcp_stream, run, serve_tcp


DEFAULT_PORT = 8080
PORT = int(getenv('PORT', DEFAULT_PORT))  # pylint: disable=invalid-envvar-default
BUFMAXLEN = 16384
OK_CONNECT_PORTS = {443, 8443}

prn = partial(print, end='')  # pylint: disable=C0103
indented = partial(indent, prefix='  ')  # pylint: disable=C0103
decoded_and_indented = lambda some_bytes: indented(some_bytes.decode())  # pylint: disable=C0103

CV_CLIENT_STREAM = ContextVar('client_stream', default=None)
CV_DEST_STREAM = ContextVar('dest_stream', default=None)
CV_PIPE_FROM = ContextVar('pipe_from', default=None)


async def http_proxy(client_stream, _connidgen=count(1)):
    client_stream.id = next(_connidgen)
    CV_CLIENT_STREAM.set(client_stream)
    async with client_stream:
        try:
            dest_stream = await tunnel(client_stream)
            async with dest_stream, open_nursery() as nursery:
                nursery.start_soon(pipe, client_stream, dest_stream)
                nursery.start_soon(pipe, dest_stream, client_stream)
        except Exception:  # pylint: disable=broad-except
            log(f'\n{indented(format_exc())}')


async def start_server(server=http_proxy, port=PORT):
    print(f'* Starting {server.__name__} on port {port or "(OS-selected port)"}...')
    try:
        await serve_tcp(server, port)
    except KeyboardInterrupt:
        print('\nGoodbye for now.')


async def tunnel(client_stream):
    """Given a stream from a client containing an HTTP CONNECT request,
    open a connection to the destination server specified in the CONNECT request,
    and notify the client when the end-to-end connection has been established.
    Return the destination stream and the corresponding host.
    """
    desthost, destport = await process_as_http_connect_request(client_stream)
    log(f'Got CONNECT request for {desthost}:{destport}, connecting...')
    dest_stream = await open_tcp_stream(desthost, destport)
    dest_stream.host = desthost
    dest_stream.port = destport
    CV_DEST_STREAM.set(dest_stream)
    log(f'Connected to {desthost}, sending 200 response...')
    await client_stream.send_all(b'HTTP/1.1 200 Connection established\r\n\r\n')
    log('Sent 200 to client, tunnel established.')
    return dest_stream


async def process_as_http_connect_request(stream, bufmaxlen=BUFMAXLEN):
    """Read a stream expected to contain a valid HTTP CONNECT request to desthost:destport.
    Parse and return the destination host. Validate (lightly) and raise if request invalid.
    See https://tools.ietf.org/html/rfc7231#section-4.3.6 for the CONNECT spec.
    """
    log(f'Reading...')
    bytes_read = await stream.receive_some(bufmaxlen)
    assert bytes_read.endswith(b'\r\n\r\n'), f'CONNECT request did not fit in {bufmaxlen} bytes?\n{decoded_and_indented(bytes_read)}'
    # Only examine the first two tokens (e.g. "CONNECT example.com:443 [ignored...]").
    # The Host header should duplicate the CONNECT request's authority and should therefore be safe
    # to ignore. Plus apparently some clients (iOS, Facebook) don't even send a Host header in
    # CONNECT requests according to https://go-review.googlesource.com/c/go/+/44004.
    split = bytes_read.split(maxsplit=2)
    assert len(split) == 3, f'Expected "<method> <authority> ..."\n{decoded_and_indented(bytes_read)}'
    method, authority, _ = split
    assert method == b'CONNECT', f'Expected "CONNECT", "{method}" unsupported\n{decoded_and_indented(bytes_read)}'
    desthost, colon, destport = authority.partition(b':')
    assert colon and destport, f'Expected ":<port>" in {authority}\n{decoded_and_indented(bytes_read)}'
    destport = int(destport.decode())
    assert destport in OK_CONNECT_PORTS, f'Forbidden destination port: {destport}'
    return desthost.decode(), destport


async def read_all(stream, bufmaxlen=BUFMAXLEN):
    while True:
        chunk = await stream.receive_some(bufmaxlen)
        if not chunk:
            break
        yield chunk


async def pipe(from_stream, to_stream, bufmaxlen=BUFMAXLEN):
    CV_PIPE_FROM.set(from_stream)
    async for chunk in read_all(from_stream, bufmaxlen=bufmaxlen):  # pylint: disable=E1133; https://github.com/PyCQA/pylint/issues/2311
        await to_stream.send_all(chunk)
        log(f'Forwarded {len(chunk)} bytes')
    log(f'Pipe finished')


def log(*args, **kw):
    client_stream = CV_CLIENT_STREAM.get()
    if client_stream:
        prn(f'[conn{client_stream.id}')
        dest_stream = CV_DEST_STREAM.get()
        if dest_stream:
            direction = '<>'
            pipe_from = CV_PIPE_FROM.get()
            if pipe_from:
                direction = '->' if pipe_from is client_stream else '<-'
            prn(f' {direction} {dest_stream.host}')
        prn('] ')
    print(*args, **kw)


if __name__ == '__main__':
    run(start_server)
