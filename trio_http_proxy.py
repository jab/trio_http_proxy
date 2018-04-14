#!/usr/bin/env python3

# Copyright 2018 Joshua Bronson. All Rights Reserved.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Simple HTTP CONNECT proxy implemented with trio: https://trio.readthedocs.io

Tested with Python 3.6 and Trio 0.3.0.

Instructions:

#. In one terminal, run this script to start the proxy on port 8080:

       $ ./trio_http_proxy.py
       * Starting HTTP proxy on port 8080...

   (You can set the PORT env var to use a different port if you prefer.)

#. In another terminal, make an HTTPS request through the proxy, e.g.

       $ curl -x http://127.0.0.1:8080 https://canhazip.com

   You should get the response you were expecting from the destination server,
   and should see output in the first terminal about the forwarded data, e.g.

       [conn1] Got CONNECT request for canhazip.com
       [conn1] Connected to canhazip.com, sending 200 response...
       [conn1] Sent "200 Connection established" to client
       [conn1 -> canhazip.com] Forwarded 196 bytes
       [conn1 <- canhazip.com] Forwarded 2954 bytes
       ...

#. For even moar proxy amaze,
   configure your OS or web browser to use the proxy,
   and then try browsing to some HTTPS websites.
   It works! 💪

   HTTP sites won't work because the proxy only handles HTTP CONNECT requests.
   But http is weak sauce anyways. 🤓

#. When you're done, just hit Ctrl+C to kill the server.
   Don't forget to restore any proxy settings you changed
   to how they were set before.

"""

from itertools import count
from functools import partial
from os import getenv
from textwrap import indent
from traceback import format_exc

import trio


PORT = int(getenv('PORT', 8080))
DEFAULT_BUFLEN = 16384
indented = partial(indent, prefix='  ')
decoded_and_indented = lambda some_bytes: indented(some_bytes.decode())


async def start_server(port=PORT):
    print(f'* Starting HTTP proxy on port {port or "(OS-chosen available port)"}...')
    try:
        await trio.serve_tcp(http_proxy, port)
    except KeyboardInterrupt:
        print('\nGoodbye for now.')


async def http_proxy(client_stream, _identgen=count(1)):
    ident = next(_identgen)
    async with client_stream:
        try:
            dest_stream, dest = await tunnel(client_stream, log=mklog(f'conn{ident}'))
            async with dest_stream, trio.open_nursery() as nursery:
                nursery.start_soon(pipe, client_stream, dest_stream, mklog(f'conn{ident} -> {dest}'))
                nursery.start_soon(pipe, dest_stream, client_stream, mklog(f'conn{ident} <- {dest}'))
        except Exception:
            print(f'[conn{ident}]:\n{indented(format_exc())}')


async def tunnel(client_stream, log=print):
    """Given a stream from a client containing an HTTP CONNECT request,
    open a connection to the destination server specified in the CONNECT request,
    and notify the client when the end-to-end connection has been established.
    Return the destination stream and the corresponding host.
    """
    dest = await read_and_get_dest_from_http_connect_request(client_stream, log=log)
    log(f'Got CONNECT request for {dest}, connecting...')
    dest_stream = await trio.open_tcp_stream(dest, 443)
    log(f'Connected to {dest}, sending 200 response...')
    await client_stream.send_all(b'HTTP/1.1 200 Connection established\r\n\r\n')
    log('Sent "200 Connection established" to client, tunnel established.')
    return dest_stream, dest


async def read_and_get_dest_from_http_connect_request(stream, maxlen=256, log=print):
    """Read a stream expected to contain a valid HTTP CONNECT request to desthost:443.
    Parse and return the destination host. Validate (lightly) and raise if request invalid.
    """
    log(f'Reading...')
    bytes_read = await stream.receive_some(maxlen)
    assert bytes_read.endswith(b'\r\n\r\n'), f'CONNECT request did not fit in {maxlen} bytes?\n{decoded_and_indented(bytes_read)}'
    split = bytes_read.split(maxsplit=2)
    assert len(split) == 3, f'No "CONNECT foo:443 HTTP/1.1"?\n{decoded_and_indented(bytes_read)}'
    connect, dest, _ = split
    assert connect == b'CONNECT', f'{connect}\n{decoded_and_indented(bytes_read)}'
    assert dest.endswith(b':443'), f'{dest}\n{decoded_and_indented(bytes_read)}'
    return dest[:-4].decode()


async def pipe(from_stream, to_stream, log=print, buflen=DEFAULT_BUFLEN):
    while True:
        chunk = await from_stream.receive_some(buflen)
        if not chunk:
            break
        await to_stream.send_all(chunk)
        log(f'Forwarded {len(chunk)} bytes')


def mklog(tag):
    def log(*args, **kw):
        print(f'[{tag}]', *args, **kw)
    return log


if __name__ == '__main__':
    trio.run(start_server)
