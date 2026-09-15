#!/usr/bin/env python3
"""
A small, targeted FEEL (Friendly Enough Expression Language) parser --
not a general-purpose FEEL implementation, just enough grammar to cover
every construct actually present in this program's DMN files (surveyed
directly from all four case studies' .dmn XML before writing this, not
assumed from the DMN spec in the abstract). Two entry points:

  parse_unary_test(text, column_var) -> predicate node
      For one <inputEntry> cell in a decision table row. `column_var` is
      that column's own bound variable name (its <inputExpression> text),
      since a FEEL unary test is implicitly "the column's value <test>",
      e.g. "> 80" means "columnVar > 80", a bare "true" means
      "columnVar = true".

  parse_expression(text) -> expression node
      For a literal-expression decision's formula (arithmetic, a
      comparison, an if/then/else, or a function call) -- used both to
      represent that decision's own value and, when another decision's
      DRD edge points at it, to inline (substitute) it into a downstream
      branch's condition tree per design doc §6.1.

Node vocabulary (deliberately the same shape the design doc's own §6.1
worked example JSON uses, extended only as far as the actual survey
required):
  {"kind": "variable", "ref": name}
  {"kind": "literal", "value": v, "type": "number"|"string"|"boolean"}
  {"op": "="|"!="|"<"|"<="|">"|">=", "left": expr, "right": expr}
  {"op": "and"|"or", "clauses": [expr, ...]}
  {"op": "not", "clause": expr}
  {"op": "in", "left": expr, "values": [expr, ...]}
  {"op": "between", "left": expr, "low": expr, "high": expr}   -- FEEL [a..b], inclusive both ends
  {"op": "+"|"-"|"*"|"/", "left": expr, "right": expr}
  {"op": "if", "cond": expr, "then": expr, "else": expr}
  {"kind": "call", "name": fname, "args": [expr, ...]}
  {"kind": "opaque_formula", "feel_text": raw, "free_variables": [...]}
      -- the honest fallback for FEEL this parser doesn't cover (list
      filters/comprehensions: "x for x in list where cond return expr").
      Surveyed occurrence: exactly one, Spree's "Prior Completed Order
      Count" (`count(order for order in store.orders where ...)`) -- kept
      structurally as a call's argument (so "it's a count(...)" is still
      visible) rather than opaquing the whole expression.

Known, deliberate non-coverage (never silently mis-parsed -- raises
UnsupportedFeelConstruct, caught by the one call site that needs the
opaque-formula fallback): quantified expressions (some/every...satisfies),
FEEL built-in functions beyond count/intersection (sum/min/max/etc. would
parse structurally as an ordinary call node -- that part *is* covered --
but their semantics are never interpreted here, only carried as a name).
"""
import re


class UnsupportedFeelConstruct(Exception):
    pass


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

TOKEN_RE = re.compile(r"""
    \s*(?:
        (?P<STRING>"(?:[^"\\]|\\.)*")
      | (?P<NUMBER>-?\d+\.\d+|-?\d+)
      | (?P<OP><=|>=|!=|\.\.|[<>=+\-*/(),])
      | (?P<IDENT>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)
      | (?P<LBRACKET>\[)
      | (?P<RBRACKET>\])
    )
""", re.VERBOSE)

KEYWORDS = {'true', 'false', 'not', 'if', 'then', 'else', 'for', 'in', 'where',
            'return', 'and', 'or'}


def tokenize(text):
    tokens = []
    pos = 0
    while pos < len(text):
        m = TOKEN_RE.match(text, pos)
        if not m or m.end() == pos:
            if text[pos:].strip() == '':
                break
            raise UnsupportedFeelConstruct(f"unrecognized token at {pos!r} in {text!r}")
        pos = m.end()
        kind = m.lastgroup
        val = m.group(kind)
        tokens.append((kind, val))
    return tokens


# ---------------------------------------------------------------------------
# Parser -- hand-written recursive descent over the token list, with an
# explicit index cursor so the "for ... in ... where ..." special case
# (inside parse_call_args) can capture raw text by re-slicing the original
# string rather than trying to re-serialize tokens.
# ---------------------------------------------------------------------------

