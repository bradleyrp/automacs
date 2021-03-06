#!/usr/bin/env python

"""
Command-line interface
----------------------

A collection of (helpful) command-line utilities. The interface is managed by the :any:`makeface <makeface>` 
module.
"""

import os,sys,subprocess,re,time,glob,shutil,json,copy

__all__ = ['locate','flag_search','config','watch','layout','gromacs_config',
	'setup','notebook','upload','download','cluster','submit','gitcheck','gitpull','rewrite_config',
	'codecheck','collect_parameters','write_continue_script','show_kickstarters','hardstart']

from datapack import asciitree,delve,delveset,yamlb,jsonify,check_repeated_keys
from makeface import fab
from control import preplist

def get_amx():
	"""
	Wrapper for getting amx since command-line calls lack the null string in the path.
	Anything that calls this function requires all of the packages e.g. scipy.
	"""
	#---! Note that something is adding '' to sys.path elsewhere because the runner imports always work.
	#---! ...this isn't a problem but it could become one
	paths = list(sys.path)
	#---command-line calls like this one are missing '' from the path
	if '' not in sys.path: sys.path.insert(0,'')
	import amx
	sys.path = paths
	return amx

def locate(keyword):
	"""
	Locate the source code for a python function which is visible to the controller.

	Parameters
	----------
	keyword : string
		Any part of a function name (including regular expressions)

	Notes
	-----
	This controller script is grepped by the makefile in order to expose its python functions to the makefile
	interface so that users can run e.g. "make program protein" in orer to access the ``program`` function
	above. The ``makeface`` function routes makefile arguments and keyword arguments into python's functions.
	The makefile also detects python functions from any scripts located in amx/procedures/extras.
	The ``locate`` function is useful for finding functions which may be found in many parts of the automacs
	directory structure.
	"""
	os.system('find ./ -name "*.py" | xargs egrep --color=always "(def|class) \w*%s\w*"'%keyword)

def flag_search(keyword):
	"""
	Search the codebase for cases where a settings flag is requested.
	"""
	keyword_ambig = re.sub('( |_)','[_ ]+',keyword)
	cmd = 'egrep -nr --color=always "\.((q|get)\(\')?%s" * -R'%keyword_ambig
	print('[NOTE] running "%s"'%cmd)
	os.system(cmd)

def config():
	"""
	Print the config in a tree form using the (hidden) asciitree function above.
	"""
	config_this = {}
	with open('config.py') as fp: config_this = eval(fp.read())
	asciitree(config_this)

def watch():
	"""
	Wrapper for a command which tails the oldest mdrun command.
	"""
	#---original command works well for watching the last mdrun but doesn't monitor the files
	cmd = 'find ./ -name "log-mdrun*" | xargs ls -ltrh | '+\
		'tail -n 1 | awk \'{print $9}\' | xargs tail -f'
	os.system(cmd)

def layout(name=None):
	"""Map all teh codes."""
	#---collect python scripts
	codes = []
	for rn,dns,fns in os.walk('.'):
		codes_here = [i for i in fns if os.path.splitext(i)[-1]=='.py']
		codes.extend([os.path.join(rn,f) for f in codes_here])
	codetoc = {}
	for fn in codes:
		route = fn.split(os.sep)
		delveset(codetoc,*route,value=[])
	for fn in codes:
		with open(fn) as fp: text = fp.read()
		funcs = [j.group(1) for j in [re.match('^((?:def|class)\s*.*?)\(',t) for t in text.splitlines()] if j]
		for func in funcs:
			route = fn.split(os.sep)
			delve(codetoc,*route).append(func)
	#---sloppy
	codetoc = codetoc['.']
	if not name: asciitree(codetoc)
	else: asciitree(codetoc[name])

