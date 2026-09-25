"""Pure DMN XML structural extraction -- decisions, DRD dependency edges,
decision-table rules (with stable rule IDs and document-order index), and
literal-expression decisions. Plain `xml.etree.ElementTree`, nothing else.

Deliberately independent of `generator/compile_constraints.py` and
`generator/feel_parser.py`: this module extracts STRUCTURE only (which
decisions exist, which ones depend on which, what a rule's raw FEEL text
literally says, in what order) -- it never interprets or translates FEEL
text into evaluable conditions. That is `validation_oracle`'s own
`rule_evaluator.py`'s job, kept separate on purpose (see
`validation_oracle/DESIGN.md`, "Architectural separation requirement").
Extracting structure is not a semantic-translation risk the same way
condition-parsing is, so this module owes nothing to, and shares nothing
with, `generator/`'s own DMN-reading code.

Every case study's `.dmn` files share one namespace, confirmed directly:
`https://www.omg.org/spec/DMN/20191111/MODEL/`.
"""
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

NS = {'dmn': 'https://www.omg.org/spec/DMN/20191111/MODEL/'}


def _tag(local_name):
    return f"{{{NS['dmn']}}}{local_name}"


def _text(elem):
    """The raw FEEL text inside a <text> child, or None if absent (a
    dash/'-' input entry, meaning "any value", is still real text -- an
    ABSENT <text> element, distinct from that, means something malformed
    in the source file and must not be silently treated as a wildcard."""
    child = elem.find(_tag('text'))
    return child.text if child is not None else None


@dataclass
class Column:
    id: str
    label: str | None
    name: str | None  # only outputs declare `name` (the FEEL variable this output binds)
    type_ref: str | None
    expression_text: str | None  # inputs only: the inputExpression's own FEEL text


@dataclass
class Rule:
    id: str
    index: int  # 0-based position in document order -- FIRST hit policy is defined by this order
    input_entries: list  # raw FEEL text per input column, same order as Decision.inputs
    output_entries: list  # raw FEEL text per output column, same order as Decision.outputs
    description: str | None = None


@dataclass
class Decision:
    id: str
    name: str
    kind: str  # 'decision_table' | 'literal_expression' | 'unsupported'
    required_decisions: list = field(default_factory=list)  # decision_ids this one depends on
    hit_policy: str | None = None  # decision_table only
    inputs: list = field(default_factory=list)  # decision_table only, list[Column]
    outputs: list = field(default_factory=list)  # decision_table only, list[Column]
    rules: list = field(default_factory=list)  # decision_table only, list[Rule], document order
    literal_expression_text: str | None = None  # literal_expression only
    output_name: str | None = None  # literal_expression only -- the single <variable name=...>


@dataclass
class DmnModel:
    dmn_file: str
    decisions: dict  # {decision_id: Decision}

    def topological_order(self):
        """Decisions in DRD dependency order -- every decision appears
        after every decision it requires. Raises on a cycle (a real DMN
        model must not have one; silently ignoring a cycle here would be
        exactly the kind of silent fallback this project's own research
        constraints rule out)."""
        order = []
        visiting = set()
        visited = set()

        def visit(decision_id):
            if decision_id in visited:
                return
            if decision_id in visiting:
                raise ValueError(f"DRD cycle detected at {decision_id!r} in {self.dmn_file}")
            visiting.add(decision_id)
            for dep in self.decisions[decision_id].required_decisions:
                if dep not in self.decisions:
                    raise ValueError(
                        f"{decision_id!r} requires {dep!r}, not found in {self.dmn_file}")
                visit(dep)
            visiting.discard(decision_id)
            visited.add(decision_id)
            order.append(decision_id)

        for decision_id in self.decisions:
            visit(decision_id)
        return order


