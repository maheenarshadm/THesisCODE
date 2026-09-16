#!/usr/bin/env python3
"""
Minimal DMN 1.3 XML builder, tuned to produce files that open cleanly in
Camunda Modeler (Camunda 7). Not a general-purpose DMN library -- just
enough to emit decision tables + a Decision Requirements Diagram (DRD) with
proper DMNDI layout, from a plain Python data structure.

Each "decision" dict looks like:
{
    'id': 'Decision_AcademicWarningStatus',
    'name': 'Academic Warning Status',
    'hit_policy': 'UNIQUE',            # UNIQUE | FIRST | COLLECT | PRIORITY | ANY
    'requires': ['Decision_Other'],     # ids of decisions this one consumes output from (DRD edges)
    'inputs': [
        {'label': 'Cumulative GPA', 'expr': 'cumulativeGPA', 'type': 'number'},
        ...
    ],
    'outputs': [
        {'label': 'New Warning Count', 'name': 'newWarningCount', 'type': 'number'},
        ...
    ],
    'rules': [
        {'in': ['>= 2.00', '0'], 'out': ['0', '"Active"', '"None"'], 'desc': 'optional annotation'},
        ...
    ],
}

A decision can instead be a plain calculation (no branching, just a formula)
by setting 'kind': 'literal_expression' and omitting inputs/outputs/rules:
{
    'id': 'Decision_AttendancePercentage',
    'name': 'Attendance Percentage',
    'kind': 'literal_expression',
    'requires': [],
    'variable': {'name': 'attendancePercentage', 'type': 'number'},
    'expression': '(lecturesAttended / lecturesHeldForOffering) * 100',
}
Its 'variable.name' is what downstream decisions reference (via 'requires' +
a plain input expr of that name) to consume the computed value.

A file is built from build_dmn_file(decisions, definitions_id, name) -> XML string.
"""
import xml.etree.ElementTree as ET

DMN_NS = "https://www.omg.org/spec/DMN/20191111/MODEL/"
DMNDI_NS = "https://www.omg.org/spec/DMN/20191111/DMNDI/"
DC_NS = "http://www.omg.org/spec/DMN/20180521/DC/"
DI_NS = "http://www.omg.org/spec/DMN/20180521/DI/"
CAMUNDA_NS = "http://camunda.org/schema/1.0/dmn"

ET.register_namespace('', DMN_NS)
ET.register_namespace('dmndi', DMNDI_NS)
ET.register_namespace('dc', DC_NS)
ET.register_namespace('di', DI_NS)
ET.register_namespace('camunda', CAMUNDA_NS)


def q(ns, tag):
    return f'{{{ns}}}{tag}'


