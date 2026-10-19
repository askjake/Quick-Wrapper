import os,sys,time,unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

@unittest.skipUnless(bool(os.environ.get('DISPLAY')) or os.name=='nt','Tk GUI acceptance requires graphical display')
class WizardGuiSmoke(unittest.TestCase):
    def test_verify_then_auto_plan_then_manual_instructions(self):
        import wizard
        from test_v03_backend import Gateway
        app=wizard.Wizard()
        try:
            gw=Gateway()
            app.gateway=lambda:gw
            app.vars['host'].set('jump.example.internal')
            app.vars['user'].set('engineer')
            app.vars['target'].set('epg-demo')
            app.vars['display_name'].set('AQ EPG Demo')
            app.vars['url'].set('https://abc.lambda-url.us-west-2.on.aws/mcp')
            app.action=lambda task,callback=None: callback(True,task()) if callback else task()
            with mock.patch.object(wizard.messagebox,'showinfo'),mock.patch.object(wizard.messagebox,'showerror') as showerror:
                app.step=1;app.render();app.update()
                app.verify_backend_action()
                self.assertEqual(app.backend_verification['status'],'BACKEND_VERIFIED')
                app.go_next();self.assertEqual(app.step,2)
                app.tool_box.selection_set(0)
                app.go_next();self.assertEqual(app.step,3)
                time.sleep(.10);app.update()
                self.assertIsNotNone(app.prepared)
                self.assertEqual(app.prepared['target'],'epg-demo')
                self.assertEqual(app.prepared['registry_entry']['allow'],['count_alerts'])
                self.assertIn('execution_plan',app.plan_view.get('1.0','end'))
                app.go_next();self.assertEqual(app.step,4)
                self.assertIn('Test connection',app.manual.get('1.0','end'))
                self.assertIn('Expected 5 argument chips',app.manual.get('1.0','end'))
                self.assertFalse(showerror.called)
        finally:app.destroy()