def parse_dmn_file(path):
    tree = ET.parse(path)
    root = tree.getroot()
    decisions = {}

    for dec_elem in root.findall(_tag('decision')):
        dec_id = dec_elem.get('id')
        dec_name = dec_elem.get('name')

        required = []
        for req_elem in dec_elem.findall(_tag('informationRequirement')):
            req_dec = req_elem.find(_tag('requiredDecision'))
            if req_dec is not None:
                href = req_dec.get('href', '')
                required.append(href.lstrip('#'))

        table_elem = dec_elem.find(_tag('decisionTable'))
        lit_elem = dec_elem.find(_tag('literalExpression'))

        if table_elem is not None:
            inputs = []
            for in_elem in table_elem.findall(_tag('input')):
                expr_elem = in_elem.find(_tag('inputExpression'))
                inputs.append(Column(
                    id=in_elem.get('id'), label=in_elem.get('label'),
                    name=None, type_ref=(expr_elem.get('typeRef') if expr_elem is not None else None),
                    expression_text=(_text(expr_elem) if expr_elem is not None else None)))

            outputs = []
            for out_elem in table_elem.findall(_tag('output')):
                outputs.append(Column(
                    id=out_elem.get('id'), label=out_elem.get('label'),
                    name=out_elem.get('name'), type_ref=out_elem.get('typeRef'),
                    expression_text=None))

            rules = []
            for idx, rule_elem in enumerate(table_elem.findall(_tag('rule'))):
                in_entries = [_text(e) for e in rule_elem.findall(_tag('inputEntry'))]
                out_entries = [_text(e) for e in rule_elem.findall(_tag('outputEntry'))]
                if len(in_entries) != len(inputs):
                    raise ValueError(
                        f"{rule_elem.get('id')!r} has {len(in_entries)} input entries, "
                        f"table declares {len(inputs)} input columns -- {path}")
                if len(out_entries) != len(outputs):
                    raise ValueError(
                        f"{rule_elem.get('id')!r} has {len(out_entries)} output entries, "
                        f"table declares {len(outputs)} output columns -- {path}")
                desc_elem = rule_elem.find(_tag('description'))
                rules.append(Rule(
                    id=rule_elem.get('id'), index=idx,
                    input_entries=in_entries, output_entries=out_entries,
                    description=(desc_elem.text if desc_elem is not None else None)))

            decisions[dec_id] = Decision(
                id=dec_id, name=dec_name, kind='decision_table',
                required_decisions=required, hit_policy=table_elem.get('hitPolicy'),
                inputs=inputs, outputs=outputs, rules=rules)

        elif lit_elem is not None:
            var_elem = dec_elem.find(_tag('variable'))
            decisions[dec_id] = Decision(
                id=dec_id, name=dec_name, kind='literal_expression',
                required_decisions=required,
                literal_expression_text=_text(lit_elem),
                output_name=(var_elem.get('name') if var_elem is not None else None))

        else:
            # A real, disclosed failure -- not a silent skip. Per this
            # project's own research constraints: fail loudly on an
            # unsupported DMN construct rather than quietly treating an
            # unrecognized decision as absent.
            decisions[dec_id] = Decision(id=dec_id, name=dec_name, kind='unsupported',
                                          required_decisions=required)

    return DmnModel(dmn_file=str(path), decisions=decisions)


if __name__ == '__main__':
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else \
        '/home/user/THesisCODE/openmrs_dmn/dmn/Patient_Identifier_Validation.dmn'
    model = parse_dmn_file(path)

    print(f"Parsed {path}")
    print(f"{len(model.decisions)} decisions:\n")
    for dec_id in model.topological_order():
        d = model.decisions[dec_id]
        print(f"  {d.id}  ({d.kind})  requires={d.required_decisions}")
        if d.kind == 'decision_table':
            print(f"    hit_policy={d.hit_policy}  "
                  f"inputs={[c.expression_text for c in d.inputs]}  "
                  f"outputs={[c.name for c in d.outputs]}")
            for r in d.rules:
                print(f"    rule[{r.index}] {r.id}: "
                      f"IF {list(zip([c.expression_text for c in d.inputs], r.input_entries))} "
                      f"THEN {r.output_entries}")
        elif d.kind == 'literal_expression':
            print(f"    output_name={d.output_name}  expr={d.literal_expression_text!r}")
        print()
