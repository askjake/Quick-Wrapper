import os
import sys
import unittest
import tkinter as tk
from tkinter import ttk
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wizard
from model import quick_connector, backend_identity


@unittest.skipUnless(os.environ.get('DISPLAY') or sys.platform in ('win32', 'darwin'),
                     'Tk GUI requires an active desktop/display')
class TestGuiQuickCopy(unittest.TestCase):
    def test_plan_and_quick_page_show_single_line_copyable_arguments(self):
        app = wizard.Wizard()
        try:
            app.vars['host'].set('gateway.example.internal')
            app.vars['user'].set('engineer')
            app.vars['target'].set('demo')
            app.vars['display_name'].set('Demo')
            app.vars['url'].set('https://abc123.lambda-url.us-west-2.on.aws/mcp')
            app.tool_selection = ['list_things']
            spec = app.spec()
            cfg = quick_connector(spec)
            app.prepared = {'quick_connector': cfg,
                            'backend_identity_sha256': backend_identity(spec),
                            'registry_entry': {'allow': ['list_things']}}
            expected = '-T -q engineer@gateway.example.internal /home/engineer/aq-mcp/aq-run.sh demo'

            def entries(widget):
                items=[]
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Entry):
                        items.append(child.get())
                    items.extend(entries(child))
                return items

            app.step=3
            app.render()
            self.assertIn('ssh', entries(app.quick_copy_area))
            self.assertIn(expected, entries(app.quick_copy_area))
            app.copy_text(expected)
            self.assertEqual(app.clipboard_get(),expected)

            app.step=4
            app.render()
            self.assertIn('ssh', entries(app.quick_copy_area))
            self.assertIn(expected, entries(app.quick_copy_area))
        finally:
            app.destroy()
