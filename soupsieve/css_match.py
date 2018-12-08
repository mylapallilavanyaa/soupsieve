"""CSS matcher."""
from . import util
import re

# Empty tag pattern (whitespace okay)
RE_NOT_EMPTY = re.compile('[^ \t\r\n]')

# Relationships
REL_PARENT = ' '
REL_CLOSE_PARENT = '>'
REL_SIBLING = '~'
REL_CLOSE_SIBLING = '+'

# Relationships for :has() (forward looking)
REL_HAS_PARENT = ': '
REL_HAS_CLOSE_PARENT = ':>'
REL_HAS_SIBLING = ':~'
REL_HAS_CLOSE_SIBLING = ':+'


class CSSMatch:
    """Perform CSS matching."""

    def __init__(self, selectors, namespaces, mode):
        """Initialize."""

        self.selectors = selectors
        self.namespaces = namespaces
        self.mode = mode

    def get_namespace(self, el):
        """Get the namespace for the element."""

        namespace = ''
        ns = el.namespace
        if ns:
            namespace = ns
        return namespace

    def supports_namespaces(self):
        """Check if namespaces are supported in the HTML type."""

        return self.mode in (util.HTML5, util.XHTML, util.XML)

    def is_xml(self):
        """Check if document is an XML type."""

        return self.mode in (util.XHTML, util.XML)

    def get_attribute(self, el, attr, prefix):
        """Get attribute from element if it exists."""

        value = None
        is_xml = self.is_xml()
        if self.supports_namespaces():
            value = None
            # If we have not defined namespaces, we can't very well find them, so don't bother trying.
            if prefix and prefix not in self.namespaces and prefix != '*':
                return None

            for k, v in el.attrs.items():
                parts = k.split(':', 1)
                if len(parts) > 1:
                    if not parts[0]:
                        a = k
                        p = ''
                    else:
                        p = parts[0]
                        a = parts[1]
                else:
                    p = ''
                    a = k
                # Can't match a prefix attribute as we haven't specified one to match
                if not prefix and p:
                    continue
                # We can't match our desired prefix attribute as the attribute doesn't have a prefix
                if prefix and not p and prefix != '*':
                    continue
                if is_xml:
                    # The prefix doesn't match
                    if prefix and p and prefix != '*' and prefix != p:
                        continue
                    # The attribute doesn't match.
                    if attr != a:
                        continue
                else:
                    # The prefix doesn't match
                    if prefix and p and prefix != '*' and util.lower(prefix) != util.lower(p):
                        continue
                    # The attribute doesn't match.
                    if util.lower(attr) != util.lower(a):
                        continue
                value = v
                break
        else:
            for k, v in el.attrs.items():
                if util.lower(attr) != util.lower(k):
                    continue
                value = v
                break
        return value

    def get_classes(self, el):
        """Get classes."""

        if self.mode not in (util.XHTML, util.XML):
            return el.attrs.get('class', [])
        else:
            return [c for c in el.attrs.get('class', '').strip().split(' ') if c]

    def match_namespace(self, el, tag):
        """Match the namespace of the element."""

        match = True
        namespace = self.get_namespace(el)
        default_namespace = self.namespaces.get('')
        # We must match the default namespace if one is not provided
        if tag.prefix is None and (default_namespace is not None and namespace != default_namespace):
            match = False
        # If we specified `|tag`, we must not have a namespace.
        elif (tag.prefix is not None and tag.prefix == '' and namespace):
            match = False
        # Verify prefix matches
        elif (
            tag.prefix and
            tag.prefix != '*' and namespace != self.namespaces.get(tag.prefix, '')
        ):
            match = False
        return match

    def match_attributes(self, el, attributes):
        """Match attributes."""

        match = True
        if attributes:
            for a in attributes:
                value = self.get_attribute(el, a.attribute, a.prefix)
                if isinstance(value, list):
                    value = ' '.join(value)
                if a.pattern is None and value is None:
                    match = False
                    break
                elif a.pattern is not None and value is None:
                    match = False
                    break
                elif a.pattern is None:
                    continue
                elif value is None or a.pattern.match(value) is None:
                    match = False
                    break
        return match

    def match_tagname(self, el, tag):
        """Match tag name."""

        return not (
            tag.name and
            tag.name not in ((util.lower(el.name) if not self.is_xml() else el.name), '*')
        )

    def match_tag(self, el, tags):
        """Match the tag."""

        has_ns = self.supports_namespaces()
        match = True
        for t in tags:
            # Verify namespace
            if has_ns and not self.match_namespace(el, t):
                match = False
                break
            if not self.match_tagname(el, t):
                match = False
                break
        return match

    def match_past_relations(self, el, relation):
        """Match past relationship."""

        found = False
        if relation.rel_type == REL_PARENT:
            parent = el.parent
            while not found and parent:
                found = self.match_selectors(parent, [relation])
                parent = parent.parent
        elif relation.rel_type == REL_CLOSE_PARENT:
            parent = el.parent
            if parent:
                found = self.match_selectors(parent, [relation])
        elif relation.rel_type == REL_SIBLING:
            sibling = el.previous_sibling
            while not found and sibling:
                if not isinstance(sibling, util.TAG):
                    sibling = sibling.previous_sibling
                    continue
                found = self.match_selectors(sibling, [relation])
                sibling = sibling.previous_sibling
        elif relation.rel_type == REL_CLOSE_SIBLING:
            sibling = el.previous_sibling
            while sibling and not isinstance(sibling, util.TAG):
                sibling = sibling.previous_sibling
            if sibling and isinstance(sibling, util.TAG):
                found = self.match_selectors(sibling, [relation])
        return found

    def match_future_child(self, parent, relation, recursive=False):
        """Match future child."""

        match = False
        for child in (parent.descendants if recursive else parent.children):
            if not isinstance(child, util.TAG):
                continue
            match = self.match_selectors(child, [relation])
            if match:
                break
        return match

    def match_future_relations(self, el, relation):
        """Match future relationship."""

        found = False
        if relation.rel_type == REL_HAS_PARENT:
            found = self.match_future_child(el, relation, True)
        elif relation.rel_type == REL_HAS_CLOSE_PARENT:
            found = self.match_future_child(el, relation)
        elif relation.rel_type == REL_HAS_SIBLING:
            sibling = el.next_sibling
            while not found and sibling:
                if not isinstance(sibling, util.TAG):
                    sibling = sibling.next_sibling
                    continue
                found = self.match_selectors(sibling, [relation])
                sibling = sibling.next_sibling
        elif relation.rel_type == REL_HAS_CLOSE_SIBLING:
            sibling = el.next_sibling
            while sibling and not isinstance(sibling, util.TAG):
                sibling = sibling.next_sibling
            if sibling and isinstance(sibling, util.TAG):
                found = self.match_selectors(sibling, [relation])
        return found

    def match_relations(self, el, relation):
        """Match relationship to other elements."""

        found = False

        if relation.rel_type.startswith(':'):
            found = self.match_future_relations(el, relation)
        else:
            found = self.match_past_relations(el, relation)

        return found

    def match_id(self, el, ids):
        """Match element's ID."""

        found = True
        for i in ids:
            if i != el.attrs.get('id', ''):
                found = False
                break
        return found

    def match_classes(self, el, classes):
        """Match element's classes."""

        current_classes = self.get_classes(el)
        found = True
        for c in classes:
            if c not in current_classes:
                found = False
                break
        return found

    def match_root(self, el):
        """Match element as root."""

        parent = el.parent
        return parent and not parent.parent

    def match_nth_tag_type(self, el, child):
        """Match tag type for `nth` matches."""

        return(
            (child.name == (util.lower(el.name) if not self.is_xml() else el.name)) and
            (self.supports_namespaces() and self.get_namespace(child) == self.get_namespace(el))
        )

    def match_nth(self, el, nth):
        """Match `nth` elements."""

        matched = True

        for n in nth:
            matched = False
            if not el.parent:
                break
            if n.selectors and not self.match_selectors(el, n.selectors):
                break
            parent = el.parent
            last = n.last
            last_index = len(parent.contents) - 1
            relative_index = 0
            a = n.a
            b = n.b
            var = n.n
            count = 0
            count_incr = 1
            factor = -1 if last else 1
            index = len(parent.contents) - 1 if last else 0
            idx = last_idx = a * count + b if var else a

            # We can only adjust bounds within a variable index
            if var:
                # Abort if our nth index is out of bounds and only getting further out of bounds as we increment.
                # Otherwise, increment to try to get in bounds.
                while idx < 1 or idx > last_index:
                    diff_low = 0 - idx
                    if idx < 0:
                        count += count_incr
                        idx = last_idx = a * count + b if var else a
                        diff = 0 - idx
                        if diff >= diff_low:
                            break
                        diff_low = diff
                    diff_high = idx - last_index
                    if idx > last_index:
                        count += count_incr
                        idx = last_idx = a * count + b if var else a
                        diff = idx - last_index
                        if diff >= diff_high:
                            break
                        diff_high = diff

                # If a < 0, our count is working backwards, so floor the index by increasing the count.
                # Find the count that yields the lowest, in bound value and use that.
                # Lastly reverse count increment so that we'll increase our index.
                lowest = count
                if a < 0:
                    while idx >= 1:
                        lowest = count
                        count += count_incr
                        idx = last_idx = a * count + b if var else a
                    count_incr = -1
                count = lowest
                idx = last_idx = a * count + b if var else a

            # Evaluate elements while our calculated nth index is still in range
            while 1 <= idx <= last_index:
                child = None
                # Evaluate while our child index is still range.
                while 0 <= index <= last_index:
                    child = parent.contents[index]
                    index += factor
                    if not isinstance(child, util.TAG):
                        continue
                    # Handle `of S` in `nth-child`
                    if n.selectors and not self.match_selectors(child, n.selectors):
                        continue
                    # Handle `of-type`
                    if n.type and not self.match_nth_tag_type(el, child):
                        continue
                    relative_index += 1
                    if relative_index == idx:
                        if child is el:
                            matched = True
                        else:
                            break
                    if child is el:
                        break
                if child is el:
                    break
                last_idx = idx
                count += count_incr
                if count < 0:
                    # Count is counting down and has now ventured into invalid territory.
                    break
                idx = a * count + b if var else a
                if last_idx == idx:
                    break
            if not matched:
                break
        return matched

    def has_child(self, el):
        """Check if element has child."""

        found_child = False
        for child in el.children:
            if isinstance(child, util.CHILD):
                found_child = True
                break
        return found_child

    def match_empty(self, el, is_empty):
        """Check if element is empty (if requested)."""

        return not is_empty or (RE_NOT_EMPTY.search(el.text) is None and not self.has_child(el))

    def match_selectors(self, el, selectors):
        """Check if element matches one of the selectors."""

        match = False
        is_html = self.mode != util.XML
        for selector in selectors:
            match = selector.is_not
            # Verify tag matches
            if not self.match_tag(el, selector.tags):
                continue
            # Verify `nth` matches
            if not self.match_nth(el, selector.nth):
                continue
            if not self.match_empty(el, selector.is_empty):
                continue
            # Verify id matches
            if is_html and selector.ids and not self.match_id(el, selector.ids):
                continue
            # Verify classes match
            if is_html and selector.classes and not self.match_classes(el, selector.classes):
                continue
            # Verify attribute(s) match
            if not self.match_attributes(el, selector.attributes):
                continue
            if selector.is_root and not self.match_root(el):
                continue
            # Verify pseudo selector patterns
            if selector.selectors and not self.match_selectors(el, selector.selectors):
                continue
            # Verify relationship selectors
            if selector.relation and not self.match_relations(el, selector.relation):
                continue
            match = not selector.is_not
            break

        return match

    def match(self, el):
        """Match."""

        return isinstance(el, util.TAG) and self.match_selectors(el, self.selectors)