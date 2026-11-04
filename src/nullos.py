#!/usr/bin/env python3
"""NullOS 0.1 alpha: explicitly scoped NullOS-style software-switch CLI."""
import argparse
import copy
import difflib
import fcntl
import getpass
import ipaddress
import json
import os
from pathlib import Path
import readline
import re
import shlex
import subprocess
import sys
import time

VERSION = '0.1.0-alpha.2'

class RestoreFailed(ValueError):
    pass

def run(*args, input=None):
    p = subprocess.run(args, input=input, text=True, capture_output=True, timeout=30)
    if p.returncode:
        raise ValueError(f'{args[0]}: {p.stderr.strip() or p.stdout.strip()}')
    return p.stdout.strip()

def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    with open(tmp, 'w') as f:
        os.chmod(tmp, 0o600)
        json.dump(value, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

def read(path, default):
    return json.loads(path.read_text()) if path.exists() else copy.deepcopy(default)

def quote(tokens):
    return shlex.join(tokens)

def display(lines):
    # Never show password hashes in normal configuration output.
    return ['set ' + quote(x[:-1] + ['<redacted>'] if 'encrypted-password' in x else x)
            for x in sorted(lines)]

class Config:
    def __init__(self, ports):
        self.ports = ports

    def patterns(self, lines):
        vlans = sorted({x[1] for x in lines if x[:1] == ['vlans']})
        users = sorted({x[3] for x in lines if x[:3] == ['system','login','user']})
        p = [(['system','host-name','<hostname>'], None),
             (['system','services','ssh'], None),
             (['vlans','<vlan>','vlan-id','<1-4094>'], None),
             (['vlans','<vlan>','l3-interface','irb.0'], None),
             (['interfaces','irb','unit','0','family','inet','address','<IPv4/prefix>'], None),
             (['routing-options','static','route','0.0.0.0/0','next-hop','<IPv4>'], None),
             (['system','login','user','<user>','class','super-user'], None),
             (['system','login','user','<user>','authentication','encrypted-password','<hash>'], None),
             (['system','login','user','<user>','authentication','plain-text-password'], None)]
        for port in self.ports:
            base = ['interfaces',port,'unit','0','family','ethernet-switching']
            p += [(base + ['interface-mode',m],None) for m in ['access','trunk']]
            p += [(base + ['vlan','members','<vlan>'],None),
                  (['interfaces',port,'disable'],None),
                  (['interfaces',port,'description','<description>'],None)]
        return [a for a,b in p], {'<vlan>':vlans, '<user>':users}

    def check_leaf(self, tokens):
        patterns,_ = self.patterns([])
        if not any(len(tokens)==len(p) and all(a.startswith('<') or a==b for a,b in zip(p,tokens)) for p in patterns):
            raise ValueError('unsupported statement; press Tab or use ? for supported paths')
        if any('\n' in x or '\x00' in x for x in tokens):
            raise ValueError('control characters are not allowed')

    def set(self, lines, tokens):
        self.check_leaf(tokens)
        # vlan members and addresses are multi-value leaves; other values replace.
        multi = tokens[-3:-1] == ['vlan','members'] or 'address' in tokens
        flag = tokens[-1] in ('disable','ssh')
        key = tokens if flag else tokens[:-1]
        out = [x for x in lines if x != tokens and (multi or x[:len(key)] != key)]
        return out + [tokens]

    def validate(self, lines):
        c = {'hostname':'NullOS','ssh':False,'vlans':{},'ports':{},'addresses':[], 'gateway':None,'users':{}}
        for x in lines:
            self.check_leaf(x)
            if x[:2] == ['system','host-name']:
                if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?',x[2]):
                    raise ValueError('invalid hostname')
                c['hostname']=x[2]
            elif x == ['system','services','ssh']: c['ssh']=True
            elif x[:3] == ['system','login','user']:
                name=x[3]
                if not re.fullmatch(r'[a-z][a-z0-9_-]{0,30}',name) or name in ('root','nullos','daemon','nobody'):
                    raise ValueError('invalid or reserved user name')
                u=c['users'].setdefault(name,{})
                if x[4]=='class': u['class']=x[5]
                elif x[5]=='encrypted-password':
                    if not re.fullmatch(r'\$6\$[./A-Za-z0-9]{1,16}\$[./A-Za-z0-9]{86}',x[6]):
                        raise ValueError('this alpha supports SHA-512 crypt hashes only; use plain-text-password')
                    u['password']=x[6]
                else: raise ValueError('password was not converted to a hash')
            elif x[0]=='vlans':
                if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,31}',x[1]): raise ValueError('invalid VLAN name')
                v=c['vlans'].setdefault(x[1],{})
                if x[2]=='vlan-id':
                    try: vid=int(x[3])
                    except ValueError: raise ValueError('VLAN ID must be 1-4094')
                    if not 1 <= vid <= 4094: raise ValueError('VLAN ID must be 1-4094')
                    v['id']=vid
                else: v['irb']=True
            elif x[:2]==['interfaces','irb']:
                addr=ipaddress.ip_interface(x[-1])
                if addr.version!=4: raise ValueError('IPv4 only in this alpha')
                c['addresses'].append(str(addr))
            elif x[0]=='interfaces':
                port=c['ports'].setdefault(x[1],{'mode':'access','members':[],'disabled':False})
                if x[2]=='disable': port['disabled']=True
                elif x[2]=='description': port['description']=x[3]
                elif x[-2]=='interface-mode': port['mode']=x[-1]
                elif x[-2]=='members': port['members'].append(x[-1])
            elif x[0]=='routing-options':
                addr=ipaddress.ip_address(x[-1])
                if addr.version!=4: raise ValueError('IPv4 gateway required')
                c['gateway']=str(addr)
        ids=[]
        for v in c['vlans'].values():
            if 'id' not in v: raise ValueError('every VLAN needs a vlan-id')
            ids.append(v['id'])
        if len(ids)!=len(set(ids)): raise ValueError('duplicate VLAN IDs')
        for name,p in c['ports'].items():
            if p['disabled']: continue
            if not p['members']: raise ValueError(f'{name}: explicit VLAN membership required')
            if p['mode']=='access' and len(p['members'])!=1: raise ValueError(f'{name}: access requires one VLAN')
            for v in p['members']:
                if v not in c['vlans']: raise ValueError(f'{name}: undefined VLAN {v}')
        irbs=[v for v in c['vlans'].values() if v.get('irb')]
        if len(irbs)>1: raise ValueError('only one VLAN may use irb.0')
        if bool(irbs)!=bool(c['addresses']): raise ValueError('irb.0 needs both a VLAN binding and an IPv4 address')
        if c['gateway'] and not any(ipaddress.ip_address(c['gateway']) in ipaddress.ip_interface(a).network for a in c['addresses']):
            raise ValueError('gateway must be on the management subnet')
        for u in c['users'].values():
            if not u.get('password') or u.get('class')!='super-user': raise ValueError('users need class super-user and a password')
        if c['ssh'] and not c['users']: raise ValueError('configure a user before enabling SSH')
        return c

    def complete(self, line, config=False, context=None, lines=None):
        try: words=shlex.split(line)
        except ValueError: return []
        partial='' if line.endswith(' ') or not words else words.pop()
        context=context or []
        lines=lines or []
        patterns,values=self.patterns(lines)
        if config:
            paths=[['set']+p[len(context):] for p in patterns if all(a.startswith('<') or a==b for a,b in zip(p,context)) and len(p)>=len(context)]
            paths += [['delete']+x[len(context):] for x in lines if x[:len(context)]==context]
            paths += [['edit']+p[len(context):i] for p in patterns for i in range(len(context)+1,len(p)) if all(a.startswith('<') or a==b for a,b in zip(p,context)) and len(p)>=len(context)]
            paths += [['commit'],['commit','check'],['commit','confirmed','<minutes>'],['rollback','0'],['rollback','1'],['show'],['show','|','compare'],['top'],['up'],['exit'],['exit','discard']]
        else:
            paths=[['request','lab','start'],['request','lab','stop'],['request','lab','host','<port>','address','<IPv4/prefix>'],['request','lab','ping','<port>','<IPv4>'],['ping','<host>'],['ping','<host>','count','<count>'],['ping','<host>','source','<IPv4>'],['configure'],['show','configuration','|','display','set'],['show','configuration'],['show','interfaces','terse'],['show','vlans'],['show','ethernet-switching','table'],['show','version'],['show','system','commit'],['exit']]
        choices=set()
        for p in paths:
            if len(words)>=len(p): continue
            if not all(a.startswith('<') or a==b for a,b in zip(p,words)): continue
            nxt=p[len(words)]
            for opt in values.get(nxt,[nxt]):
                if opt.startswith(partial): choices.add(opt)
        return sorted(choices)