def gromacs_config(where=None):
	"""
	Make sure there is a gromacs configuration available.
	"""
	config_std = '~/.automacs.py'
	config_local = 'gromacs_config.py'
	#---instead of using config.py, we hard-code a global config location
	#---the global configuration is overridden if a local config file exists
	#---we source the config from a default copy in the amx directory
	default_config = 'gromacs/gromacs_config.py.bak'
	if where:
		if where not in ['home','local']:
			#---! print the error message here?
			raise Exception('[ERROR] options are `make gromacs_config local` or `make gromacs_config home`. '+
				'the argument tells us whether to write a local (%s) or global (%s) configuration'%
				(config_local,config_std))
		else:
			dest_fn = config_local if where=='local' else config_std
			dest_fn_abs = os.path.abspath(os.path.expanduser(dest_fn))
			shutil.copyfile(os.path.join(os.path.dirname(__file__),default_config),dest_fn_abs)
			return dest_fn_abs
	config_std_path = os.path.abspath(os.path.expanduser(config_std))
	config_local_path = os.path.abspath(os.path.expanduser(config_local))
	has_std = os.path.isfile(config_std_path)
	has_local = os.path.isfile(config_local_path)
	if has_local: 
		print('[NOTE] using local gromacs configuration at ./gromacs_config.py')
		return config_local_path
	elif has_std: 
		print('[NOTE] using global gromacs configuration at ~/.automacs.py')
		return config_std_path
	else: 
		import textwrap
		msg = ("we cannot find either a global (%s) or local (%s) "%(config_std,config_local)+
			"gromacs path configuration file. the global location (a hidden file in your home directory) "+
			"is the default, but you can override it with a local copy. "+
			"run `make gromacs_config home` or `make gromacs_config local` to write a default "+
			"configuration to either location. then you can continue to use automacs.")
		raise Exception('\n'.join(['[ERROR] %s'%i for i in textwrap.wrap(msg,width=80)]))

def rewrite_config(source='config.py'):
	"""
	Reformat the config.py file in case you change it and want it to look normal again.
	"""
	if not os.path.isfile(os.path.abspath(source)): raise Exception('cannot find file "%s"'%source)
	try: config = eval(open(os.path.abspath(source)).read())
	except: raise Exception('[ERROR] failed to read master config from "%s"'%source)
	import pprint
	#---write the config
	with open(source,'w') as fp: 
		fp.write('#!/usr/bin/env python -B\n'+str(pprint.pformat(config,width=110)))

def show_kickstarters():
	"""
	Print the available kickstarters for the user.
	"""
	from makeface import import_remote
	mod = import_remote('amx/kickstarts.py')
	for key,val in mod['kickstarters'].items():
		print('[KICKSTARTER] "%s"\n%s'%(key,val))

def setup(name=''):
	"""
	Run this after cloning a fresh copy of automacs in order to clone some standard
	"""
	from makeface import import_remote
	mod = import_remote('amx/kickstarts.py')
	kickstarters = mod['kickstarters']
	if not name: 
		raise Exception('you must specify a setup script: %s'%(', '.join(kickstarters.keys())))
	if name not in kickstarters: raise Exception('cannot find kickstarter script: %s'%name)
	with open('kickstart.sh','w') as fp:
		fp.write("#!/bin/bash\n\nset -e\n\n"+kickstarters[name])
	subprocess.check_call('bash kickstart.sh',shell=True)
	os.remove('kickstart.sh')
	print('[WARNING] new users must run `make gromacs_config (local|home)` '+
		'to tell automacs how to find gromacs.')
	print('[STATUS] setup is complete')

def serial_number():
	"""
	Add a random serial number to the simulation.
	This function adds the ``serial`` variable to the state.
	!Note that we must propagate the serial on subsequent steps.
	!Requires state hence you should import amx in the calling function e.g. upload.
	"""
	amx = get_amx()
	path = list(sys.path)
	sys.path.insert(0,'')
	from runner.states import state_set_and_save
	sys.path = path
	serial = amx.state.get('serial',None)
	if not serial:
		import random
		serialno = random.randint(0,10**9)
		state_set_and_save(amx.state,serial=serialno)
	return amx.state['serial']

def make_timestamp():
	"""Make timestamps for upload/download logs."""
	import datetime
	ts = datetime.datetime.fromtimestamp(time.time()).strftime('%Y.%m.%d.%H%M')
	return ts

