"""Conservative direct lifecycle-call preflight, not a Python sandbox."""
import ast

from .errors import BadRequest


def inspect_source(source, filename):
    tree = ast.parse(source, filename=filename)
    names = {"QgsApplication"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == 'QgsApplication':
                    names.add(alias.asname or alias.name)
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) else ""
            if name in names or name in ('initQgis', 'exitQgis'):
                findings.append({'path': filename, 'line': node.lineno, 'call': name})
    return sorted(findings, key=lambda item: item['line'])


def check_source(source, filename):
    findings = inspect_source(source, filename)
    if findings:
        raise BadRequest(
            'QGIS Desktop lifecycle-call candidates detected; execution stopped. '
            'Review the test environment and run standalone tests in external QGIS Python. '
            'No source was rewritten. This is not a confirmed defect or a complete safety check.',
            details={'environment': 'QGIS Desktop', 'findings': findings},
        )