def build_dmn_file(decisions, definitions_id, definitions_name):
    defs = ET.Element(q(DMN_NS, 'definitions'), {
        'id': definitions_id,
        'name': definitions_name,
        'namespace': f'http://flex2.nu.edu.pk/dmn/{definitions_id}',
        'exporter': 'FLEX2 DMN drafting toolkit (Claude)',
        'exporterVersion': '1.0',
    })

    req_id_counter = [0]

    for dec in decisions:
        dec_el = ET.SubElement(defs, q(DMN_NS, 'decision'), {
            'id': dec['id'], 'name': dec['name'],
        })
        if dec.get('kind') == 'literal_expression':
            var = dec['variable']
            ET.SubElement(dec_el, q(DMN_NS, 'variable'), {
                'id': f"{dec['id']}_Var", 'name': var['name'], 'typeRef': var['type'],
            })
            for req in dec.get('requires', []):
                req_id_counter[0] += 1
                ir = ET.SubElement(dec_el, q(DMN_NS, 'informationRequirement'),
                                    {'id': f'InfoReq_{req_id_counter[0]}'})
                ET.SubElement(ir, q(DMN_NS, 'requiredDecision'), {'href': f'#{req}'})
            le = ET.SubElement(dec_el, q(DMN_NS, 'literalExpression'), {'id': f"{dec['id']}_Expr"})
            text_el = ET.SubElement(le, q(DMN_NS, 'text'))
            text_el.text = dec['expression']
            continue

        for req in dec.get('requires', []):
            req_id_counter[0] += 1
            ir = ET.SubElement(dec_el, q(DMN_NS, 'informationRequirement'),
                                {'id': f'InfoReq_{req_id_counter[0]}'})
            ET.SubElement(ir, q(DMN_NS, 'requiredDecision'), {'href': f'#{req}'})

        dt = ET.SubElement(dec_el, q(DMN_NS, 'decisionTable'), {
            'id': f"{dec['id']}_Table", 'hitPolicy': dec.get('hit_policy', 'UNIQUE'),
        })

        for i, inp in enumerate(dec['inputs'], start=1):
            in_el = ET.SubElement(dt, q(DMN_NS, 'input'), {
                'id': f"{dec['id']}_Input_{i}", 'label': inp['label'],
            })
            ie = ET.SubElement(in_el, q(DMN_NS, 'inputExpression'), {
                'id': f"{dec['id']}_InputExpr_{i}", 'typeRef': inp['type'],
            })
            text_el = ET.SubElement(ie, q(DMN_NS, 'text'))
            text_el.text = inp['expr']
            if inp.get('values'):
                iv = ET.SubElement(in_el, q(DMN_NS, 'inputValues'),
                                    {'id': f"{dec['id']}_InputVals_{i}"})
                t2 = ET.SubElement(iv, q(DMN_NS, 'text'))
                t2.text = inp['values']

        for j, outp in enumerate(dec['outputs'], start=1):
            out_attrs = {
                'id': f"{dec['id']}_Output_{j}", 'label': outp['label'],
                'name': outp['name'], 'typeRef': outp['type'],
            }
            ET.SubElement(dt, q(DMN_NS, 'output'), out_attrs)

        for k, rule in enumerate(dec['rules'], start=1):
            rule_el = ET.SubElement(dt, q(DMN_NS, 'rule'), {'id': f"{dec['id']}_Rule_{k}"})
            if rule.get('desc'):
                desc_el = ET.SubElement(rule_el, q(DMN_NS, 'description'))
                desc_el.text = rule['desc']
            for m, entry in enumerate(rule['in'], start=1):
                ie_el = ET.SubElement(rule_el, q(DMN_NS, 'inputEntry'),
                                       {'id': f"{dec['id']}_Rule_{k}_InEntry_{m}"})
                t = ET.SubElement(ie_el, q(DMN_NS, 'text'))
                t.text = entry
            for m, entry in enumerate(rule['out'], start=1):
                oe_el = ET.SubElement(rule_el, q(DMN_NS, 'outputEntry'),
                                       {'id': f"{dec['id']}_Rule_{k}_OutEntry_{m}"})
                t = ET.SubElement(oe_el, q(DMN_NS, 'text'))
                t.text = entry

    # ---- DMNDI: simple layered layout based on dependency depth ----
    depth = {}

    def compute_depth(dec_id, decs_by_id, seen=None):
        if dec_id in depth:
            return depth[dec_id]
        seen = seen or set()
        d = decs_by_id[dec_id]
        reqs = d.get('requires', [])
        if not reqs:
            depth[dec_id] = 0
        else:
            depth[dec_id] = 1 + max(compute_depth(r, decs_by_id) for r in reqs)
        return depth[dec_id]

    decs_by_id = {d['id']: d for d in decisions}
    for d in decisions:
        compute_depth(d['id'], decs_by_id)

    col_counters = {}
    positions = {}
    W, H, GAPX, GAPY, MARGIN = 220, 90, 90, 110, 60
    for d in decisions:
        lvl = depth[d['id']]
        col = col_counters.get(lvl, 0)
        col_counters[lvl] = col + 1
        x = MARGIN + lvl * (W + GAPX)
        y = MARGIN + col * (H + GAPY)
        positions[d['id']] = (x, y)

    dmndi = ET.SubElement(defs, q(DMNDI_NS, 'DMNDI'))
    diagram = ET.SubElement(dmndi, q(DMNDI_NS, 'DMNDiagram'), {'id': f'{definitions_id}_Diagram'})

    for d in decisions:
        x, y = positions[d['id']]
        shape = ET.SubElement(diagram, q(DMNDI_NS, 'DMNShape'), {
            'id': f"{d['id']}_Shape", 'dmnElementRef': d['id'],
        })
        ET.SubElement(shape, q(DC_NS, 'Bounds'), {
            'x': str(x), 'y': str(y), 'width': str(W), 'height': str(H),
        })

    # edges: walk decisions again to find the informationRequirement ids we created
    edge_counter = [0]
    for dec_el in defs.findall(q(DMN_NS, 'decision')):
        dec_id = dec_el.get('id')
        for ir in dec_el.findall(q(DMN_NS, 'informationRequirement')):
            req_href = ir.find(q(DMN_NS, 'requiredDecision')).get('href').lstrip('#')
            edge_counter[0] += 1
            x1, y1 = positions[req_href]
            x2, y2 = positions[dec_id]
            edge = ET.SubElement(diagram, q(DMNDI_NS, 'DMNEdge'), {
                'id': f"Edge_{edge_counter[0]}", 'dmnElementRef': ir.get('id'),
            })
            ET.SubElement(edge, q(DI_NS, 'waypoint'), {'x': str(x1 + W), 'y': str(y1 + H // 2)})
            ET.SubElement(edge, q(DI_NS, 'waypoint'), {'x': str(x2), 'y': str(y2 + H // 2)})

    xml_bytes = ET.tostring(defs, encoding='utf-8', xml_declaration=True)
    return xml_bytes.decode('utf-8')


def write_dmn(decisions, definitions_id, definitions_name, out_path):
    xml_str = build_dmn_file(decisions, definitions_id, definitions_name)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(xml_str)
    return out_path
