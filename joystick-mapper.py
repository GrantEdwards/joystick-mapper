#!/usr/bin/python

import sys,evdev,copy,time,collections,argparse,traceback
from evdev import ecodes
from evdev.ecodes import EV_ABS, EV_KEY, EV_SYN, ABS, KEY, BTN

EV_PULSE = 987654321 # used for "key" output we just want to pulse

write = sys.stdout.write

KEYBTN = KEY | BTN

parser = argparse.ArgumentParser(prog=sys.argv[0], description='Joystick channel mapper')

parser.add_argument('-c', '--config-file', default=".joystick-mapperrc")
parser.add_argument('-D', '--device-list', action='store_true')
parser.add_argument('-i', '--input-name', type=str)
parser.add_argument('-I', '--input-specs', action='store_true')
parser.add_argument('-o', '--output-name', type=str)
parser.add_argument('-O', '--output-specs', action='store_true')
parser.add_argument('-m', '--monitor-inputs', action='store_true')
parser.add_argument('-M', '--monitor-outputs', action='store_true')
args = parser.parse_args()

if args.device_list:
    for device in [evdev.InputDevice(path) for path in evdev.list_devices()]:
        print(device.name)
    sys.exit(0)

# counters for auto-allocated axes and buttons
abscode =  -1
btncode = 255


def code_for_absname(name):
    global abscode
    if name.startswith("ABS_#"):
        return int(name[5:])
    if name.startswith("ABS_"):
        return ecodes.ecodes[name]
    abscode += 1
    return abscode

def code_for_btnname(name):
    global btncode
    if name.startswith("BTN_#") or name.startswith("KEY_#"):
        return int(name[5:])
    if name.startswith("BTN_") or name.startswith("KEY_"):
        return ecodes.ecodes[name]
    btncode += 1
    return btncode

# read config file into list of 'Outspec' named-tuples
Outspec = collections.namedtuple('Outspec', ['name', 'type', 'code', 'min', 'max', 'vexpr', 'vcode', 'inset'])
outputs = []
with open(args.config_file,'r') as f:
    linenum = 0
    for line in f:
        linenum += 1
        line = line.strip()
        if line.startswith('#') or line == '':
            pass
        elif line.startswith('input:'):
            if not args.input_name:
                args.input_name = line.split(':')[1].strip()
        elif line.startswith('output:'):
            if  not args.output_name:
                args.output_name = line.split(':')[1].strip()
        elif '=' in line:
            try:
                oname, ovexpr = [s.strip() for s in line.split('=',1)]
                ovcode = compile(ovexpr, '', 'eval')
                oinset = set(ovcode.co_names)
                omin,omax = None,None
                if '[' in oname and oname.endswith(']'):
                    oname,minmax = [s.strip() for s in oname.split('[')]
                    minmax = minmax[:-1].split(':')
                    if len(minmax) != 2:
                        print('Invalid range specification at line {linenum}:\n{line}\n')
                        sys.exit(1)
                    omin,omax = map(int,minmax)
                    otype = EV_ABS
                    ocode = code_for_absname(oname)
                elif oname.startswith('P:'):
                    oname = oname[2:].strip()
                    otype = EV_PULSE
                    ocode = code_for_btnname(oname)
                else:
                    otype = EV_KEY
                    ocode = code_for_btnname(oname)
                outputs.append(Outspec(oname, otype, ocode, omin, omax, ovexpr, ovcode, oinset))
            except Exception as e:
                print(f'Invlaid config at line {linenum}:\n{line}\n')
                traceback.print_exc()
                sys.exit(1)
        else:
            print(f'Invalid config at line {linenum}:\n{line}\n')
            sys.exit(1)

# find input device

for device in [evdev.InputDevice(path) for path in evdev.list_devices()]:
    if args.input_name in device.name:
        indev = device
        print(f"using input device: {indev.name}")
        break
else:    
    print(f'Device "{args.input_name}" not found')
    sys.exit(1)

incaps = indev.capabilities()

# define friendly names for inputs: a0-aN, s0-sN along with dicts to map input
# code values to our names

cn = [(c,f'a{i}') for (i,(c,a)) in enumerate(incaps[EV_ABS])]
absname = dict(cn)
innames = [n for c,n in cn]  # names in order

