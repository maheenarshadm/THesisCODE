"""Minimal DMN 1.3 + DRD generator: decision tables and literal-expression
decisions. Writes whatever FEEL text it is given verbatim (data-driven),
matching this project's established dmn_builder.py convention."""
import xml.sax.saxutils as sx

NS = {
    'dmn': 'https://www.omg.org/spec/DMN/20191111/MODEL/',
    'dmndi': 'https://www.omg.org/spec/DMN/20191111/DMNDI/',
    'dc': 'http://www.omg.org/spec/DMN/20180521/DC/',
    'di': 'http://www.omg.org/spec/DMN/20180521/DI/',
}

def esc(s):
    return sx.escape(str(s))

def build_decision_table(decision, idx):
    inputs = decision['inputs']
    outputs = decision['outputs']
    rules = decision['rules']
    hit_policy = decision.get('hit_policy', 'FIRST')
    lines = []
    lines.append(f'    <decision id="{decision["id"]}" name="{esc(decision["name"])}">')
    for req in decision.get('requires', []):
        lines.append(f'      <informationRequirement id="ir_{decision["id"]}_{req}"><requiredDecision href="#{req}"/></informationRequirement>')
    lines.append(f'      <decisionTable id="dt_{decision["id"]}" hitPolicy="{hit_policy}">')
    for i, inp in enumerate(inputs):
        lines.append(f'        <input id="in_{decision["id"]}_{i}" label="{esc(inp["label"])}">')
        lines.append(f'          <inputExpression id="ie_{decision["id"]}_{i}" typeRef="{inp["type"]}"><text>{esc(inp["var"])}</text></inputExpression>')
        lines.append('        </input>')
    for j, out in enumerate(outputs):
        lines.append(f'        <output id="out_{decision["id"]}_{j}" label="{esc(out["label"])}" name="{esc(out["var"])}" typeRef="{out["type"]}"/>')
    for r, rule in enumerate(rules):
        lines.append(f'        <rule id="{decision["id"]}_rule_{r+1}">')
        for cond in rule['conditions']:
            lines.append(f'          <inputEntry><text>{esc(cond)}</text></inputEntry>')
        for val in rule['outputs']:
            lines.append(f'          <outputEntry><text>{esc(val)}</text></outputEntry>')
        if 'annotation' in rule:
            lines.append(f'          <annotationEntry><text>{esc(rule["annotation"])}</text></annotationEntry>')
        lines.append('        </rule>')
    lines.append('      </decisionTable>')
    lines.append('    </decision>')
    return '\n'.join(lines)

def build_literal_expression(decision, idx):
    lines = []
    lines.append(f'    <decision id="{decision["id"]}" name="{esc(decision["name"])}">')
    for req in decision.get('requires', []):
        lines.append(f'      <informationRequirement id="ir_{decision["id"]}_{req}"><requiredDecision href="#{req}"/></informationRequirement>')
    out = decision['output']
    lines.append(f'      <literalExpression id="le_{decision["id"]}" typeRef="{out["type"]}">')
    lines.append(f'        <text>{esc(decision["expression"])}</text>')
    lines.append('      </literalExpression>')
    lines.append('    </decision>')
    return '\n'.join(lines)

def build_dmn_file(namespace, name, decisions, out_path):
    header = f'''<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="{NS['dmn']}" xmlns:dmndi="{NS['dmndi']}" xmlns:dc="{NS['dc']}" xmlns:di="{NS['di']}"
             id="{name}" name="{esc(name)}" namespace="{namespace}">
'''
    body = []
    for i, d in enumerate(decisions):
        if d['kind'] == 'table':
            body.append(build_decision_table(d, i))
        else:
            body.append(build_literal_expression(d, i))
    dmndi = ['  <dmndi:DMNDI>', '    <dmndi:DMNDiagram>']
    x = 100
    for d in decisions:
        dmndi.append(f'      <dmndi:DMNShape dmnElementRef="{d["id"]}"><dc:Bounds x="{x}" y="100" width="180" height="80"/></dmndi:DMNShape>')
        x += 220
    dmndi.append('    </dmndi:DMNDiagram>')
    dmndi.append('  </dmndi:DMNDI>')
    footer = '\n'.join(dmndi) + '\n</definitions>\n'
    xml_text = header + '\n'.join(body) + '\n' + footer
    with open(out_path, 'w') as f:
        f.write(xml_text)
    return out_path
