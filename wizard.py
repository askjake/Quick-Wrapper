"""AQ-MCP Connector Wizard v0.1, local Windows desktop UI (tkinter).
No web listener, no Quick database mutations, no saved PATs or passwords.
"""
import json
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from deploy_lib import SSHGateway, ConnectorDeployer, DeploymentError
from model import validate_gateway, validate_spec, ValidationError, quick_connector, config_export
from quick_reg import quick_instructions, write_quick_config, inspect_dips_read_only

BG='#101826'
PANEL='#1B2738'
FG='#EDF2FA'
SOFT='#AFC0D1'
ACCENT='#56C5E6'

class Wizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('AQ-MCP Connector Wizard  •  v0.1')
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
        self.vars={
            'host':tk.StringVar(), 'user':tk.StringVar(),
            'known_hosts':tk.StringVar(value=os.path.expanduser('~/.ssh/known_hosts')),
            'kind':tk.StringVar(value='lambda'), 'target':tk.StringVar(value='epg-demo'),
            'display_name':tk.StringVar(value='AQ EPG Demo'),
            'url':tk.StringVar(), 'server':tk.StringVar(value='aq_build_artifacts_mcp.py')}
        self.screens=['SSH Gateway','Backend','Tool policy','Review & deploy','Quick registration']
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
        t=tk.Text(parent,height=height,wrap='word',background=PANEL,foreground=FG,
                  insertbackground=FG,relief='flat',font=('Consolas',10),padx=12,pady=12)
        t.pack(fill='both',expand=True,pady=8)
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
        ttk.Label(self.body,text='01  Trusted SSH jump server',style='Heading.TLabel').pack(anchor='w')
        self.helper(self.body,'The wizard uses SSH keys or the SSH agent. It refuses unknown host keys. The gateway must already contain the reviewed aq-mcp runtime.')
        self.field(self.body,'Jump server hostname / IP','host')
        self.field(self.body,'Remote SSH username','user')
        self.field(self.body,'Local known_hosts path','known_hosts')
        ttk.Button(self.body,text='Test SSH / inspect gateway (read only)',command=self.inspect_action).pack(anchor='w',pady=20)
        self.gateway_result=self.text_area(self.body,9)
        self.gateway_result.insert('1.0','Connect using an approved, pre-trusted host key. No gateway writes during inspection.')

    def render_backend(self):
        ttk.Label(self.body,text='02  Select MCP backend',style='Heading.TLabel').pack(anchor='w')
        self.helper(self.body,'Choose the preapproved gateway path. Only new Lambda registry entries can be deployed in v0.1.')
        group=ttk.Frame(self.body);group.pack(fill='x',pady=14)
        for label,value in [('AWS Lambda Function URL (SigV4)','lambda'),('Guarded Git MCP (existing)','git'),('Local approved MCP (existing)','local')]:
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

    def kind_changed(self):
        self.prepared=None
        k=self.vars['kind'].get()
        self.vars['target'].set({'lambda':'epg-demo','git':'github-ghes','local':'build-artifacts'}[k])
        self.render()

    def render_tools(self):
        ttk.Label(self.body,text='03  Tool discovery and allow-list',style='Heading.TLabel').pack(anchor='w')
        if self.vars['kind'].get()!='lambda':
            self.helper(self.body,'This backend is already registered on the gateway. Its existing Git guard / local tool policy is not modified.')
            return
        self.helper(self.body,'Discover tools through the 3090 (MCP initialize + tools/list only). Check exact tools to expose. An empty list is prohibited because the current proxy treats empty as ALL.')
        ttk.Button(self.body,text='Discover offered tools (read-only requests)',command=self.discover_action).pack(anchor='w',pady=6)
        self.tool_box=tk.Listbox(self.body,selectmode='multiple',height=12,exportselection=False,
                                 bg=PANEL,fg=FG,selectbackground='#28617D',
                                 selectforeground='white',font=('Consolas',10),relief='flat')
        self.tool_box.pack(fill='both',expand=True,pady=10)
        for i,t in enumerate(self.discovered):
            self.tool_box.insert('end',t['name']+'   '+t.get('description','')[:85])
            if t['name'] in getattr(self,'tool_selection',[]): self.tool_box.selection_set(i)
        self.helper(self.body,'Select explicitly. An actual deployment will rediscover and verify every selected name before writing.')

    def render_review(self):
        ttk.Label(self.body,text='04  Plan, deploy and verify',style='Heading.TLabel').pack(anchor='w')
        self.helper(self.body,'Preview and checksum the LIVE registry before approval. Apply is locked until a plan exists and your approval is confirmed.')
        controls=ttk.Frame(self.body);controls.pack(fill='x',pady=6)
        ttk.Button(controls,text='Generate deployment plan',command=self.plan_action).pack(side='left',padx=(0,10))
        ttk.Button(controls,text='Deploy approved plan',command=self.deploy_action).pack(side='left',padx=(0,10))
        ttk.Button(controls,text='Rollback last deployment',command=self.rollback_action).pack(side='left',padx=(0,10))
        ttk.Button(controls,text='Save receipt',command=self.save_receipt_action).pack(side='left')
        self.plan_view=self.text_area(self.body,16)
        if self.prepared:self.plan_view.insert('1.0',json.dumps(self.prepared,indent=2))
        else:self.plan_view.insert('1.0','No approved plan yet. Click Generate deployment plan.')

    def render_quick(self):
        ttk.Label(self.body,text='05  Register in Amazon Quick',style='Heading.TLabel').pack(anchor='w')
        self.helper(self.body,'Gateway deployment and Quick Desktop registration are separate steps. This version NEVER writes to the DIPS database; its schema and supported registration lifecycle are unverified.')
        try:msg=quick_instructions(self.spec())
        except Exception as e:msg='Complete prior steps: '+str(e)
        self.manual=self.text_area(self.body,12)
        self.manual.insert('1.0',msg)
        controls=ttk.Frame(self.body);controls.pack(fill='x',pady=12)
        ttk.Button(controls,text='Copy Quick settings',command=lambda:self.copy_text(msg)).pack(side='left',padx=(0,10))
        ttk.Button(controls,text='Export JSON example',command=self.export_action).pack(side='left',padx=(0,10))
        ttk.Button(controls,text='Inspect DIPS schema (read-only)',command=self.dips_action).pack(side='left')
        self.helper(self.body,'After saving in Quick, open a NEW Quick chat, verify tools/list or a harmless read, and review per-tool permission settings. Registration status: MANUAL_REQUIRED.')

    def spec(self):
        spec={k:v.get().strip() for k,v in self.vars.items() if k!='known_hosts'}
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
        return SSHGateway(spec['host'],spec['user'],self.vars['known_hosts'].get().strip())

    def action(self,task,callback=None):
        self.status.config(text='Working…')
        self.configure(cursor='watch')
        def run():
            try:result=task();ok=True
            except Exception as e:result=str(e);ok=False
            def done():
                self.configure(cursor='');self.status.config(text='Ready' if ok else 'Operation failed')
                if callback:callback(ok,result)
                elif not ok:messagebox.showerror('Operation failed',result)
            self.after(0,done)
        threading.Thread(target=run,daemon=True).start()

    def inspect_action(self):
        def done(ok,result):
            self.gateway_result.delete('1.0','end')
            self.gateway_result.insert('1.0',json.dumps(result,indent=2) if ok else result)
        self.action(lambda:ConnectorDeployer(self.gateway()).inspect(),done)

    def discover_action(self):
        sp=self.spec();sp['allow']=['discovery-placeholder']
        def done(ok,result):
            if not ok:messagebox.showerror('Discovery failed',result);return
            self.discovered=result['tools'];self.tool_selection=[]
            self.render()
            messagebox.showinfo('Discovery', '{} tools returned. Select the ones to expose.'.format(len(self.discovered)))
        self.action(lambda:ConnectorDeployer(self.gateway()).discover(sp),done)

    def plan_action(self):
        spec=self.spec()
        def done(ok,result):
            if not ok:messagebox.showerror('Plan failed',result);return
            self.prepared=result
            self.plan_view.delete('1.0','end');self.plan_view.insert('1.0',json.dumps(result,indent=2))
        self.action(lambda:ConnectorDeployer(self.gateway()).prepare(spec),done)

    def deploy_action(self):
        if not self.prepared:messagebox.showerror('Plan first','Generate a deployment plan first.');return
        spec=self.spec();prepared=dict(self.prepared)
        try:validate_spec(spec)
        except Exception as exc:messagebox.showerror('Validation',str(exc));return
        if not messagebox.askyesno('Approve gateway change',
             'Deploy only {} on the approved jump server?\n\nA registry backup is created; health checks run; Quick registration remains manual.'.format(spec['target'])):
            return
        gw=self.gateway()
        def done(ok,result):
            if not ok:messagebox.showerror('Deployment failed',result);return
            self.last_receipt=result;self.last_gateway=gw
            self.plan_view.delete('1.0','end');self.plan_view.insert('1.0',json.dumps(result,indent=2))
            messagebox.showinfo('Gateway result',result['status']+'\nQuick registration remains manual.')
        self.action(lambda:ConnectorDeployer(gw).deploy(spec,prepared,True),done)

    def save_receipt_action(self):
        if not self.last_receipt or not self.last_receipt.get('backup_name'):
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
        if not self.last_receipt or not self.last_receipt.get('backup_name'):
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
            try:validate_gateway(self.vars['host'].get().strip(),self.vars['user'].get().strip())
            except Exception as e:messagebox.showerror('Invalid gateway',str(e));return
        if self.step==1:
            try:
                s=self.spec();s['allow']=s.get('allow') or ['discovery-placeholder'];validate_spec(s)
            except Exception as e:messagebox.showerror('Invalid backend',str(e));return
        if self.step==2:
            self.save_selection()
            if self.vars['kind'].get()=='lambda' and not self.tool_selection:
                messagebox.showerror('No tools','Discover and select at least one exact tool.');return
        self.step+=1;self.render()

    def go_back(self):
        if self.step>0:self.save_selection();self.step-=1;self.render()

if __name__=='__main__':
    Wizard().mainloop()