class Backend:
    def __init__(self, ports, demo=False): self.ports,self.demo=ports,demo
    def apply(self,c,old):
        if self.demo: return
        # Reject collisions with pre-existing system accounts before changing networking.
        for user in c['users']:
            if user not in old.get('users',{}):
                p=subprocess.run(['getent','passwd',user],capture_output=True)
                if p.returncode==0 and 'nullos-admin' not in run('id','-nG',user).split():
                    raise ValueError(f'user {user} already exists outside NullOS')
        cmds=['ovs-vsctl','--timeout=10','--','--may-exist','add-br','nsw0','--','set','Bridge','nsw0','stp_enable=true']
        for logical,linux in self.ports.items():
            cmds += ['--','--if-exists','del-port','nsw0',linux]
            p=c['ports'].get(logical)
            if p and not p['disabled']:
                vids=[str(c['vlans'][v]['id']) for v in p['members']]
                cmds += ['--','add-port','nsw0',linux,'--','set','Port',linux]
                cmds += ['vlan_mode=access','tag='+vids[0]] if p['mode']=='access' else ['vlan_mode=trunk','trunks='+','.join(vids)]
        cmds += ['--','--if-exists','del-port','nsw0','nmgmt0']
        irb=next((v['id'] for v in c['vlans'].values() if v.get('irb')),None)
        if irb:
            cmds += ['--','add-port','nsw0','nmgmt0','tag='+str(irb),'--','set','Interface','nmgmt0','type=internal']
        run(*cmds)
        for interface in ['nsw0', *self.ports.values()]:
            run('sysctl','-q','-w',f'net.ipv6.conf.{interface}.disable_ipv6=1')
            run('ip','-4','address','flush','dev',interface)
        run('ip','link','set','nsw0','up')
        for logical,linux in self.ports.items():
            p=c['ports'].get(logical)
            run('ip','link','set',linux,'up' if p and not p['disabled'] else 'down')
        if irb:
            run('sysctl','-q','-w','net.ipv6.conf.nmgmt0.disable_ipv6=1')
            run('ip','link','set','nmgmt0','up')
            run('ip','-4','address','flush','dev','nmgmt0')
            run('ip','-4','route','flush','default','dev','nmgmt0')
            for a in c['addresses']: run('ip','address','add',a,'dev','nmgmt0')
            if c['gateway']: run('ip','route','replace','default','via',c['gateway'],'dev','nmgmt0')
        run('hostnamectl','set-hostname',c['hostname'])
        for user,u in c['users'].items():
            if subprocess.run(['id',user],capture_output=True).returncode:
                run('useradd','-m','-s','/usr/local/bin/nullos-login','-G','nullos-admin',user)
            run('usermod','-s','/usr/local/bin/nullos-login','-p',u['password'],user)
        for user in old.get('users',{}).keys()-c['users'].keys():
            run('usermod','-L',user)
            run('usermod','-s','/usr/sbin/nologin',user)
        run('systemctl','start' if c['ssh'] else 'stop','ssh')