class _Parser:
    def __init__(self, text):
        self.text = text
        self.tokens = tokenize(text)
        self.i = 0

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else (None, None)

    def advance(self):
        tok = self.peek()
        self.i += 1
        return tok

    def expect(self, val):
        kind, v = self.advance()
        if v != val:
            raise UnsupportedFeelConstruct(f"expected {val!r}, got {v!r} in {self.text!r}")

    def at_end(self):
        return self.i >= len(self.tokens)

    # expression ::= if_expr | comparison
    def parse_expression(self):
        kind, val = self.peek()
        if val == 'if':
            return self._parse_if()
        return self._parse_comparison()

    def _parse_if(self):
        self.expect('if')
        cond = self._parse_comparison()
        self.expect('then')
        then_e = self.parse_expression()
        self.expect('else')
        else_e = self.parse_expression()
        return {'op': 'if', 'cond': cond, 'then': then_e, 'else': else_e}

    _COMPARISON_OPS = {'=', '!=', '<', '<=', '>', '>='}

    def _parse_comparison(self):
        left = self._parse_additive()
        kind, val = self.peek()
        if val in self._COMPARISON_OPS:
            self.advance()
            right = self._parse_additive()
            return {'op': val, 'left': left, 'right': right}
        return left

    def _parse_additive(self):
        left = self._parse_multiplicative()
        while self.peek()[1] in ('+', '-'):
            op = self.advance()[1]
            right = self._parse_multiplicative()
            left = {'op': op, 'left': left, 'right': right}
        return left

    def _parse_multiplicative(self):
        left = self._parse_primary()
        while self.peek()[1] in ('*', '/'):
            op = self.advance()[1]
            right = self._parse_primary()
            left = {'op': op, 'left': left, 'right': right}
        return left

    def _parse_primary(self):
        kind, val = self.peek()
        if kind == 'NUMBER':
            self.advance()
            return {'kind': 'literal', 'value': float(val) if '.' in val else int(val), 'type': 'number'}
        if kind == 'STRING':
            self.advance()
            return {'kind': 'literal', 'value': val[1:-1], 'type': 'string'}
        if val in ('true', 'false'):
            self.advance()
            return {'kind': 'literal', 'value': val == 'true', 'type': 'boolean'}
        if val == '(':
            self.advance()
            inner = self.parse_expression()
            self.expect(')')
            return inner
        if kind == 'IDENT':
            self.advance()
            if self.peek()[1] == '(':
                return self._parse_call(val)
            return {'kind': 'variable', 'ref': val}
        raise UnsupportedFeelConstruct(f"unexpected token {val!r} in {self.text!r}")

    def _parse_call(self, name):
        self.expect('(')
        args = []
        if self.peek()[1] != ')':
            args.append(self._parse_call_arg())
            while self.peek()[1] == ',':
                self.advance()
                args.append(self._parse_call_arg())
        self.expect(')')
        return {'kind': 'call', 'name': name, 'args': args}

    def _parse_call_arg(self):
        """One function-call argument -- normally an ordinary expression,
        except FEEL's list-filter/comprehension form ("x for x in list
        where cond") isn't expression-shaped at all. Detected by trying an
        ordinary expression parse first and falling back to capturing the
        raw text up to the argument's own closing delimiter (','/')' at
        this nesting depth) as an opaque_formula if that hits a 'for'
        keyword this grammar doesn't otherwise accept as an expression start.
        """
        start_i = self.i
        try:
            expr = self.parse_expression()
            # A normal expression parse can succeed on just a prefix of a
            # FEEL comprehension ("order for order in ...": "order" alone
            # is already a valid identifier expression) and still leave a
            # dangling 'for' the grammar doesn't accept as an argument
            # separator -- that's the comprehension case too, not just an
            # outright parse failure.
            if self.peek()[1] != 'for':
                return expr
        except UnsupportedFeelConstruct:
            pass
        # Fallback: scan raw tokens from start_i to the matching ','/')' at
        # depth 0, treating that whole span as opaque.
        self.i = start_i
        depth = 0
        raw_tokens = []
        while not self.at_end():
            kind, val = self.peek()
            if val == '(':
                depth += 1
            elif val == ')':
                if depth == 0:
                    break
                depth -= 1
            elif val == ',' and depth == 0:
                break
            raw_tokens.append(val)
            self.advance()
        free_vars = sorted({t for t in raw_tokens
                             if re.match(r'^[A-Za-z_]', t) and t not in KEYWORDS})
        return {'kind': 'opaque_formula', 'feel_text': ' '.join(raw_tokens),
                'free_variables': free_vars}