cn = [(c,f's{i}') for (i,c) in enumerate(incaps[EV_KEY])]
keyname = dict(cn)
innames += [n for c,n in cn]

# return "official" name of key/channel if one is defined
def GetName(d,c):
    r = d.get(c,"?")
    if isinstance(r, str):
        return r
    return r[0]

# print in/out specs if requested by user (then exit)

if args.input_specs:
    print("Input Axes:")
    for c,info in incaps[EV_ABS]:
        print(f'  {absname[c]:>3}: ({c},{GetName(ABS,c)}) {info}')
    print("Input Switches:")
    for k in incaps[EV_KEY]:
        print(f'  {keyname[k]:>3}: ({k},{GetName(KEYBTN,k)})')

if args.output_specs:
    print('Output Axes:')
    for o in [o for o in outputs if o.type == EV_ABS]:
        print(f' {o.name} ({o.code},{GetName(ABS,o.code)}) [{o.min}:{o.max}] = {o.vexpr}')
    print('Output Switches:')
    for o in [o for o in outputs if o.type == EV_KEY]:
        print(f' {o.name} ({o.code},{GetName(KEYBTN,o.code)}) = {o.vexpr}')
    print('Output Pulses:')
    for o in [o for o in outputs if o.type == EV_PULSE]:
        print(f' {o.name} ({o.code},{GetName(KEYBTN,o.code)}) = {o.vexpr}')

if args.input_specs or args.output_specs:
    sys.exit(0)
    
# dict where input values are stored
in_val = {}

# initialize input values
for c,n in absname.items():
    in_val[n] = indev.absinfo(c).value

for n in keyname.values():
    in_val[n] = 0

for k in indev.active_keys():
    in_val[keyname[k]] = 1

# create capabilities dict for output device
outcaps = {EV_ABS: [], EV_KEY: []}
for o in outputs:
    if o.type == EV_KEY or o.type == EV_PULSE:
        outcaps[EV_KEY].append(o.code)
    elif o.type == EV_ABS:
        absinf = evdev.AbsInfo(value=(o.min+o.max)//2, min=o.min, max=o.max, resolution=0, fuzz=0, flat=0)
        outcaps[EV_ABS].append( (o.code, absinf) )

# create output device        
outdev = evdev.UInput(outcaps, name=args.output_name, version=0x3)
    
# in_val is a "safe" global context for eval with limited builtins
# available

in_val['__builtins__'] = {'int':int}

# set containing input names that have changed since last SYN was received

changeset = set()

if args.monitor_inputs:
    def monitorinvals():
        write(' '.join(f'{n}={in_val[n]:<3}' for n in innames))
else:
    def monitorinvals():
        pass

# dict for storing output values so we can print them and detect transitions
out_val = {}

def update_output(o):
    val = eval(o.vcode, in_val, None)
    if val != out_val[o.name]:
        out_val[o.name] = val
        if o.type == EV_PULSE:
            if val:
                outdev.write(EV_KEY, o.code, 1)
                outdev.write(EV_KEY, o.code, 0)
        else:
            outdev.write(o.type, o.code, val)

if args.monitor_outputs:
    def monitoroutvals():
        write(' OUT: ')
        write(' '.join(f'{o.name}={out_val[o.name]:<3}' for o in outputs))
else:
    def monitoroutvals():
        pass    

if args.monitor_outputs or args.monitor_inputs:
    def monitorcr():
        write('\r')
else:
    def monitorcr():
        pass

# initialize output values
for o in outputs:
    out_val[o.name] = None

# send initial output values
for o in outputs:
    update_output(o)
outdev.syn()

# Main loop that reads input values and saves them.
# When a SYNC is received: update outputs which depend on any changed
# inputs, then send a SYNC.

try:
    for event in indev.read_loop():
        if event.type == EV_ABS:
            name = absname[event.code] 
            in_val[name] = event.value
            changeset.add(name)
        elif event.type == EV_KEY:
            name = keyname[event.code] 
            in_val[name] = event.value
            changeset.add(name)
        elif event.type == EV_SYN:
            monitorinvals();
            for o in outputs:
                if o.inset & changeset:
                    update_output(o)
            outdev.syn()
            changeset.clear()
            monitoroutvals()
            monitorcr()
            
except KeyboardInterrupt:
    print()
    print()
    