class LabBackend(Backend):
    """Session-owned Linux namespace with a VLAN-aware bridge and endpoint hosts."""
    def __init__(self,ports):
        super().__init__(ports,True)
        import uuid
        self.namespace='nullos-'+uuid.uuid4().hex[:12]
        self.owned=[];self.hosts={}
    def ns(self,name,*args):return run('ip','netns','exec',name,*args)
    def create_ns(self,name):
        run('ip','netns','add',name);self.owned.append(name)
        self.ns(name,'ip','link','set','lo','up')
    def start(self):
        if os.geteuid()!=0:raise ValueError('temporary backend needs Linux root privileges: launch with sudo and --demo')
        try:
            self.create_ns(self.namespace)
            self.ns(self.namespace,'ip','link','add','br0','type','bridge','vlan_filtering','1','vlan_default_pvid','0')
            self.ns(self.namespace,'ip','link','set','br0','up')
            for i,logical in enumerate(self.ports):
                host=self.namespace+'-h'+str(i);self.create_ns(host);self.hosts[logical]=host
                port='p'+str(i)
                self.ns(self.namespace,'ip','link','add',port,'type','veth','peer','name','eth0','netns',host)
                self.ns(self.namespace,'ip','link','set',port,'master','br0')
                self.ns(host,'ip','link','set','eth0','up')
        except Exception:
            self.stop();raise
    def stop(self):
        errors=[]
        for name in list(reversed(self.owned)):
            try:run('ip','netns','del',name);self.owned.remove(name)
            except Exception as e:errors.append(str(e))
        if errors:raise ValueError('cleanup incomplete: '+'; '.join(errors))
    def apply(self,c,old):
        ns=self.namespace
        # Only isolated switch state is applied; system accounts and SSH remain simulated.
        for i,logical in enumerate(self.ports):
            port='p'+str(i);p=c['ports'].get(logical)
            self.ns(ns,'ip','link','set',port,'down')
            self.ns(ns,'bridge','vlan','del','dev',port,'vid','1-4094')
            if p and not p['disabled']:
                for member in p['members']:
                    args=['bridge','vlan','add','dev',port,'vid',str(c['vlans'][member]['id'])]
                    if p['mode']=='access':args+=['pvid','untagged']
                    self.ns(ns,*args)
                self.ns(ns,'ip','link','set',port,'up')
        links=json.loads(self.ns(ns,'ip','-j','link','show'))
        if any(x['ifname']=='mgmt0' for x in links):self.ns(ns,'ip','link','del','mgmt0')
        self.ns(ns,'bridge','vlan','del','dev','br0','vid','1-4094','self')
        vid=next((v['id'] for v in c['vlans'].values() if v.get('irb')),None)
        if vid:
            self.ns(ns,'bridge','vlan','add','dev','br0','vid',str(vid),'self')
            self.ns(ns,'ip','link','add','link','br0','name','mgmt0','type','vlan','id',str(vid))
            self.ns(ns,'ip','link','set','mgmt0','up')
            for addr in c['addresses']:self.ns(ns,'ip','addr','add',addr,'dev','mgmt0')
            if c['gateway']:self.ns(ns,'ip','route','replace','default','via',c['gateway'],'dev','mgmt0')
    def address(self,port,address):
        if port not in self.hosts:raise ValueError('unknown port')
        addr=ipaddress.IPv4Interface(address)
        self.ns(self.hosts[port],'ip','-4','addr','flush','dev','eth0')
        self.ns(self.hosts[port],'ip','addr','add',str(addr),'dev','eth0')

