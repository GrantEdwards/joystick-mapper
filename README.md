# joystick-mapper

Linux application to remap/modify Joystick channels/switches

## Background

This is a joystick "channel mapper" for linux.  It lets users create a
virtual "joystick" device that outputs modified values from another
joystick device.  The standard Linux joystick subsystem along with
utilities like 'jscal' and 'evdev-joystick' let you do a lot of the
usual things:

 * Calibrate axis endoints and center
 * Change order of axes or switches.
 * Set center deadzone
 * Set fuzz filtering
 * Apply segmented line xfer function

Most RC simulators have their own axis detection, calibration, trim,
expo, etc. So the usual practice is to disable all of the above and
have the Linux joystick subsystem send "raw" values to the simulator.

However, there are a few useful things that can't be done with the standard Linux joystick subsystem and utilities:

 * Create a new output axis from combination of input switches and or
   input axis values.
 * Send keyboard "commands" based on input switch positions or input
   axis values
 * Create a new switch that changes state based on input axis and/or
   switch values.
 * Hide an axis or switch.
 * Create a "dummy" output axis or switch with a fixed value.

### Example Use Case

The USB controller I use for RC simulators is the Futaba Interlink
Elite.  It has 6 "analog" axes (8-bit values 0-255) and 5
switches. The first 5 analog axes are what you would expect:

 * Ailerons
 * Elevator
 * Throttle
 * Rudder
 * Flaps/Gain knob

The final axis, however, is a bit odd.  The Interlink Elite has five
three-position momentary rocker switches (4 for trim, one for menu
up/down).  The combined states of those five switches are encoded into
an 8-bit value that is output as the 6th axis.  That value is a
five-trit ternary value from 00000₃ to 22222₃ (inclusive), where each
switch state is one trit value (0,1,2).  Needless to say, that's not
something that any simulator except for that one version of RF can
understand.  My mapper allows that axis value to be decoded and
presented to a simulator as 10 "normal" momentary switches or keyboard
command characters.

Simulators usually have an extensive set of keyboard commands, and you
can usually assign commands to switches.  What sometimes can't be done
is to assign a set of keyboard commands to various combinations of
switch values.

There are also simulators like SeligSim which have fixed expectations
for the input device which on Windows can be met with
vJoy/JSGremlin. SeligSim reportedly works well on Linux under Wine,
but the input device requirements can't be met with the standard Linux
joystick subsystem/utilities.

## Usage

The mapper is a command-line utility written in Python.  It supports a
number of command line options and reads most of the mapping
information from a configuration file.

Command line options can be shown using the --help option:

~~~
$ ./joystick-mapper.py --help

usage: ./joystick-mapper.py [-h] [-c CONFIG_FILE] [-D] [-i INPUT_NAME] [-I] [-o OUTPUT_NAME] [-O] [-m] [-M]

Joystick channel mapper

options:
  -h, --help            show this help message and exit
  -c CONFIG_FILE, --config-file CONFIG_FILE
  -D, --device-list
  -i INPUT_NAME, --input-name INPUT_NAME
  -I, --input-specs
  -o OUTPUT_NAME, --output-name OUTPUT_NAME
  -O, --output-specs
  -m, --monitor-inputs
  -M, --monitor-outputs
~~~

You would usually start out by showing a list of available input
devices using the -D option:

~~~
$ ./joystick-mapper.py -D
GREAT PLANES InterLink Elite
~~~
Then you can specify that as the input device with the '-i' option
(specify any string that is uniquely part of the device name shown
with -D) and show the input channels provided using the -I option:

~~~
$ ./joystick-mapper.py -i InterLink -I
using input device: GREAT PLANES InterLink Elite
Input Axes:
   a0: (0,ABS_X) value 127, min 0, max 255, fuzz 0, flat 0, res 0
   a1: (1,ABS_Y) value 128, min 0, max 255, fuzz 0, flat 0, res 0
   a2: (2,ABS_Z) value 210, min 0, max 255, fuzz 0, flat 0, res 0
   a3: (3,ABS_RX) value 66, min 0, max 255, fuzz 0, flat 0, res 0
   a4: (4,ABS_RY) value 130, min 0, max 255, fuzz 0, flat 0, res 0
   a5: (40,ABS_MISC) value 0, min 0, max 255, fuzz 0, flat 0, res 0