def upload(alias,path='~',sure=False,state_fn='state.json',bulk=False):
	"""
	Upload the data to a supercomputer.
	!Bulk is not implemented yet.
	!Note that putting sure before path ruins the argument handling hence makeface needs fix
	"""
	amx = get_amx()
	#---! a rare connection down to gromacs which needs to be revised
	from amx.gromacs.gromacs_commands import gmx_get_last_call
	serial_number()
	last_step = amx.state['here']
	gmx_get_last_call('mdrun',this_state=amx.state)
	#---upload requires knowledge of the last mdrun so we only send up cpt and tpr
	last_mdrun = gmx_get_last_call('mdrun',this_state=amx.state)
	restart_fns = [last_step+i for i in [last_mdrun['flags']['-s'],last_mdrun['flags']['-cpo']]]
	#---upload cluster files if they are already prepared by users who wish to run cluster before sending it
	for fn in ['script-continue.sh','cluster-continue.sh']:
		if os.path.isfile(os.path.join(last_step,fn)):
			restart_fns.append(os.path.join(last_step,fn))
	if not all([os.path.isfile(fn) for fn in restart_fns]):
		error = '[STATUS] could not find necessary upload files from get_last_gmx_call'+\
			"\n[ERROR] missing: %s"%str([fn for fn in restart_fns if not os.path.isfile(fn)])
		raise Exception(error)
	#---get defaults list
	default_fns,default_dirs = ['makefile','config.py','state.json'],['amx','runner']
	if os.path.isfile('gromacs_config.py'): default_fns += ['gromacs_config.py']
	default_fns += [os.path.join(root,fn) for dn in default_dirs for root,dirnames,fns 
		in os.walk(dn) for fn in fns]
	default_fns = [fn for fn in default_fns if not re.match('.+\.pyc$',fn) and not re.search('/\.git/',fn)]
	#---write list to upload
	with open('uploads.txt','w') as fp: 
		for fn in restart_fns+default_fns: fp.write(fn+'\n')
	cwd = os.path.basename(os.path.abspath(os.getcwd()))
	if not sure:
		cmd = 'rsync -%s%s ../%s %s:%s/%s'%(
			'avin',' --files-from=uploads.txt' if not bulk else ' --exclude=.git',cwd,
			alias,path,cwd if not bulk else '')
		print(cmd)
		p = subprocess.Popen(cmd,shell=True,cwd=os.path.abspath(os.getcwd()),executable='/bin/bash')
		log = p.communicate()
	if (sure or (input if sys.version_info>(3,0) else raw_input)
		('\n[QUESTION] continue [y/N]? ')[:1] not in 'nN'):
		cmd = 'rsync -%s%s ../%s %s:%s/%s'%(
			'avi',' --files-from=uploads.txt' if not bulk else ' --exclude=.git',cwd,
			alias,path,cwd if not bulk else '')
		print(cmd)
		p = subprocess.Popen(cmd,shell=True,cwd=os.path.abspath(os.getcwd()),executable='/bin/bash')
		log = p.communicate()
		if not bulk: os.remove('uploads.txt')
	if p.returncode == 0 and last_step:
		destination = '%s:%s/%s'%(alias,path,cwd)
		ts = make_timestamp()
		from runner.states import state_set_and_save
		this_upload = dict(to=destination,when=ts)
		state_set_and_save(amx.state,upload=this_upload)
		upload_history = amx.state.get('upload_history',[])
		upload_history.append(this_upload)
		state_set_and_save(amx.state,upload_history=upload_history)
	elif p.returncode != 0: 
		print("[STATUS] upload failure (not logged)")
		sys.exit(1)