class Store:
    def __init__(self,path,ports,demo=False):
        self.path=Path(path); self.path.mkdir(parents=True,exist_ok=True)
        self.cfg=Config(ports); self.backend=Backend(ports,demo)
    def load(self): return read(self.path/'state.json',{'active':[],'history':[],'pending':None,'revision':0})
    def save(self,s): atomic(self.path/'state.json',s)
    def lock(self):
        f=open(self.path/'lock','w'); fcntl.flock(f,fcntl.LOCK_EX); return f
    def apply(self,new,old):
        a,b=self.cfg.validate(new),self.cfg.validate(old)
        try: self.backend.apply(a,b)
        except Exception as exc:
            try: self.backend.apply(b,a)
            except Exception as rollback: raise RestoreFailed(f'APPLY FAILED: {exc}; RESTORE ALSO FAILED: {rollback}; use console') from exc
            raise ValueError(f'apply failed; previous configuration restored: {exc}') from exc
    def commit(self,lines,revision,minutes=None):
        with self.lock():
            s=self.load()
            if revision!=s['revision']: raise ValueError('configuration changed in another session; exit discard and configure again')
            self.cfg.validate(lines)
            if s['pending'] and lines!=s['active']: raise ValueError('confirm the pending commit before changing configuration')
            if s['pending'] and minutes: raise ValueError('a confirmed commit is already pending')
            if s['pending'] and lines==s['active']:
                s['pending']=None; self.save(s); return s
            old=copy.deepcopy(s)
            # Persist recovery intent before touching the backend. Boot always restores pending work.
            s['pending']={'previous':s['active'],'deadline':time.time()+((minutes or 10)*60),'applying':True}
            self.save(s)
            try: self.apply(lines,old['active'])
            except RestoreFailed:
                # Keep recovery intent for watchdog/boot retry; do not claim restoration.
                raise
            except Exception:
                self.save(old); raise
            s['history']=([old['active']]+old['history'])[:10]
            s['active']=copy.deepcopy(lines); s['revision']+=1
            s['pending']=({'previous':old['active'],'deadline':time.time()+minutes*60,'applying':False} if minutes else None)
            self.save(s); return s
    def recover(self,boot=False):
        with self.lock():
            s=self.load(); p=s['pending']
            if p and (boot or p['deadline']<=time.time()):
                self.apply(p['previous'],s['active'])
                s['active']=p['previous'];s['pending']=None;s['revision']+=1;self.save(s)
            elif boot:
                c=self.cfg.validate(s['active'])
                self.backend.apply(c,c)