def parse_expression(text):
    """Parses a literal-expression decision's formula. Never raises for
    input covered by the grammar above; anything else propagates
    UnsupportedFeelConstruct for the caller to decide how to degrade."""
    p = _Parser(text)
    node = p.parse_expression()
    if not p.at_end():
        raise UnsupportedFeelConstruct(f"trailing tokens after parse: {text!r}")
    return node


# ---------------------------------------------------------------------------
# Unary-test parsing (decision-table input-entry cells)
# ---------------------------------------------------------------------------

def _literal_from_token(kind, val):
    if kind == 'NUMBER':
        return {'kind': 'literal', 'value': float(val) if '.' in val else int(val), 'type': 'number'}
    if kind == 'STRING':
        return {'kind': 'literal', 'value': val[1:-1], 'type': 'string'}
    if val in ('true', 'false'):
        return {'kind': 'literal', 'value': val == 'true', 'type': 'boolean'}
    if kind == 'IDENT':
        return {'kind': 'variable', 'ref': val}
    raise UnsupportedFeelConstruct(f"not a literal/identifier: {val!r}")


def _parse_bound(p):
    """One endpoint of a range, one list element, or a comparison's
    right-hand side: a number, string, boolean, bare identifier
    (cross-variable reference), or a zero/single-arg built-in call
    (surveyed occurrence: "today()", e.g. "<= today()") -- never a full
    arithmetic expression in any construct actually observed."""
    kind, val = p.advance()
    if kind == 'IDENT' and p.peek()[1] == '(':
        return p._parse_call(val)
    return _literal_from_token(kind, val)


def parse_unary_test(text, column_var):
    """Parses one <inputEntry> cell against the column's own bound
    variable (column_var). Returns None for the wildcard "-" (matches
    anything -- not a real constraint, so no predicate node at all)."""
    text = (text or '').strip()
    if text in ('', '-'):
        return None

    left = {'kind': 'variable', 'ref': column_var}
    p = _Parser(text)

    kind, val = p.peek()

    # not(...) : negated list-membership or negated range
    if val == 'not':
        p.advance()
        p.expect('(')
        inner = _parse_test_body(p, left)
        p.expect(')')
        if not p.at_end():
            raise UnsupportedFeelConstruct(f"trailing tokens after not(...): {text!r}")
        return {'op': 'not', 'clause': inner}

    # comparison operators: "> X", ">= X", "<= X", "< X", "!= X"
    if val in ('<', '<=', '>', '>=', '!='):
        p.advance()
        right = _parse_bound(p)
        if not p.at_end():
            raise UnsupportedFeelConstruct(f"trailing tokens: {text!r}")
        return {'op': val, 'left': left, 'right': right}

    node = _parse_test_body(p, left)
    if not p.at_end():
        raise UnsupportedFeelConstruct(f"trailing tokens: {text!r}")
    return node


def _parse_test_body(p, left):
    """Everything a unary test can be once a leading comparison operator
    and 'not(' have already been stripped: a range literal [a..b], a
    comma-separated list (membership test, 1+ elements -- a single bare
    value is just the n=1 case, handled the same way as "= value"), or a
    single bare value (bare boolean/string/number literal, or a bare
    identifier meaning cross-variable equality)."""
    if p.peek()[1] == '[':
        p.advance()
        low = _parse_bound(p)
        p.expect('..')
        high = _parse_bound(p)
        p.expect(']')
        return {'op': 'between', 'left': left, 'low': low, 'high': high}

    values = [_parse_bound(p)]
    while p.peek()[1] == ',':
        p.advance()
        values.append(_parse_bound(p))

    if len(values) == 1:
        return {'op': '=', 'left': left, 'right': values[0]}
    return {'op': 'in', 'left': left, 'values': values}