def download(sure=False,state_fn='state.json'):
	"""
	Download a simulation from the cluster if it has already been uploaded.
	"""
	amx = get_amx()
	if 'upload' not in amx.state: 
		raise Exception('cannot find "upload" key in the state. did you upload this already?')
	state_merge = dict()
	state_merge['upload'] = copy.deepcopy(amx.state.upload)
	state_merge['upload_history'] = amx.state.get('upload_history',[])
	destination = amx.state['upload']['to']
	serialno = serial_number()
	print("[STATUS] the state says that this simulation (#%d) is located at %s"%(serialno,destination))
	try:
		if not sure:
			cmd = 'rsync -avin --progress %s/* ./'%destination
			print('[STATUS] running: "%s"'%cmd)
			p = subprocess.Popen(cmd,shell=True,cwd=os.path.abspath(os.getcwd()))
			log = p.communicate()
			if p.returncode != 0: raise
		if (sure or (input if sys.version_info>(3,0) else raw_input)
			('\n[QUESTION] continue [y/N]? ')[:1] not in 'nN'):
			cmd = 'rsync -avi --progress %s/* ./'%destination
			print('[STATUS] running "%s"'%cmd)
			p = subprocess.Popen(cmd,shell=True,cwd=os.path.abspath(os.getcwd()))
			log = p.communicate()
		#---if we get a state, add the upload history back and write it
		if os.path.isfile('state.json'):
			from runner.datapack import DotDict
			from runner.states import statesave
			state = DotDict(**json.load(open(state_fn)))
			if 'upload' not in state: state.upload = state_merge['upload']
			#---! should we check the destinations?
			else: pass 
			if 'upload_history' not in state: state.upload_history = state_merge['upload_history']
			else: raise Exception('development error. need to merge upload history here.')
			ts = make_timestamp()
			state.upload_history.append({'from':destination,'to':'here','when':ts})
			statesave(amx.state)
	except Exception as e:
		import traceback
		s = traceback.format_exc()
		print("[TRACE] > "+"\n[TRACE] > ".join(s.split('\n')))
		print("[ERROR] failed to find simulation")
		print("[NOTE] find the data on the remote machine via \"find ./ -name serial-%s\""%serialno)
		sys.exit(1)

def write_continue_script(hostname=None,overwrite=False,gmxpaths=None):
	"""
	Write the continue script if it does not yet exist.
	Note that this script wraps the same function in amx.continue_script for the CLI.
	"""
	#---! a rare connection down to gromacs which needs to be revised
	from amx.gromacs.calls import gmx_get_machine_config
	machine_configuration = gmx_get_machine_config(hostname=hostname)
	sys.path.insert(0,'amx')
	here = globals()['state']['here'] if 'state' in globals() else None
	#---! a rare connection down to gromacs which needs to be revised
	from amx.gromacs.continue_script import write_continue_script_master
	script_fn = write_continue_script_master(
		machine_configuration=machine_configuration,here=here,gmxpaths=gmxpaths)
	return script_fn

