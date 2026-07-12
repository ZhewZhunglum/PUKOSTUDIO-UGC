"""Batch public-profile email extraction, ported from the creator-finder
extension's local service (server/profiles.mjs + emailDig.mjs + index.mjs).

Pure parsing/validation logic lives in resolve.py / parsers.py /
email_extract.py so it can be unit tested; IO (httpx fetch, DNS MX lookups)
lives in fetcher.py / mx.py; digger.py wires them together.
"""
