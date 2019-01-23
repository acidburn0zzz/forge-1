# Copyright (C) 2013 Internet Systems Consortium.
#
# Permission to use, copy, modify, and distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND INTERNET SYSTEMS CONSORTIUM
# DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL
# INTERNET SYSTEMS CONSORTIUM BE LIABLE FOR ANY SPECIAL, DIRECT,
# INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING
# FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT,
# NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION
# WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

# Author: Wlodzimierz Wencel
import sys

if 'pytest' in sys.argv[0]:
    from features.lettuce_compat import step
else:
    from lettuce import step

#
# This file contains a number of common steps that are general and may be used
# By a lot of feature files.
#


@step('References: (\S+).')
def references_check(step, references):
    assert len(references), "References cannot be empty."


@step('Tags: (\S+)')
def tags_check(step, tags):
    assert len(tags), "Tags cannot be empty."