def cluster(hostname=None,overwrite=True):
	"""
	Write a cluster header according to the machine configuration.
	The machine configuration is read from ``~/.automacs.py`` but can be overriden by a local ``config.py``
	which can be created with :meth:`make config local <amx.controller.config>`.
	This code will concatenate the cluster submission header with a continuation script.
	Note that we do not log this operation because it only manipulates BASH scripts.
	"""
	amx = get_amx()
	#---! a rare connection down to gromacs which needs to be revised
	from amx.gromacs.gromacs_commands import gmx_get_last_call
	if hostname: 
		#---warn the user that specifying hostname from the commandline might show warnings, however
		#---...it is still very useful to prepare the cluster scripts before uploading to clusters
		print(fab('[WARNING]','white_black')+' running `make cluster <hostname>` might throw errors '
			'on modules which are not locally available')
	#---! a rare connection down to gromacs which needs to be revised
	from amx.gromacs.calls import gmx_get_machine_config
	machine_configuration = gmx_get_machine_config(hostname=hostname)
	if not 'cluster_header' in machine_configuration: 
		raise Exception('no cluster information. add this machine to `machine_configuration` in '
			'either `./gromacs_config.py` or `~/.automacs.py` and '
			'make sure that it includes `cluster_header`')
	head = machine_configuration['cluster_header']
	for key,val in machine_configuration.items(): head = re.sub(key.upper(),str(val),head)
	with open('cluster-header.sh','w') as fp: fp.write(head)
	print('[STATUS] wrote cluster-header.sh')
	#---get the most recent step (possibly duplicate code from base)
	last_step = amx.state.here if 'here' in amx.state else False
	#---gmxpaths can be saved to the state or retrieved automatically
	try: gmxpaths = get_gmx_paths(hostname=hostname,override=True if hostname else False)
	except: gmxpaths = amx.state.gmxpaths
	#---override the mdrun command if the cluster definition says so
	if 'mdrun_command' in machine_configuration: gmxpaths['mdrun'] = machine_configuration['mdrun_command']
	if last_step:
		#---this script requires a continue script to be available. overwrites by default
		if not 'continuation_script' in amx.state or overwrite: 
			script_continue_fn = write_continue_script(hostname=hostname,overwrite=True,gmxpaths=gmxpaths)
		else: script_continue_fn = amx.state.here+amx.state.continuation_script
		#---code from base.functions.write_continue_script to rewrite the continue script
		with open(script_continue_fn,'r') as fp: lines = fp.readlines()
		#---! a rare connection down to gromacs which needs to be revised
		from amx.gromacs.continue_script import interpret_walltimes
		maxhours = interpret_walltimes(machine_configuration.get('walltime',24))['maxhours']
		#---make a jobname from the directory name, which should be a unique identifier for the job
		try: jobname = os.path.basename(os.getcwd())
		except: jobname = 'gmxjob'
		settings = {'maxhours':maxhours,
			'tpbconv':gmxpaths['tpbconv'],
			'mdrun':gmxpaths['mdrun'],
			'jobname':jobname}
		if 'nprocs' in machine_configuration: settings['nprocs'] = machine_configuration['nprocs']
		else: settings['nprocs'] = machine_configuration['ppn']*machine_configuration['nnodes']
		#---! how should we parse multiple modules from the machine_configuration?
		if 'modules' in machine_configuration:
			need_modules = machine_configuration['modules']
			need_modules = [need_modules] if type(need_modules)==str else need_modules
			for m in need_modules: head += "module load %s\n"%m
		for key in ['extend','until']: 
			if key in machine_configuration: settings[key] = machine_configuration[key]
		# if until is in the machine configuration we also set mode to match
		#! this feature needs tested against the new continue script
		if 'until' in machine_configuration: settings['mode'] = 'until' 
		#---! must intervene above to come up with the correct executables
		setting_text = '\n'.join([str(key.upper())+'='+('"' if type(val)==str else '')+
			str(val)+('"' if type(val)==str else '') for key,val in settings.items()])
		lines = map(lambda x: re.sub('#---SETTINGS OVERRIDES HERE$',setting_text,x),lines)
		script_fn = 'script-continue.sh'
		cont_fn = last_step+script_fn
		print('[STATUS] %swriting %s'%('over' if os.path.isfile(last_step+script_fn) else '',cont_fn))
		with open(last_step+script_fn,'w') as fp:
			for line in lines: fp.write(line)
		os.chmod(last_step+script_fn,0o744)
		#---code above from base.functions.write_continue_script		
		with open(cont_fn,'r') as fp: continue_script = fp.read()
		continue_script = re.sub('#!/bin/bash\n','',continue_script)
		cluster_continue = os.path.join(last_step,'cluster-continue.sh')
		print('[STATUS] writing %s'%cluster_continue)
		print('[NOTE] you should submit that script from %s or try `make submit`'%last_step)
		#---the header gets settings substitutions
		for key,val in settings.items(): head = re.sub(key.upper(),str(val),head,re.M)
		with open(cluster_continue,'w') as fp: fp.write(head+continue_script)
	#---for each python script in the root directory we write an equivalent cluster script
	pyscripts = glob.glob('script-*.py')
	if len(pyscripts)>0: 
		with open('cluster-header.sh','r') as fp: header = fp.read()
	for script in pyscripts:
		name = re.findall('^script-([\w-]+)\.py$',script)[0]
		with open('cluster-%s.sh'%name,'w') as fp:
			fp.write(header+'\n')
			fp.write('python script-%s.py &> log-%s\n'%(name,name))
		print('[STATUS] wrote cluster-%s.sh'%name)