Input Switches:
   s0: (288,BTN_JOYSTICK)
   s1: (289,BTN_THUMB)
   s2: (290,BTN_THUMB2)
   s3: (291,BTN_TOP)
   s4: (292,BTN_TOP2)
~~~

Next you would create a config file (default $PWD/.joystick-mapperrc).  Here is
an example (somewhat complicated) config file:

~~~
# device names

input: GREAT PLANES InterLink Elite
output: My joystick-mapper device

# Reminder: output (LHS) namespace is distinct from input (RHS)
# namespace.

# analog "abs" axis outputs with min:max values in brackets.

a0 [0:255] = a2                    # rearrange first three channels
ABS_#13 [0:255] = a0
a2 [0:255] = a1
a3 [0:255] = 4*a3 - 256            # overrange values work fine
a4 [0:255] = 255-a4                # invert
a5 [0:255] = a5                    # no change

# triple-throw-center-off switch shows up as s3/s4.

# convert that into a 3-state (0/128/255) analog channel

a6 [0:255] = 128 + s4*127 - s3*128 

# and to three different keyboard keypresses (d,m,u)

P:KEY_D = s3
P:KEY_M = not (s3 or s4)
P:KEY_U = s4

# switch outputs

s0 = not s0
s1 = s1
s2 = a3 >= 200   

# switch 2 is red reset button, make it send a space 

P:KEY_SPACE = s2

# InterLink Elite maps 5 three-position rockers (trims and menu
# up/down) into a single "analog" axis value encoded as a 5-trit
# ternary number from 00000 to 22222.  So decode that 5 trit value
# into 10 different switch values:

