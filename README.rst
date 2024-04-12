trio_http_proxy.py
==================

Simple HTTP CONNECT proxy implemented with
`Trio <https://trio.readthedocs.io>`__.

Tested with Python 3.12 and Trio 0.25.0
(but other versions probably work too).


Why
---

- An HTTP CONNECT proxy is one of the simplest
  async I/O things you can build
  that does something real.
  Namely, you can load HTTPS sites
  (including streaming YouTube and Netflix)
  through it.

- If you're trying to access content that's restricted by an IP-based geofence,
  you could run this from a machine inside the geofence to get access!

  Note: Please consult the relevant terms and conditions first
  to make sure you wouldn't be breaking the rules.
  😇

  Also note: Many popular streaming services
  blacklist IPs of major cloud hosting providers
  to thwart unauthorized geofence hopping.
  So you'd need to run this from
  `some other hosting provider <http://lowendbox.com>`__.

- I was sold on Trio *before* I saw
  `@njsmith <https://github.com/njsmith>`__
  `live code happy eyeballs in 40 lines of Python
  <https://www.youtube.com/watch?v=i-R704I8ySE>`__.
  🙀

  If you haven't yet read his post,
  `Notes on structured concurrency, or: Go statement considered harmful
  <https://vorpus.org/blog/notes-on-structured-concurrency-or-go-statement-considered-harmful/>`__
  definitely check it out.


Instructions
------------

#. Install Trio and h11 if you haven't already.

   .. code-block::

      uv venv .venv  # create a virtualenv (recommended)
      uv pip install -r requirements-lock.txt  # install dependencies

#. In one shell session, run this script to start the proxy on port 8080:

   .. code-block::

      ./trio_http_proxy.py
      * Starting HTTP proxy on port 8080...

   (You can set the PORT env var to use a different port if you prefer.)

#. In another session, make an HTTPS request through the proxy, e.g.

   .. code-block::

      curl -x http://127.0.0.1:8080 https://canhazip.com

   You should get the response you were expecting from the destination server,
   and should see output from the proxy in the first shell session
   about the forwarded data, e.g.

   .. code-block::

      [conn1] Reading...
      [conn1] Got CONNECT request for canhazip.com, connecting...
      [conn1 <> canhazip.com] Connected to canhazip.com, sending 200 response...
      [conn1 <> canhazip.com] Sent "200 Connection established" to client, tunnel established.
      [conn1 -> canhazip.com] Forwarded 196 bytes
      [conn1 <- canhazip.com] Forwarded 2954 bytes
      ...

#. You can even configure your OS or browser to use the proxy,
   and then try visiting some HTTPS websites as you would normally.
   It works! 💪

   HTTP sites won't work because the proxy only handles HTTP CONNECT requests.
   But HTTP is weak sauce anyways. 🤓

   *A YouTube video streaming through the proxy:*

   .. image:: https://user-images.githubusercontent.com/64992/38785817-c03acd0a-414d-11e8-8f4a-2c5aa27e79e6.png
      :alt: screenshot of a YouTube video streaming through the proxy

   *Changing system proxy settings on macOS:*

   .. image:: https://user-images.githubusercontent.com/64992/38785931-b657d804-414e-11e8-8cfa-e05a11364f7d.png
      :alt: screenshot of changing system proxy settings on macOS

#. When you're done, just hit Ctrl+C to kill the server.
   Don't forget to restore any proxy settings you changed
   to how they were set before.


For a one-liner test that only requires one shell session, run:

.. code-block::

   ./trio_http_proxy.py & sleep 1; curl -x http://127.0.0.1:8080 https://canhazip.com ; kill %1