def submit():
	"""
	Submits the job to the queue. This saves you from changing into the latest step directory.
	"""
	amx = get_amx()
	here = amx.state.here
	if not os.path.isfile(here+'cluster-continue.sh'):
		raise Exception('[ERROR] cannot find "cluster-continue.sh" in the last step directory (%s). '
			%here+'try running `make cluster` to generate it.')
	#---! a rare connection down to gromacs which needs to be revised
	from amx.gromacs.calls import gmx_get_machine_config
	machine_config = gmx_get_machine_config()
	cmd = '%s cluster-continue.sh'%machine_config.get('submit_command','qsub')
	print('[STATUS] running "%s"'%cmd)
	subprocess.check_call(cmd,cwd=here,shell=True)

def notebook(procedure,rewrite=False,go=False,name='notebook.ipynb'):
	"""
	Make an IPython notebook for a particular procedure.
	"""
	if not rewrite and os.path.isfile(name): raise Exception('refusing to overwrite %s'%name)
	if rewrite: subprocess.check_call('make clean sure',shell=True)
	#---run make prep per usual
	subprocess.check_call('make prep %s'%procedure,shell=True)
	#---! not sure how to get the names from an integer sent to prep above
	if procedure.isdigit(): raise Exception('integers not allowed. use the full name.')
	import nbformat as nbf
	import json,pprint
	nb = nbf.v4.new_notebook()
	#---write the header
	text = "# %s\n"%procedure +\
		"\n*an AUTOMACS script*\n\n**Note:** you should only changes settings blocks before executing "+\
		"these codes in the given sequence."
	nb['cells'].append(nbf.v4.new_markdown_cell(text))
	#---always clean and prepare again
	reset = "%%capture\n! "+"make clean sure && make prep %s"%procedure
	nb['cells'].append(nbf.v4.new_code_cell(reset))
	#---! autoscrolling option causes overlaps
	autoscroll = "%%html\n"+"<style> .output_wrapper, .output {height:auto!important;max-height:100px; }"+\
		" .output_scroll {box-shadow:none!important;webkit-box-shadow:none!important;}</style>"
	#---! diabled
	if False: nb['cells'].append(nbf.v4.new_code_cell(autoscroll))
	#---note that we use inference to distinguish metarun from run
	#---! quick scripts may not work with the notebook format
	#---loop over valid experiment files
	expt_fns = sorted(glob.glob('expt*.json'))
	if not expt_fns: raise Exception('cannot find experiments')
	is_metarun = len(expt_fns)>1
	for stepno,expt_fn in enumerate(expt_fns):
		#---unpack the expt.json file into readable items
		with open(expt_fn) as fp: expt = json.loads(fp.read())
		script_fn = expt['script']
		#---settings block gets its own text
		settings = expt.pop('settings')
		settings_block = 'settings = """%s"""'%settings
		if 'settings_overrides' in expt: 
			settings_block += '\n\nsettings_overrides = """%s"""'%expt.pop('settings_overrides')
		#---warning to the user about what happens next
		if is_metarun: 
			step_name = yamlb(settings)['step']
			nb['cells'].append(nbf.v4.new_markdown_cell('# step %d: %s'%(stepno+1,step_name)))
		nb['cells'].append(nbf.v4.new_code_cell(settings_block))
		#---rewrite metadata
		rewrite_expt = "import json,shutil,os\nsets = dict(settings=settings)\n"+\
			"if 'settings_overrides' in globals():\n\tsets['settings_overrides'] = settings_overrides"+\
			"\n\tdel settings_overrides\n"+\
			"expt = dict(metadata,**sets)\n"+\
			"with open('expt.json','w') as fp: json.dump(expt,fp)"+\
			"\nif not os.path.isfile('script.py'): shutil.copyfile(expt['script'],'script.py');"
		nb['cells'].append(nbf.v4.new_code_cell('#---save settings (run this cell without edits)\n'+
			'metadata = %s\n'%pprint.pformat(expt)+rewrite_expt))
		with open(script_fn) as fp: text = fp.read()
		regex_no_hashbang = '^#!/usr/bin/env python\n\s*\n(.+)\n?$'
		try: code = re.match(regex_no_hashbang,text,re.M+re.DOTALL).group(1).strip('\n')
		except: code = text
		#---time the run/step
		code = "%%time\n"+code
		#---if this step in the metarun is a standard run we write the code block
		if 'quick' in expt: nb['cells'].append(nbf.v4.new_code_cell('! python -B script.py'))
		#---standard runs are written directly to cells
		else: nb['cells'].append(nbf.v4.new_code_cell(code))
		#---add a coda if available
		#---! note that this feature requires extra routing via controlspec.py
		if 'jupyter_coda' in expt: nb['cells'].append(nbf.v4.new_code_cell(expt['jupyter_coda'].strip('\n')))

	#---write the notebook
	with open(name,'w') as f: nbf.write(nb,f)
	#---run the notebook directly with os.system so INT works
	if go: os.system('jupyter notebook %s'%name)
	else: print('[STATUS] notebook is ready at %s. '%name+
		'run this manually or use the "go" flag next time.')

