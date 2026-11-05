"""Test-only path-prefix adapter; dispatch remains the real ViewHandler.

The shell registers /app/. Production uses its gateway to strip that prefix.
This disposable fixture performs only that rewrite after the real HTTP parser,
without replacing Chromium's requests with Playwright APIRequestContext fetches.
Neither credentials, headers, bodies nor query values are copied into logs.
"""
from web import ViewHandler


class AttachmentFixtureHandler(ViewHandler):
    prefix = '/app/'

    def parse_request(self):
        accepted = super().parse_request()
        if accepted and self.path.startswith(self.prefix):
            self.path = self.path[len(self.prefix) - 1:]
        return accepted