class CLI:
    def __init__(self,store):
        self.store=store;self.editing=False;self.context=[];self.candidate=[];self.revision=0
        readline.set_completer_delims(' \t\n')
        readline.set_completer(self.complete)
        readline.parse_and_bind('bind ^I rl_complete' if 'libedit' in readline.__doc__ else 'tab: complete')
    def complete(self,text,state):
        opts=self.store.cfg.complete(readline.get_line_buffer(),self.editing,self.context,self.candidate)
        opts=[x+' ' for x in opts if not x.startswith('<')]
        return opts[state] if state<len(opts) else None
    def execute(self,line):
        if line.rstrip().endswith('?'):
            print('\n'.join(self.store.cfg.complete(line.rstrip()[:-1],self.editing,self.context,self.candidate)));return
        t=shlex.split(line)
        if not t:return
        if not self.editing:
            if t[:2]==['request','lab']:
                if not self.store.backend.demo:raise ValueError('lab commands require demo mode')
                lab=self.store.backend
                if t==['request','lab','start']:
                    if isinstance(lab,LabBackend):raise ValueError('lab already running')
                    if self.store.load()['pending']:raise ValueError('confirm or roll back pending commit first')
                    new=LabBackend(lab.ports);new.start()
                    try:new.apply(self.store.cfg.validate(self.store.load()['active']),{})
                    except Exception:new.stop();raise
                    self.store.backend=new
                    print('Temporary isolated backend started: '+new.namespace);return
                if not isinstance(lab,LabBackend):raise ValueError('start the lab first')
                if t==['request','lab','stop']:
                    lab.stop();self.store.backend=Backend(lab.ports,True);print('Temporary backend removed');return
                if len(t)==6 and t[2]=='host' and t[4]=='address':
                    lab.address(t[3],t[5]);print('Host address configured');return
                if len(t)==5 and t[2]=='ping':
                    if t[3] not in lab.hosts:raise ValueError('unknown port')
                    target=str(ipaddress.IPv4Address(t[4]))
                    subprocess.run(['ip','netns','exec',lab.hosts[t[3]],'ping','-4','-n','-c','4','-W','2',target],check=False);return
                raise ValueError('unsupported lab command')
            if t==['configure']:
                s=self.store.load();self.candidate=copy.deepcopy(s['active']);self.revision=s['revision'];self.editing=True;return
            if t==['exit']:raise EOFError
            if t==['show','version']:print('NullOS '+VERSION);return
            if t[0]=='ping':
                if len(t)<2 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.:-]*',t[1]):
                    raise ValueError('usage: ping <host> [count <1-100>] [source <IPv4>]')
                options=t[2:]; count=5; source=None; seen=set()
                if len(options)%2: raise ValueError('ping options require values')
                for key,value in zip(options[::2],options[1::2]):
                    if key in seen: raise ValueError('duplicate ping option')
                    seen.add(key)
                    if key=='count':
                        count=int(value)
                        if not 1<=count<=100: raise ValueError('count must be 1-100')
                    elif key=='source': source=str(ipaddress.IPv4Address(value))
                    else: raise ValueError('unsupported ping option: '+key)
                if self.store.backend.demo and not isinstance(self.store.backend,LabBackend):
                    print('Demo mode: ping requires the installed networking backend'); return
                command=['ping','-4','-n','-c',str(count),'-W','2']
                if source: command+=['-I',source]
                # No shell; stream replies and preserve normal nonzero unreachable status.
                prefix=['ip','netns','exec',self.store.backend.namespace] if isinstance(self.store.backend,LabBackend) else []
                subprocess.run(prefix+command+['--',t[1]],check=False)
                return
            if t in (['show','configuration'],['show','configuration','|','display','set']): print('\n'.join(display(self.store.load()['active'])));return
            if t==['show','system','commit']:
                s=self.store.load();print(f"revision {s['revision']}; retained rollbacks {len(s['history'])}; confirmation pending: {bool(s['pending'])}");return
            if t==['show','vlans']:
                c=self.store.cfg.validate(self.store.load()['active'])
                for n,v in c['vlans'].items(): print(n,v['id'],'irb.0' if v.get('irb') else '')
                return
            if t==['show','interfaces','terse']:
                for logical,linux in self.store.backend.ports.items():
                    state='demo' if self.store.backend.demo else Path('/sys/class/net',linux,'operstate').read_text().strip()
                    print(f'{logical:16} {linux:16} {state}')
                return
            if t==['show','ethernet-switching','table']:
                print('Demo: no live forwarding table' if self.store.backend.demo else run('ovs-appctl','fdb/show','nsw0'));return
            raise ValueError('unsupported command; press Tab or use ?')
        if t[0]=='set':
            tokens=self.context+t[1:]
            if tokens[-1:] == ['plain-text-password']:
                self.store.cfg.check_leaf(tokens)
                a=getpass.getpass('New password: ');b=getpass.getpass('Retype new password: ')
                if a!=b or len(a)<12: raise ValueError('passwords must match and contain at least 12 characters')
                tokens=tokens[:-1]+['encrypted-password',run('openssl','passwd','-6','-stdin',input=a+'\n')]
            self.candidate=self.store.cfg.set(self.candidate,tokens)
        elif t[0]=='delete' and len(t)>1:
            prefix=self.context+t[1:]
            matches=[x for x in self.candidate if x[:len(prefix)]==prefix]
            if not matches:raise ValueError('statement not found')
            self.candidate=[x for x in self.candidate if x not in matches]
        elif t[0]=='edit' and len(t)>1:
            ctx=self.context+t[1:];patterns,_=self.store.cfg.patterns(self.candidate)
            if not any(len(ctx)<len(p) and all(a.startswith('<') or a==b for a,b in zip(p,ctx)) for p in patterns): raise ValueError('unsupported edit path')
            self.context=ctx
        elif t==['top']:self.context=[]
        elif t==['up']:self.context=self.context[:-1]
        elif t==['show']:
            print('\n'.join(display([x for x in self.candidate if x[:len(self.context)]==self.context])))
        elif t==['show','|','compare']:
            print('\n'.join(difflib.unified_diff(display(self.store.load()['active']),display(self.candidate),fromfile='active',tofile='candidate',lineterm='')))
        elif t[0]=='rollback' and len(t)==2:
            n=int(t[1]);s=self.store.load()
            if n<0 or n>len(s['history']):raise ValueError('rollback unavailable')
            self.candidate=copy.deepcopy(s['active'] if n==0 else s['history'][n-1])
        elif t==['commit','check']:self.store.cfg.validate(self.candidate);print('configuration check succeeds')
        elif t==['commit'] or t[:2]==['commit','confirmed']:
            minutes=None
            if t!=['commit']:
                if len(t)>3:raise ValueError('usage: commit confirmed [minutes]')
                if isinstance(self.store.backend,LabBackend):raise ValueError('confirmed commits are not supported with a temporary lab; use commit')
                minutes=int(t[2]) if len(t)==3 else 10
                if not 1<=minutes<=60:raise ValueError('confirmation timeout must be 1-60 minutes')
            s=self.store.commit(self.candidate,self.revision,minutes);self.revision=s['revision']
            print('commit complete'+(f'; automatic rollback in {minutes} minutes unless confirmed' if minutes else ''))
        elif t in (['exit'],['exit','discard']):
            if self.context and t==['exit']:self.context=[];return
            if t==['exit'] and self.candidate!=self.store.load()['active']:raise ValueError('uncommitted changes; commit or exit discard')
            self.editing=False;self.context=[]
        else:raise ValueError('unsupported command; press Tab or use ?')
    def loop(self):
        print('NullOS '+VERSION+' — experimental software switch. Tab completes; ? lists choices.')
        while True:
            try:
                hostname=self.store.cfg.validate(self.store.load()['active'])['hostname']
                if self.editing:print('[edit'+(' '+quote(self.context) if self.context else '')+']')
                line=input(f'{os.environ.get("SUDO_USER",getpass.getuser())}@{hostname}{"#" if self.editing else ">"} ')
                self.execute(line)
            except EOFError:return
            except KeyboardInterrupt:print()
            except (ValueError,OSError,subprocess.SubprocessError) as e:print('error:',e)