def gitcheck():
	"""
	Check all git repos for changes.
	"""
	from makeface import fab
	with open('config.py') as fp: config_this = eval(fp.read())
	#---loop over modules and check the status
	for far,near in [('.','.')]+config_this['modules']:
		print('[STATUS] checking `git status` of %s'%
			fab(near if near!='.' else 'automacs (root)','red_black'))
		subprocess.check_call('git status',cwd=near,shell=True)
	print('[STATUS] the above messages will tell you if you are up to date')

def gitpull():
	"""
	Pull in each git module.
	"""
	with open('config.py') as fp: config_this = eval(fp.read())
	#---pull the main module
	subprocess.check_call('git pull',cwd='.',shell=True)
	#---loop over modules and pull
	for far,near in config_this['modules']:
		print('[STATUS] running `git pull` at %s'%near)
		subprocess.check_call('git pull',cwd=near,shell=True)

def codecheck(fn):
	"""
	Check a file for evaluation from the command line.
	This utility is useful when you want to see if a file with dict literals passes the JSON check.
	"""
	if not os.path.isfile(fn): raise Exception('cannot find file %s'%fn)
	with open(fn) as fp: text = fp.read()
	print('[NOTE] parsing with python')
	result = eval(text)
	print('[NOTE] parsing with jsonify')
	result = jsonify(text)
	print('[NOTE] parsing with check_repeated_keys')
	check_repeated_keys(text,verbose=True)

def collect_parameters():
	"""
	Scan for all parameters files.
	"""
	#---! is it okay to import acme here (or anywhere in cli)?
	from acme import read_inputs,get_path_to_module
	inputlib = read_inputs()
	params_fns = sorted(list(set([os.path.join('.',get_path_to_module(v['params']))
		if re.match('^@',v['params']) 
		else os.path.join(v['cwd'],v['params']) 
		for k,v, in inputlib.items() if 'params' in v and v['params']])))
	asciitree({'PARAMETER SPECIFICATIONS':params_fns})

def hardstart():
	"""
	Generate a state.json to initiate a hard restart.
	This functionality is useful for dropping CPT and TPR files into a new directory for a continuation.
	"""
	if os.path.isfile('state.json'): raise Exception('cannot hard restart if state.json is here')
	#---figure out the last step folder
	dns = [fn for fn in glob.glob('*') if re.match('s\d+-.+',fn) and os.path.isdir(fn)]
	dns = sorted(dns,key=lambda x:os.path.getmtime(x))
	here = os.path.join(dns[-1],'')
	from makeface import import_remote
	get_gmx_paths = import_remote('amx/gromacs/calls.py')['gmx_get_paths']
	gmxpaths = get_gmx_paths()
	state = dict(here=here,gmxpaths=gmxpaths)
	state['history_gmx'] = [{'call':'mdrun','flags':{}}]
	#---detect the last mdrun by modification time
	for suf in ['cpt','tpr']:
		fns = sorted([fn for fn in glob.glob(os.path.join(here,'*.%s'%suf)) 
			if re.match('md\.part\d{4}\.%s'%suf,os.path.basename(fn))],key=lambda x:os.path.getmtime(x))
		if not fns: raise Exception('cannot find a %s file in %s'%(suf,here))
		state['history_gmx'][-1]['flags'][{'cpt':'-cpo','tpr':'-s'}[suf]] = os.path.basename(fns[-1])
	with open('state.json','w') as fp: fp.write(json.dumps(state))
