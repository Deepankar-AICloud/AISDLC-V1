"""AISDLC Studio: a self-contained web front door that runs the AISDLC generator directly.

A shared username/password signs users in; each requirement is processed in its own
isolated git clone of the AISDLC repository, so the real working tree is never touched.
"""