def main():
    p=argparse.ArgumentParser();p.add_argument('--demo',action='store_true');p.add_argument('--ports',type=int,default=None);p.add_argument('--state-dir');p.add_argument('--boot',action='store_true');p.add_argument('--watch',action='store_true');args=p.parse_args()
    if not args.demo and os.geteuid()!=0:p.error('root required; use --demo to test without networking changes')
    root=Path(args.state_dir or (str(Path.home()/'.nullos-demo') if args.demo else '/var/lib/nullos'))
    if args.ports is not None and (not args.demo or args.ports<1): p.error('--ports requires --demo and a positive count')
    inventory=root/'ports.json'
    ports=(read(inventory,{f'ge-0/0/{i}':f'demo{i}' for i in range(48)}) if args.demo else read(Path('/etc/nullos/ports.json'),{}))
    if args.demo and args.ports is not None:
        proposed={f'ge-0/0/{i}':f'demo{i}' for i in range(args.ports)}
        state=read(root/'state.json',{'active':[],'history':[],'pending':None})
        configs=[state['active']]+state['history']
        if state.get('pending'): configs.append(state['pending']['previous'])
        if any(x[:1]==['interfaces'] and x[1] in ports and x[1] not in proposed for cfg in configs for x in cfg):
            p.error('cannot remove ports referenced by saved configuration or rollback history; use a separate --state-dir')
        ports=proposed
    if args.demo: atomic(inventory,ports)
    if not ports: p.error('configure at least one port')
    if set(ports)!={f'ge-0/0/{i}' for i in range(len(ports))} or len(set(ports.values()))!=len(ports):p.error('invalid port mapping')
    if not args.demo:
        for name in ports.values():
            if not re.fullmatch(r'[A-Za-z0-9_.-]{1,15}',name) or name in ('lo','nsw0','nmgmt0') or not Path('/sys/class/net',name).exists():p.error('invalid or missing Linux interface')
    store=Store(root,ports,args.demo)
    if args.boot:store.recover(boot=True)
    elif args.watch:
        while True:
            try:store.recover()
            except Exception as e:print('recovery error:',e,flush=True)
            time.sleep(1)
    else:
        try:CLI(store).loop()
        finally:
            if isinstance(store.backend,LabBackend):store.backend.stop()
if __name__=='__main__':main()