s3 = (a5 % 3) == 1
s4 = (a5 % 3) == 2
s5 = ((a5//3) % 3) == 1
s6 = ((a5//3) % 3) == 2
s7  = ((a5//9) % 3) == 1
s8 = ((a5//9) % 3) == 2
s9 = ((a5//27) % 3) == 1
s10 = ((a5//27) % 3) == 2
s11 = ((a5//81) % 3) == 1
s12 = ((a5//81) % 3) == 2
~~~

To check the config file, you can ask to see the output configuration
with the -O option:

~~~
$ ./joystick-mapper.py -O

using input device: GREAT PLANES InterLink Elite
Output Axes:
 a0 (0,ABS_X) [0:255] = a2                    # rearrange first three channels
 ABS_#13 (13,?) [0:255] = a0
 a2 (1,ABS_Y) [0:255] = a1
 a3 (2,ABS_Z) [0:255] = 4*a3 - 256            # overrange values work fine
 a4 (3,ABS_RX) [0:255] = 255-a4                # invert
 a5 (4,ABS_RY) [0:255] = a5                    # no change
 a6 (5,ABS_RZ) [0:255] = 128 + s4*127 - s3*128
Output Switches:
 s0 (256,BTN_0) = not s0
 s1 (257,BTN_1) = s1
 s3 (258,BTN_2) = a3 >= 200
 s4 (259,BTN_3) = (a5 % 3) == 1
 s5 (260,BTN_4) = (a5 % 3) == 2
 s6 (261,BTN_5) = ((a5//3) % 3) == 1
 s7 (262,BTN_6) = ((a5//3) % 3) == 2
 s8 (263,BTN_7) = ((a5//9) % 3) == 1
 s9 (264,BTN_8) = ((a5//9) % 3) == 2
 s10 (265,BTN_9) = ((a5//27) % 3) == 1
 s11 (266,?) = ((a5//27) % 3) == 2
 s12 (267,?) = ((a5//81) % 3) == 1
 s13 (268,?) = ((a5//81) % 3) == 2
Output Pulses:
 KEY_D (32,KEY_D) = s3
 KEY_M (50,KEY_M) = not (s3 or s4)
 KEY_U (22,KEY_U) = s4

~~~

## Config File Syntax

The config file can contain 5 different types of lines:

 *  Empty or only whitespace
 *  Comment (first non-whitespace character is '#')
 *  Input device name
 *  Output device name
 *  Output signal definition

The first two are self explanitory. The others are explained below.

### Input/Output Device Names

An input device name line starts with the string 'input:' or
'output:'. The remainder of the line after the colon will have
leading/trialing whitespace removed and will then be used as the
input/output device name strings.  The first device found whose name
contains the 'input' name string will be used as the input device.

The output device will be created with the name specified on the
output: line.

### Output Signal Definitions

An output signal definition looks vaguely like a Python assignment
statement.  There's a left-hand-side (LHS) a single '=' and a
right-hand-side (RHS).

The RHS must be a legal Python expression. The namespace in which
those expressions are evaluated is limited to the signal names shown
using the '-I' option along with the Python builtin 'int'.  More
builtins or custom function names may be added in the future.

The RHS and LHS namespaces are distinct and separate.  You can not use
an output defined on one line as an input for another line.

The LHS defines one of three types of output signals:

 * Absolute Axis Outputs are normal analog joystick "channels" that
   will be set to the value determined by the RHS expression (which
   must evaluate to an integer or boolean).

 * Switch Outputs are binary outputs that will be set to the value
   determined by the RHS expression (which should evaluate to a
   boolean or an integer 0/1 value).

 * Pulse Outputs are binary outputs that will briefly pulse high each
   time the RHS value changes from 0/false to non-zero/true. Pulse
   outputs are useful for sending keyboard keypress commands.

#### Absolute Axis Output

    <name> [<min>:<max>] = <RHS>

This is a normal joystick "channel" which will be created with the
min/max values contained in square brackets.  Those min/max values are
advisory only. They are reported to the end application (the sim), but
neither this channel mapper nor the Linux joystick subsystem will
limit the actual output value.  [It's entirely possible the sim will
ignore them too.]

The output name is for internal use only, and may take one of three
forms:

**`ABS_#nn`**  Will create an absolute output with index <nn> (base 10).

**`ABS_<other>`** Will create an absolute output with index found by
searching the standard set of axis names. If the name does not match,
it is an error.

**`<other>`** Will create an absolute output with an index
auto-allocated started with index 1 (AKA "ABS_X"). Subsequent
auto-allocated indexes will each increase by 1 each time.

There is currently no check to see if auto-allocated output indexes
conflict with those manually chosen by using ABS_ names.

#### Switch Output

    <name> = <RHS>

Similar to an absolute axis a switch output name may take multiple forms:

**`KEY_#nn`** or **`BTN_#nn`** Will create a boolean button/key output
with index <nn> (base 10).

**`KEY_<other>`** or **`BTN_<other>`** Will create a boolean
button/key output with an index found by searching the standard set of
button/key names. There is no semantic difference between KEY and BTN.

**`<other>`** Will create a boolean button/key output with an index
auto-allocated starting with 256 (AKA "BTN_0"). Subsequently 
auto-allocated button/key indexes will increase by 1 each time.

There is currently no check to see if auto-allocated output indexes
conflict with those manually chosen by using BTN_ or KEY_ names.

#### Pulse Output

    P:<name> = <RHS>

The syntax and semantics for `<name>` are the same as for Switch
Outputs.  The only difference is the behavior of the output as a
function of the RHS.

## Implementation

The heavy lifting is handled by the Python [evdev
library](https://python-evdev.readthedocs.io/) which is used to both
read from the input device and to create and write to the output
device.  The channel mapper comprises about 200 lines of Python
(including debug and monitoring code).

## Todo

 * When synthesizing switch states or keyboard commands based on
   analog axis thresholds (e.g.  s4 = a3 > 200) you really need to
   have some user-specified hysteresis to prevent "chatter" or
   "bounce".

