import tempfile
import unittest
from pathlib import Path

from qgis_dev_probe.core.errors import BadRequest
from qgis_dev_probe.core.qgis_preflight import check_source, inspect_source
from qgis_dev_probe.core.recipes import load_recipe


class PreflightTests(unittest.TestCase):
    def test_candidates_include_aliases_and_function_bodies(self):
        for code in ['from qgis.core import QgsApplication as App\na=App([], False)',
                     'core.QgsApplication([],False)', 'def run(ctx,args):\n    app.exitQgis()']:
            with self.subTest(code=code), self.assertRaises(BadRequest) as raised:
                check_source(code, 'fixture.py')
            self.assertEqual(raised.exception.details['findings'][0]['path'], 'fixture.py')

    def test_strings_comments_and_registry_are_not_lifecycle_calls(self):
        self.assertEqual(inspect_source('# app.initQgis()\nx="exitQgis()"\nQgsApplication.processingRegistry()', 'ok.py'), [])

    def test_recipe_rejected_before_any_side_effect(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / 'marker'
            (Path(folder) / 'bad.py').write_text(
                f'open({str(marker)!r}, "w").close()\napp.initQgis()\n', encoding='utf-8')
            with self.assertRaises(BadRequest):
                load_recipe(folder, 'bad')
            self.assertFalse(marker.exists())

    def test_syntax_errors_are_not_swallowed(self):
        with self.assertRaises(SyntaxError):
            check_source('def run(:', 'bad.py')
