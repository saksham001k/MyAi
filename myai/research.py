"""Account-free public web retrieval. Search availability depends on upstream sites."""
import html
import zlib
import xml.etree.ElementTree as ET
import http.client
import ipaddress
import json
import socket
import ssl
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlparse, urljoin, urlencode, parse_qs


class PageText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.links = [], []
        self.hidden = 0
        self.link = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style', 'noscript'):
            self.hidden += 1
        if tag == 'a':
            self.link = [attrs.get('href', ''), []]
        if tag in ('p', 'div', 'br', 'li', 'h1', 'h2', 'h3'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'):
            self.hidden = max(0, self.hidden - 1)
        if tag == 'a' and self.link:
            self.links.append((self.link[0], ' '.join(self.link[1]).strip()))
            self.link = None

    def handle_data(self, value):
        if not self.hidden:
            self.parts.append(value)
            if self.link:
                self.link[1].append(value)

    def text(self):
        return '\n'.join(' '.join(line.split()) for line in ''.join(self.parts).splitlines() if line.strip())


def public_addresses(url):
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Use a public http/https URL without credentials.')
    if parsed.port not in (None, 80, 443):
        raise ValueError('Public research supports standard web ports only.')
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80), type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('Public research cannot access private, loopback or link-local addresses.')
    return parsed, addresses


def retrieve(url, cancel=None):
    # Connect to a validated address, preserving HTTPS hostname verification.
    # This avoids checking one DNS result and connecting to a later private one.
    for _ in range(5):
        if cancel is not None and cancel.is_set():
            raise RuntimeError('Research cancelled.')
        parsed, addresses = public_addresses(url)
        family, socktype, proto, _, address = addresses[0]
        sock = socket.socket(family, socktype, proto)
        sock.settimeout(12)
        connection = None
        try:
            sock.connect(address)
            if parsed.scheme == 'https':
                sock = ssl.create_default_context().wrap_socket(sock, server_hostname=parsed.hostname)
            connection = http.client.HTTPConnection(parsed.hostname, timeout=12)
            connection.sock = sock
            target = parsed.path or '/'
            if parsed.query:
                target += '?' + parsed.query
            connection.request('GET', target, headers={'User-Agent': 'MyAi/0.3 personal research', 'Accept': 'text/html,text/plain,application/json,application/rss+xml', 'Accept-Encoding': 'identity'})
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader('Location')
                if not location:
                    raise ValueError('Redirect has no destination.')
                url = urljoin(url, location)
                continue
            if response.status != 200:
                raise ValueError(f'Website returned HTTP {response.status}. Try another source.')
            kind = response.getheader('Content-Type', '')
            if not any(x in kind for x in ('text/', 'json', 'xhtml', 'xml')):
                raise ValueError('This URL is not a readable text page. Download and attach PDFs separately.')
            data = bytearray()
            while len(data) <= 2_000_000:
                if cancel is not None and cancel.is_set():
                    raise RuntimeError('Research cancelled.')
                chunk = response.read(16384)
                if not chunk:
                    break
                data.extend(chunk)
            if len(data) > 2_000_000:
                raise ValueError('Page exceeds the 2 MB retrieval budget.')
            encoding = response.getheader('Content-Encoding', '').lower()
            if encoding in ('gzip', 'deflate'):
                decoder = zlib.decompressobj(16 + zlib.MAX_WBITS if encoding == 'gzip' else zlib.MAX_WBITS)
                data = decoder.decompress(bytes(data), 2_000_001)
                if len(data) > 2_000_000 or decoder.unconsumed_tail:
                    raise ValueError('Decompressed page exceeds the retrieval budget.')
            elif encoding not in ('', 'identity'):
                raise ValueError('Website returned an unsupported compression format.')
            return url, data.decode('utf-8', 'replace')
        finally:
            if connection:
                connection.close()
            else:
                sock.close()
    raise ValueError('Too many redirects.')


class Research:
    def __init__(self, cancel):
        self.cancel = cancel
        self.sources = []

    def search(self, query):
        if not isinstance(query, str) or not 1 <= len(query) <= 500:
            raise ValueError('Search query must contain 1–500 characters.')
        errors = []
        try:
            _, body = retrieve('https://html.duckduckgo.com/html/?' + urlencode({'q': query}), self.cancel)
            parser = PageText()
            parser.feed(body)
            results, seen = [], set()
            for href, title in parser.links:
                if 'uddg=' in href:
                    href = parse_qs(urlparse(html.unescape(href)).query).get('uddg', [''])[0]
                if href.startswith('http') and 'duckduckgo.com' not in urlparse(href).netloc and title and href not in seen:
                    seen.add(href)
                    results.append({'title': title[:250], 'url': href})
            if results:
                return {'provider': 'DuckDuckGo', 'results': results[:6], 'note': 'Candidates only. Read pages before citing them.'}
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append(str(exc))
        try:
            _, body = retrieve('https://www.bing.com/search?' + urlencode({'q': query, 'format': 'rss'}), self.cancel)
            feed = ET.fromstring(body)
            results = [{'title': item.findtext('title', '')[:250], 'url': item.findtext('link', '')}
                       for item in feed.findall('./channel/item') if item.findtext('link', '').startswith('http')]
            if results:
                return {'provider': 'Bing RSS', 'results': results[:6], 'note': 'Candidates only. Read pages before citing them.'}
        except (OSError, ValueError, RuntimeError, ET.ParseError) as exc:
            errors.append(str(exc))
        raise ValueError('Free search is currently unavailable. Provide a public source URL instead. ' + '; '.join(errors)[:300])

    def fetch(self, url):
        if len(self.sources) >= 8:
            raise ValueError('Eight sources have been read. Finish the report or start a focused follow-up.')
        final_url, body = retrieve(url, self.cancel)
        parser = PageText()
        parser.feed(body)
        content = parser.text()[:12000]
        if not content:
            raise ValueError('No readable content was found.')
        record = {'id': f'S{len(self.sources) + 1}', 'url': final_url,
                  'retrieved_at': datetime.now(timezone.utc).isoformat(), 'text': content}
        self.sources.append(record)
        return record
