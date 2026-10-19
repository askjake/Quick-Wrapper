"""AQ-MCP Connector Wizard v0.4, local desktop UI (tkinter).
No web listener, no Quick database mutations, no saved PATs or passwords.
"""
import json
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from deploy_lib import SSHGateway, ConnectorDeployer, DeploymentError
from native_gateway import NativeGateway
from model import (validate_gateway, validate_spec, ValidationError, quick_connector,
                   config_export, backend_identity, risk_tool_names)
from quick_reg import quick_instructions, write_quick_config, inspect_dips_read_only

BG='#101826'
PANEL='#1B2738'
FG='#EDF2FA'
SOFT='#AFC0D1'
ACCENT='#56C5E6'

class Wizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('AQ-MCP Connector Wizard  •  v0.4')
        self.geometry('970x710')
        self.minsize(760,620)
        self.configure(bg=BG)
        self.style=ttk.Style(self)
        self.style.theme_use('clam')
        self.style.configure('TFrame',background=BG)
        self.style.configure('TLabel',background=BG,foreground=FG,font=('Segoe UI',10))
        self.style.configure('Muted.TLabel',background=BG,foreground=SOFT,font=('Segoe UI',9))
        self.style.configure('Heading.TLabel',background=BG,foreground=FG,font=('Segoe UI Semibold',16))
        self.style.configure('TButton',padding=(13,8),font=('Segoe UI',10))
        self.style.configure('TEntry',fieldbackground='white',foreground='#101826')
        self.style.configure('TCombobox',fieldbackground='white',foreground='#101826')
        self.style.configure('TCheckbutton',background=BG,foreground=FG)
        self.step=0
        self.prepared=None
        self.last_receipt=None
        self.last_gateway=None
        self.discovered=[]
        self.gateway_inspection=None
        self.backend_verification=None
        self.busy=False
        self.vars={
            'host':tk.StringVar(), 'user':tk.StringVar(),
            'known_hosts':tk.StringVar(value=os.path.expanduser('~/.ssh/known_hosts')),
            'transport':tk.StringVar(value='linux-ssh'),
            'kind':tk.StringVar(value='lambda'), 'target':tk.StringVar(value='epg-demo'),
            'display_name':tk.StringVar(value='AQ EPG Demo'),
            'url':tk.StringVar(), 'server':tk.StringVar(value='aq_build_artifacts_mcp.py')}
        self.screens=['Gateway','Backend','Tool policy','Review & deploy','Quick registration']
        self.heading=ttk.Frame(self,padding=(24,18));self.heading.pack(fill='x')
        ttk.Label(self.heading,text='AQ-MCP  /  CONNECTOR WIZARD',style='Muted.TLabel').pack(anchor='w')
        ttk.Label(self.heading,text='Build a verified MCP connector',style='Heading.TLabel').pack(anchor='w',pady=(6,0))
        self.pill=ttk.Label(self.heading,text='PLAN FIRST  •  NO QUICK DATABASE WRITES',style='Muted.TLabel')
        self.pill.pack(anchor='w',pady=(7,0))
        self.step_label=ttk.Label(self,text='',style='Muted.TLabel')
        self.step_label.pack(anchor='w',padx=25)
        self.body=ttk.Frame(self,padding=(26,18)); self.body.pack(fill='both',expand=True)
        foot=ttk.Frame(self,padding=(24,8))
        foot.pack(fill='x',side='bottom')
        self.back_btn=ttk.Button(foot,text='← Back',command=self.go_back);self.back_btn.pack(side='left')
        self.next_btn=ttk.Button(foot,text='Continue →',command=self.go_next);self.next_btn.pack(side='right')
        self.status=ttk.Label(foot,text='Ready',style='Muted.TLabel')
        self.status.pack(side='right',padx=15)
        self.render()

    def field(self,parent,label,key,placeholder=None):
        ttk.Label(parent,text=label).pack(anchor='w',pady=(12,5))
        e=ttk.Entry(parent,textvariable=self.vars[key],width=90)
        e.pack(fill='x')
        return e

    def helper(self,parent,text):
        ttk.Label(parent,text=text,style='Muted.TLabel',wraplength=840,justify='left').pack(anchor='w',pady=7)

    def text_area(self,parent,height=8):
        holder=ttk.Frame(parent)
        holder.pack(fill='both',expand=True,pady=8)
        scroll=ttk.Scrollbar(holder,orient='vertical')
        scroll.pack(side='right',fill='y')
        t=tk.Text(holder,height=height,wrap='word',background=PANEL,foreground=FG,
                  insertbackground=FG,relief='flat',font=('Consolas',10),padx=12,pady=12,
                  yscrollcommand=scroll.set)
        t.pack(side='left',fill='both',expand=True)
        scroll.config(command=t.yview)
        return t

    def render(self):
        for item in self.body.winfo_children():item.destroy()
        self.step_label.config(text='   /   '.join(('[{}] {}'.format(i+1,n) if i==self.step else '{} {}'.format(i+1,n)) for i,n in enumerate(self.screens)))
        self.back_btn.config(state='disabled' if self.step==0 else 'normal')
        self.next_btn.config(text='Finish' if self.step==4 else 'Continue →')
        if self.step==0:self.render_gateway()
        elif self.step==1:self.render_backend()
        elif self.step==2:self.render_tools()
        elif self.step==3:self.render_review()
        else:self.render_quick()

    def render_gateway(self):
        ttk.Label(self.body,text='01  Select gateway location',style='Heading.TLabel').pack(anchor='w')
        self.helper(self.body,'Use native localhost on Windows with NO SSH server or admin rights, or keep your existing Linux SSH jump server. Native localhost does not open an inbound port.')
        selector=ttk.Frame(self.body);selector.pack(anchor='w',pady=6)
        for label,value in [('Linux SSH jump server (existing v0.3 workflow)','linux-ssh'),
                            ('Native gateway on THIS computer (no SSH/admin)','native-local')]:
            ttk.Radiobutton(selector,text=label,value=value,variable=self.vars['transport'],
                            command=self.transport_changed).pack(anchor='w')
        if self.vars['transport'].get()=='linux-ssh':
            self.helper(self.body,'Strict SSH host-key verification; Linux gateway bootstrap only. 127.0.0.1 is valid if your own computer runs Linux SSH.')
            self.field(self.body,'Jump server hostname / IP','host')
            self.field(self.body,'Remote SSH username','user')
            self.field(self.body,'Local known_hosts path','known_hosts')
        else:
            self.helper(self.body,'Native gateway folder: ~/AQ-MCP-Gateway. Runs under your current Windows account and uses its own venv. Linux/macOS native-local is experimental. No WSL2, Docker, SSH daemon or admin rights required for Lambda targets.')
        buttons=ttk.Frame(self.body);buttons.pack(anchor='w',pady=(16,4))
        ttk.Button(buttons,text='Inspect gateway (read only)',command=self.inspect_action).pack(side='left',padx=(0,8))
        ttk.Button(buttons,text='Install missing gateway',command=self.bootstrap_action).pack(side='left',padx=(0,8))
        if self.vars['transport'].get()=='linux-ssh':
            ttk.Button(buttons,text='Repair core permissions',command=self.repair_action).pack(side='left')
        self.helper(self.body,'Fresh install is create-only and needs approved Python package downloads. AWS credentials are configured separately; no PATs or Quick database writes. Existing installations are never overwritten.')
        self.gateway_result=self.text_area(self.body,9)
        self.gateway_result.insert('1.0','Click Inspect. A missing gateway can be installed only with approval; core permission repair is separate.')

    def render_backend(self):
        ttk.Label(self.body,text='02  Select MCP backend',style='Heading.TLabel').pack(anchor='w')
        self.helper(self.body,'Choose the approved backend. Native-local v0.4 supports SigV4 Lambda; Git and existing local servers remain Linux SSH-only.')
        group=ttk.Frame(self.body);group.pack(fill='x',pady=8)
        modes=[('AWS Lambda Function URL (SigV4)','lambda')]
        if self.vars['transport'].get()=='linux-ssh':modes += [('Guarded Git MCP (existing)','git'),('Local approved MCP (existing)','local')]
        for label,value in modes:
            ttk.Radiobutton(group,text=label,value=value,variable=self.vars['kind'],command=self.kind_changed).pack(anchor='w',pady=4)
        self.field(self.body,'Registry / Git target name','target')
        self.field(self.body,'Quick connector display name','display_name')
        if self.vars['kind'].get()=='lambda':
            self.field(self.body,'AWS Lambda Function URL (HTTPS, IAM-authorized)','url')
            self.helper(self.body,'Example: https://EXAMPLE.lambda-url.us-west-2.on.aws/mcp. No other HTTP domains are permitted by this proxy.')
        elif self.vars['kind'].get()=='git':
            self.helper(self.body,'Choose existing gateway target github-ghes or gitlab. The wizard never edits Docker images, token stores, or branch guards.')
            ttk.Button(self.body,text='Use github-ghes',command=lambda:self.vars['target'].set('github-ghes')).pack(anchor='w')
            ttk.Button(self.body,text='Use gitlab',command=lambda:self.vars['target'].set('gitlab')).pack(anchor='w')
        else:
            self.helper(self.body,'Local mode registers an existing local target such as build-artifacts; it cannot execute arbitrary scripts.')
            ttk.Button(self.body,text='Use build-artifacts',command=lambda:self.vars['target'].set('build-artifacts')).pack(anchor='w')
        ttk.Button(self.body,text='Test / Verify Backend (MCP handshake)',command=self.verify_backend_action).pack(anchor='w',pady=(15,7))
        self.backend_result=self.text_area(self.body,7)
        v=self.backend_verification
        if v and v.get('backend_identity_sha256')==backend_identity(self.spec()):
            self.backend_result.insert('1.0',self.describe_backend(v))
        else:
            self.backend_result.insert('1.0','Not verified. Test the selected backend before continuing.\n'
                                       'The check requests MCP initialize + tools/list, but does not execute application tools.\n'
                                       'Git/local verification starts the existing approved MCP launcher.')

    def describe_backend(self,report):
        lines=['STATUS: '+report['status'],
               'Registry target: '+('EXISTING (registration-only)' if report.get('existing_target') else 'NEW (eligible for create-only install)'),
               'Handshake: '+report['handshake'],
               'Offered tools: '+str(report['tool_count']),
               'Backend identity: '+report['backend_identity_sha256'][:20]+'...',
               'Verification only: no application tool calls.']
        for warning in report.get('warnings',[]):lines.append('WARNING: '+warning)
        if report.get('potentially_mutating_tools_name_only'):
            lines.append('REVIEW potential mutators (name-based guess, NOT a safety verdict):')
            lines.extend('  - '+name for name in report['potentially_mutating_tools_name_only'])
        lines.extend('  '+t['name'] for t in report['tools'])
        return '\n'.join(lines)

    def verify_backend_action(self):
        spec=self.spec()
        # Backend verification does not require choosing tool policy yet.
        if spec['kind']=='lambda':spec['allow']=['verification-placeholder']
        def done(ok,result):
            if not ok:
                self.backend_verification=None
                messagebox.showerror('Backend verification failed',str(result))
                if self.step==1:self.backend_result.delete('1.0','end');self.backend_result.insert('1.0','FAILED: '+str(result))
                return
            if result.get('backend_identity_sha256')!=backend_identity(self.spec()):
                self.backend_verification=None
                messagebox.showwarning('Inputs changed','The selected backend changed while verification was running. Test again.');return
            self.backend_verification=result
            self.prepared=None
            if self.vars['kind'].get()=='lambda':
                self.discovered=list(result['tools'])
                self.tool_selection=list(result.get('existing_allow') or [])
            if self.step==1:
                self.backend_result.delete('1.0','end')
                self.backend_result.insert('1.0',self.describe_backend(result))
            messagebox.showinfo('Backend verification','MCP tools/list succeeded: {} tool(s).\n'
                                'Review warnings and choose the allowed tools next.'.format(result['tool_count']))
        self.action(lambda:ConnectorDeployer(self.gateway()).verify_backend(spec),done)


    def transport_changed(self):
        self.gateway_inspection=None
        self.backend_verification=None
        self.prepared=None
        self.discovered=[]
        self.tool_selection=[]
        if self.vars['transport'].get()=='native-local':
            self.vars['kind'].set('lambda')
        self.render()

    def kind_changed(self):
        self.prepared=None
        self.backend_verification=None
        self.discovered=[]
        self.tool_selection=[]
        k=self.vars['kind'].get()
        self.vars['target'].set({'lambda':'epg-demo','git':'github-ghes','local':'build-artifacts'}[k])
        self.render()

    def render_tools(self):
        ttk.Label(self.body,text='03  Tool discovery and allow-list',style='Heading.TLabel').pack(anchor='w')
        if self.vars['kind'].get()!='lambda':
            self.helper(self.body,'This backend is already registered on the gateway. Its existing Git guard / local tool policy is not modified.')
            return
        self.helper(self.body,'Discover tools through the chosen gateway (MCP initialize + tools/list only). Check exact tools to expose. An empty list is prohibited because the current proxy treats empty as ALL.')
        ttk.Button(self.body,text='Re-test / refresh backend tool list',command=self.discover_action).pack(anchor='w',pady=6)
        self.helper(self.body,'WARNING: Tool names and descriptions are not safety guarantees. An EPG label with Alerts/export tools may indicate the wrong Lambda URL.')
        self.tool_box=tk.Listbox(self.body,selectmode='multiple',height=12,exportselection=False,
                                 bg=PANEL,fg=FG,selectbackground='#28617D',
                                 selectforeground='white',font=('Consolas',10),relief='flat')
        self.tool_box.pack(fill='both',expand=True,pady=10)
        for i,t in enumerate(self.discovered):
            self.tool_box.insert('end',t['name']+'   '+t.get('description','')[:85])
            if t['name'] in getattr(self,'tool_selection',[]): self.tool_box.selection_set(i)
        self.helper(self.body,'Select explicitly. An actual deployment will rediscover and verify every selected name before writing.')
        if self.backend_verification:
            for warning in self.backend_verification.get('warnings',[]):self.helper(self.body,'WARNING: '+warning)

    def render_review(self):
        ttk.Label(self.body,text='04  Plan, deploy and verify',style='Heading.TLabel').pack(anchor='w')
        self.helper(self.body,'The verified backend and selected tools produce a plan automatically. The live registry is checked before approval; Apply is locked until planning finishes.')
        controls=ttk.Frame(self.body);controls.pack(fill='x',pady=6)
        ttk.Button(controls,text='Refresh deployment plan',command=self.plan_action).pack(side='left',padx=(0,10))
        ttk.Button(controls,text='Deploy approved plan',command=self.deploy_action).pack(side='left',padx=(0,10))
        ttk.Button(controls,text='Rollback last deployment',command=self.rollback_action).pack(side='left',padx=(0,10))
        ttk.Button(controls,text='Save receipt',command=self.save_receipt_action).pack(side='left')
        self.plan_view=self.text_area(self.body,16)
        if self.prepared:self.plan_view.insert('1.0',json.dumps(self.prepared,indent=2))
        else:self.plan_view.insert('1.0','Generating a deployment plan automatically from verified backend and selected tools...')
        self.after(75,self.auto_plan)

    def render_quick(self):
        ttk.Label(self.body,text='05  Register in Amazon Quick',style='Heading.TLabel').pack(anchor='w')
        self.helper(self.body,'Gateway deployment and Quick Desktop registration are separate steps. Native-local uses direct Python (no SSH); Linux SSH uses ssh. This version NEVER writes to DIPS.')
        try:msg=quick_instructions(self.spec())
        except Exception as e:msg='Complete prior steps: '+str(e)
        self.manual=self.text_area(self.body,12)
        self.manual.insert('1.0',msg)
        controls=ttk.Frame(self.body);controls.pack(fill='x',pady=12)
        ttk.Button(controls,text='Copy Quick settings',command=lambda:self.copy_text(msg)).pack(side='left',padx=(0,10))
        ttk.Button(controls,text='Export JSON example',command=self.export_action).pack(side='left',padx=(0,10))
        ttk.Button(controls,text='Inspect DIPS schema (read-only)',command=self.dips_action).pack(side='left')
        self.helper(self.body,'After saving in Quick, open a NEW Quick chat, verify tools/list or a harmless read, and review per-tool permission settings. Registration status: MANUAL_REQUIRED.')

    def auto_plan(self):
        if self.step != 3 or self.busy:return
        current=self.spec()
        if self.prepared and self.prepared.get('backend_identity_sha256')==backend_identity(current):
            if current['kind']!='lambda' or self.prepared.get('registry_entry',{}).get('allow')==sorted(current.get('allow',[])):
                return
        self.plan_action()

    def spec(self):
        spec={k:v.get().strip() for k,v in self.vars.items() if k!='known_hosts'}
        if spec['transport']=='native-local':
            spec['host']='127.0.0.1'
            spec['user']='local'
        if spec['kind']=='lambda':
            if hasattr(self,'tool_box') and self.tool_box.winfo_exists():
                spec['allow']=[self.discovered[int(i)]['name'] for i in self.tool_box.curselection()]
            elif hasattr(self,'tool_selection'):
                spec['allow']=list(self.tool_selection)
            else: spec['allow']=[]
        return spec

    def save_selection(self):
        if self.step==2 and self.vars['kind'].get()=='lambda' and hasattr(self,'tool_box'):
            self.tool_selection=[self.discovered[int(i)]['name'] for i in self.tool_box.curselection()]
        if self.step==1: self.prepared=None

    def gateway(self):
        spec=self.spec()
        validate_gateway(spec['host'],spec['user'])
        if spec.get('transport')=='native-local':return NativeGateway()
        return SSHGateway(spec['host'],spec['user'],self.vars['known_hosts'].get().strip())

    def action(self,task,callback=None):
        if self.busy:return
        self.busy=True
        self.back_btn.config(state='disabled');self.next_btn.config(state='disabled')
        self.status.config(text='Working…')
        self.configure(cursor='watch')
        def run():
            try:result=task();ok=True
            except Exception as e:result=str(e);ok=False
            def done():
                self.busy=False
                self.configure(cursor='');self.status.config(text='Ready' if ok else 'Operation failed')
                self.back_btn.config(state='disabled' if self.step==0 else 'normal');self.next_btn.config(state='normal')
                if callback:callback(ok,result)
                elif not ok:messagebox.showerror('Operation failed',result)
            self.after(0,done)
        threading.Thread(target=run,daemon=True).start()

    def inspect_action(self):
        def done(ok,result):
            self.gateway_result.delete('1.0','end')
            self.gateway_inspection=result if ok else None
            self.gateway_result.insert('1.0',json.dumps(result,indent=2) if ok else result)
        self.action(lambda:ConnectorDeployer(self.gateway()).inspect(),done)

    def bootstrap_action(self):
        state=self.gateway_inspection
        if not state or state.get('state')!='MISSING':
            messagebox.showerror('Inspect first','Only a confirmed missing gateway can be installed. Click Inspect first.');return
        location=('a new user-owned ~/AQ-MCP-Gateway on THIS computer' if self.vars['transport'].get()=='native-local' else 'a new PRIVATE ~/aq-mcp gateway on this Linux SSH server')
        if not messagebox.askyesno('Install new gateway',
            'Install '+location+'?\n\n'
            'This installs reviewed gateway Python sources and downloads pinned packages using the jump server configured pip index. '
            'No existing installation will be overwritten. AWS credentials are NOT created.\n\nProceed?'):
            return
        self.action(lambda:ConnectorDeployer(self.gateway()).bootstrap(approved=True),
                    lambda ok,result:self.install_done(ok,result))

    def repair_action(self):
        state=self.gateway_inspection
        if not state or state.get('state')!='PERMISSIONS_NEED_REPAIR':
            messagebox.showerror('Inspect first','Permission repair requires an inspected owned gateway with unsafe core-file modes.');return
        names=', '.join(x['file'] for x in state['mode_issues'])
        if not messagebox.askyesno('Change access modes',
            'Remove group/world WRITE permission from these owned gateway files:\n'+names+'\n\n'
            'This may affect other users or shared workflows. No unrelated files are changed. Continue?'):
            return
        self.action(lambda:ConnectorDeployer(self.gateway()).repair_permissions(state,approved=True),
                    lambda ok,result:self.install_done(ok,result))

    def install_done(self,ok,result):
        if not ok:
            messagebox.showerror('Gateway action failed',str(result));return
        self.gateway_inspection=None
        messagebox.showinfo('Gateway action',json.dumps(result,indent=2)[:2000]+'\n\nInspect again before deploying a target.')
        self.inspect_action()

    def discover_action(self):
        sp=self.spec();sp['allow']=['discovery-placeholder']
        def done(ok,result):
            if not ok:
                self.backend_verification=None;self.discovered=[];self.tool_selection=[]
                messagebox.showerror('Discovery failed',result);return
            self.backend_verification=result
            self.prepared=None
            self.discovered=list(result['tools']);self.tool_selection=list(result.get('existing_allow') or [])
            self.render()
            messagebox.showinfo('Discovery','{} tools returned. Select exact tools, and review the potential mutators.'.format(len(self.discovered)))
        self.action(lambda:ConnectorDeployer(self.gateway()).verify_backend(sp),done)

    def plan_action(self):
        spec=self.spec()
        if not self.backend_verification or self.backend_verification.get('backend_identity_sha256')!=backend_identity(spec):
            self.prepared=None
            messagebox.showerror('Backend not verified','Return to Step 2 and test the selected backend before generating a plan.');return
        def done(ok,result):
            if not ok:
                self.prepared=None;self.plan_view.delete('1.0','end');self.plan_view.insert('1.0','Plan failed: '+str(result))
                messagebox.showerror('Plan failed',str(result));return
            if result.get('backend_identity_sha256')!=backend_identity(self.spec()):
                self.prepared=None;messagebox.showerror('Plan stale','The backend fields changed; regenerate the plan.');return
            result['verification_summary']={'status':'BACKEND_VERIFIED',
                'handshake':self.backend_verification['handshake'],
                'offered_tool_count':self.backend_verification['tool_count'],
                'offered_name_sha256':__import__('hashlib').sha256(','.join(sorted(x['name'] for x in self.backend_verification['tools'])).encode()).hexdigest()}
            self.prepared=result
            self.plan_view.delete('1.0','end');self.plan_view.insert('1.0',json.dumps(result,indent=2))
        self.action(lambda:ConnectorDeployer(self.gateway()).prepare(spec),done)

    def deploy_action(self):
        if not self.prepared:messagebox.showerror('Plan first','Wait for the automatically generated deployment plan first.');return
        spec=self.spec();prepared=dict(self.prepared)
        if prepared.get('backend_identity_sha256')!=backend_identity(spec) or prepared.get('quick_connector')!=quick_connector(spec):
            messagebox.showerror('Stale plan','Backend/connector settings changed. Refresh the plan before deployment.');return
        if spec['kind']=='lambda' and (prepared.get('registry_entry') or {}).get('allow')!=sorted(spec.get('allow',[])):
            messagebox.showerror('Stale tool policy','Tool selection changed. Refresh the plan before deployment.');return
        try:validate_spec(spec)
        except Exception as exc:messagebox.showerror('Validation',str(exc));return
        risky=prepared.get('potentially_mutating_tools_name_only',[])
        if risky and not messagebox.askyesno('Review selected tools',
            'Potentially MUTATING tool names were selected:\n'+', '.join(risky[:14])+
            '\n\nName heuristics are NOT a safety verdict. Did you inspect each tool and intentionally approve exposing these actions?'):
            return
        if prepared.get('warnings') and not messagebox.askyesno('Backend warnings',
            '\n'.join(prepared['warnings'])+'\n\nConfirm this is the correct endpoint and tool set?'):
            return
        if not messagebox.askyesno('Approve gateway change',
             'Deploy only {} on the selected gateway?\n\nA registry backup is created; health checks run; Quick registration remains manual.'.format(spec['target'])):
            return
        gw=self.gateway()
        def done(ok,result):
            if not ok:messagebox.showerror('Deployment failed',result);return
            self.last_receipt=result;self.last_gateway=gw
            self.plan_view.delete('1.0','end');self.plan_view.insert('1.0',json.dumps(result,indent=2))
            messagebox.showinfo('Gateway result',result['status']+'\nQuick registration remains manual.')
        self.action(lambda:ConnectorDeployer(gw).deploy(spec,prepared,True),done)

    def save_receipt_action(self):
        if not self.last_receipt or not (self.last_receipt.get('backup_name') or self.last_receipt.get('backup_file')):
            messagebox.showerror('No deployment receipt','Deploy a new Lambda target before saving a receipt.');return
        path=filedialog.asksaveasfilename(title='Save private rollback receipt',
                                          defaultextension='.json',filetypes=[('JSON','*.json')])
        if not path:return
        try:
            with open(path,'x',encoding='utf-8') as fp:
                json.dump(self.last_receipt,fp,indent=2,sort_keys=True);fp.write('\n')
            messagebox.showinfo('Receipt saved','Keep this file internal: it includes the gateway/connector address.')
        except Exception as e:messagebox.showerror('Could not save receipt',str(e))

    def rollback_action(self):
        if not self.last_receipt or not (self.last_receipt.get('backup_name') or self.last_receipt.get('backup_file')):
            messagebox.showerror('No rollback receipt','Only newly installed Lambda entries can be rolled back.');return
        if not messagebox.askyesno('Confirm rollback','Restore only if the registry SHA has NOT changed since deployment?'):
            return
        self.action(lambda:ConnectorDeployer(self.last_gateway).rollback(self.last_receipt),
                    lambda ok,result:messagebox.showinfo('Rollback' if ok else 'Rollback blocked',str(result)))

    def copy_text(self,value):
        self.clipboard_clear();self.clipboard_append(value);self.update()
        self.status.config(text='Copied to clipboard')

    def export_action(self):
        spec=self.spec()
        try:validate_spec(spec)
        except Exception as e:messagebox.showerror('Invalid form',str(e));return
        path=filedialog.asksaveasfilename(title='Save example (not directly importable)',defaultextension='.json',filetypes=[('JSON','*.json')])
        if not path:return
        try:write_quick_config(spec,path)
        except Exception as exc:messagebox.showerror('Export failed',str(exc));return
        messagebox.showinfo('Example saved','Export written. This file is NOT proof that Quick can import it.')

    def dips_action(self):
        path=filedialog.askopenfilename(title='Select Quick DIPS database (read only)')
        if not path:return
        if not messagebox.askyesno('Read only','Close Quick before inspecting. Continue with read-only schema inventory?'):return
        try:result=inspect_dips_read_only(path)
        except Exception as e:messagebox.showerror('Inspection failed',str(e));return
        messagebox.showinfo('Schema inventory (no writes)',json.dumps(result,indent=2)[:3000])

    def go_next(self):
        if self.step==4:messagebox.showinfo('Finish','Complete registration manually in Quick and verify a safe tool call.');return
        if self.step==0:
            try:
                g=self.spec()
                validate_gateway(g['host'],g['user'])
            except Exception as e:messagebox.showerror('Invalid gateway',str(e));return
        if self.step==1:
            try:
                s=self.spec();s['allow']=s.get('allow') or ['discovery-placeholder'];validate_spec(s)
            except Exception as e:messagebox.showerror('Invalid backend',str(e));return
            if not self.backend_verification or self.backend_verification.get('backend_identity_sha256')!=backend_identity(self.spec()):
                messagebox.showerror('Backend verification required','Click Test / Verify Backend and wait for a successful MCP tools/list before continuing.');return
        if self.step==2:
            self.save_selection()
            if self.vars['kind'].get()=='lambda' and not self.tool_selection:
                messagebox.showerror('No tools','Discover and select at least one exact tool.');return
        self.step+=1;self.render()

    def go_back(self):
        if self.step>0:self.save_selection();self.step-=1;self.render()

if __name__=='__main__':
    Wizard().mainloop()
