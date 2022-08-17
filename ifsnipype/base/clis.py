# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
#
# Copyright 2022 The Nipy Developers <neuroimaging@python.org>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# STATEMENT OF CHANGES: This file is derived from sources licensed under the Apache-2.0 terms,
# and this file has been changed.
# The original file this work derives from is found at:
# https://github.com/nipy/nipype/blob/1dee93965dfb6b0d0e50a6abd7ac89bf13dfbf8c/nipype/interfaces/base/core.py
#
"""Command Line Interfaces (CLIs)."""
import os
import logging
import subprocess as sp
import shlex

from nipype.utils.filemanip import (
    canonicalize_env,
    get_dependencies,
    split_filename,
    which,
)
from nipype.utils.subprocess import run_command


from ifsnipype.base.traits_extension import traits, isdefined
from ifsnipype.base.core import BaseInterface
from ifsnipype.base.specs import (
    CommandLineInputSpec,
    StdOutCommandLineInputSpec,
    MpiCommandLineInputSpec,
)

from ifsnipype.support import NipypeInterfaceError

iflogger = logging.getLogger("nipype.interface")

VALID_TERMINAL_OUTPUT = [
    "stream",
    "allatonce",
    "file",
    "file_split",
    "file_stdout",
    "file_stderr",
    "none",
]


class CommandLine(BaseInterface):
    """Implements functionality to interact with command line programs
    class must be instantiated with a command argument

    Parameters
    ----------
    command : str
        define base immutable `command` you wish to run
    args : str, optional
        optional arguments passed to base `command`

    Examples
    --------
    >>> import pprint
    >>> from nipype.interfaces.base import CommandLine
    >>> cli = CommandLine(command='ls', environ={'DISPLAY': ':1'})
    >>> cli.inputs.args = '-al'
    >>> cli.cmdline
    'ls -al'

    >>> # Use get_traitsfree() to check all inputs set
    >>> pprint.pprint(cli.inputs.get_traitsfree())  # doctest:
    {'args': '-al',
     'environ': {'DISPLAY': ':1'}}

    >>> cli.inputs.get_hashval()[0][0]
    ('args', '-al')
    >>> cli.inputs.get_hashval()[1]
    '11c37f97649cd61627f4afe5136af8c0'

    """

    input_spec = CommandLineInputSpec
    _cmd_prefix = ""
    _cmd = None
    _version = None
    _terminal_output = "stream"
    _write_cmdline = False

    @classmethod
    def set_default_terminal_output(cls, output_type):
        """Set the default terminal output for CommandLine Interfaces.

        This method is used to set default terminal output for
        CommandLine Interfaces.  However, setting this will not
        update the output type for any existing instances.  For these,
        assign the <instance>.terminal_output.
        """

        if output_type in VALID_TERMINAL_OUTPUT:
            cls._terminal_output = output_type
        else:
            raise AttributeError("Invalid terminal output_type: %s" % output_type)

    def __init__(
        self, command=None, terminal_output=None, write_cmdline=False, **inputs
    ):
        super(CommandLine, self).__init__(**inputs)
        self._environ = None
        # Set command. Input argument takes precedence
        self._cmd = command or getattr(self, "_cmd", None)

        # TODO Store dependencies in runtime object
        # self._ldd = str2bool(config.get("execution", "get_linked_libs", "true"))
        self._ldd = False

        if self._cmd is None:
            raise Exception("Missing command")

        if terminal_output is not None:
            self.terminal_output = terminal_output

        self._write_cmdline = write_cmdline

    @property
    def cmd(self):
        """sets base command, immutable"""
        if not self._cmd:
            raise NotImplementedError(
                "CommandLineInterface should wrap an executable, but "
                "none has been set."
            )
        return self._cmd

    @property
    def cmdline(self):
        """`command` plus any arguments (args)
        validates arguments and generates command line"""
        self._check_mandatory_inputs()
        allargs = [self._cmd_prefix + self.cmd] + self._parse_inputs()
        return " ".join(allargs)

    @property
    def terminal_output(self):
        return self._terminal_output

    @terminal_output.setter
    def terminal_output(self, value):
        if value not in VALID_TERMINAL_OUTPUT:
            raise RuntimeError(
                'Setting invalid value "%s" for terminal_output. Valid values are '
                "%s." % (value, ", ".join(['"%s"' % v for v in VALID_TERMINAL_OUTPUT]))
            )
        self._terminal_output = value

    @property
    def write_cmdline(self):
        return self._write_cmdline

    @write_cmdline.setter
    def write_cmdline(self, value):
        self._write_cmdline = value is True

    def raise_exception(self, runtime):
        raise RuntimeError(
            (
                "Command:\n{cmdline}\nStandard output:\n{stdout}\n"
                "Standard error:\n{stderr}\nReturn code: {returncode}"
            ).format(**runtime.dictcopy())
        )

    def _get_environ(self):
        return getattr(self.inputs, "environ", {})

    def version_from_command(self, flag="-v", cmd=None):
        iflogger.warning(
            "version_from_command member of CommandLine was "
            "Deprecated in nipype-1.0.0 and deleted in 1.1.0"
        )
        if cmd is None:
            cmd = self.cmd.split()[0]

        env = dict(os.environ)
        if which(cmd, env=env):
            out_environ = self._get_environ()
            env.update(out_environ)
            proc = sp.Popen(
                " ".join((cmd, flag)),
                shell=True,
                env=canonicalize_env(env),
                stdout=sp.PIPE,
                stderr=sp.PIPE,
            )
            o, e = proc.communicate()
            return o

    def _run_interface(self, runtime, correct_return_codes=(0,)):
        """Execute command via subprocess

        Parameters
        ----------
        runtime : passed by the run function

        Returns
        -------
        runtime :
            updated runtime information
            adds stdout, stderr, merged, cmdline, dependencies, command_path

        """
        out_environ = self._get_environ()
        # Initialize runtime Bunch

        try:
            runtime.cmdline = self.cmdline
        except Exception as exc:
            raise RuntimeError(
                "Error raised when interpolating the command line"
            ) from exc

        runtime.stdout = None
        runtime.stderr = None
        runtime.cmdline = self.cmdline
        runtime.environ.update(out_environ)
        runtime.success_codes = correct_return_codes

        # which $cmd
        executable_name = shlex.split(self._cmd_prefix + self.cmd)[0]
        cmd_path = which(executable_name, env=runtime.environ)

        if cmd_path is None:
            raise IOError(
                'No command "%s" found on host %s. Please check that the '
                "corresponding package is installed."
                % (executable_name, runtime.hostname)
            )

        runtime.command_path = cmd_path
        runtime.dependencies = (
            get_dependencies(executable_name, runtime.environ)
            if self._ldd
            else "<skipped>"
        )
        runtime = run_command(
            runtime,
            output=self.terminal_output,
            write_cmdline=self.write_cmdline,
        )
        return runtime

    def _format_arg(self, name, trait_spec, value):
        """A helper function for _parse_inputs

        Formats a trait containing argstr metadata
        """
        argstr = trait_spec.argstr
        iflogger.debug("%s_%s", name, value)
        if trait_spec.is_trait_type(traits.Bool) and "%" not in argstr:
            # Boolean options have no format string. Just append options if True.
            return argstr if value else None
        # traits.Either turns into traits.TraitCompound and does not have any
        # inner_traits
        elif trait_spec.is_trait_type(traits.List) or (
            trait_spec.is_trait_type(traits.TraitCompound) and isinstance(value, list)
        ):
            # This is a bit simple-minded at present, and should be
            # construed as the default. If more sophisticated behavior
            # is needed, it can be accomplished with metadata (e.g.
            # format string for list member str'ification, specifying
            # the separator, etc.)

            # Depending on whether we stick with traitlets, and whether or
            # not we beef up traitlets.List, we may want to put some
            # type-checking code here as well
            sep = trait_spec.sep if trait_spec.sep is not None else " "

            if argstr.endswith("..."):
                # repeatable option
                # --id %d... will expand to
                # --id 1 --id 2 --id 3 etc.,.
                argstr = argstr.replace("...", "")
                return sep.join([argstr % elt for elt in value])
            else:
                return argstr % sep.join(str(elt) for elt in value)
        else:
            # Append options using format string.
            return argstr % value

    def _filename_from_source(self, name, chain=None):
        if chain is None:
            chain = []

        trait_spec = self.inputs.trait(name)
        retval = getattr(self.inputs, name)
        source_ext = None
        if not isdefined(retval) or "%s" in retval:
            if not trait_spec.name_source:
                return retval

            # Do not generate filename when excluded by other inputs
            if any(
                isdefined(getattr(self.inputs, field)) for field in trait_spec.xor or ()
            ):
                return retval

            # Do not generate filename when required fields are missing
            if not all(
                isdefined(getattr(self.inputs, field))
                for field in trait_spec.requires or ()
            ):
                return retval

            if isdefined(retval) and "%s" in retval:
                name_template = retval
            else:
                name_template = trait_spec.name_template
            if not name_template:
                name_template = "%s_generated"

            ns = trait_spec.name_source
            while isinstance(ns, (list, tuple)):
                if len(ns) > 1:
                    iflogger.warning("Only one name_source per trait is allowed")
                ns = ns[0]

            if not isinstance(ns, (str, bytes)):
                raise ValueError(
                    "name_source of '{}' trait should be an input trait "
                    "name, but a type {} object was found".format(name, type(ns))
                )

            if isdefined(getattr(self.inputs, ns)):
                name_source = ns
                source = getattr(self.inputs, name_source)
                while isinstance(source, list):
                    source = source[0]

                # special treatment for files
                try:
                    _, base, source_ext = split_filename(source)
                except (AttributeError, TypeError):
                    base = source
            else:
                if name in chain:
                    raise NipypeInterfaceError("Mutually pointing name_sources")

                chain.append(name)
                base = self._filename_from_source(ns, chain)
                if isdefined(base):
                    _, _, source_ext = split_filename(base)
                else:
                    # Do not generate filename when required fields are missing
                    return retval

            chain = None
            retval = name_template % base
            _, _, ext = split_filename(retval)
            if trait_spec.keep_extension and (ext or source_ext):
                if (ext is None or not ext) and source_ext:
                    retval = retval + source_ext
            else:
                retval = self._overload_extension(retval, name)
        return retval

    def _gen_filename(self, name):
        raise NotImplementedError

    def _overload_extension(self, value, name=None):
        return value

    def _list_outputs(self):
        metadata = dict(name_source=lambda t: t is not None)
        traits = self.inputs.traits(**metadata)
        if traits:
            outputs = self.output_spec().trait_get()
            for name, trait_spec in list(traits.items()):
                out_name = name
                if trait_spec.output_name is not None:
                    out_name = trait_spec.output_name
                fname = self._filename_from_source(name)
                if isdefined(fname):
                    outputs[out_name] = os.path.abspath(fname)
            return outputs

    def _parse_inputs(self, skip=None):
        """Parse all inputs using the ``argstr`` format string in the Trait.

        Any inputs that are assigned (not the default_value) are formatted
        to be added to the command line.

        Returns
        -------
        all_args : list
            A list of all inputs formatted for the command line.

        """
        all_args = []
        initial_args = {}
        final_args = {}
        metadata = dict(argstr=lambda t: t is not None)
        for name, spec in sorted(self.inputs.traits(**metadata).items()):
            if skip and name in skip:
                continue
            value = getattr(self.inputs, name)
            if spec.name_source:
                value = self._filename_from_source(name)
            elif spec.genfile:
                if not isdefined(value) or value is None:
                    value = self._gen_filename(name)

            if not isdefined(value):
                continue

            try:
                arg = self._format_arg(name, spec, value)
            except Exception as exc:
                raise ValueError(
                    f"Error formatting command line argument '{name}' with value '{value}'"
                ) from exc

            if arg is None:
                continue
            pos = spec.position
            if pos is not None:
                if int(pos) >= 0:
                    initial_args[pos] = arg
                else:
                    final_args[pos] = arg
            else:
                all_args.append(arg)
        first_args = [el for _, el in sorted(initial_args.items())]
        last_args = [el for _, el in sorted(final_args.items())]
        return first_args + all_args + last_args


class StdOutCommandLine(CommandLine):
    input_spec = StdOutCommandLineInputSpec

    def _gen_filename(self, name):
        return self._gen_outfilename() if name == "out_file" else None

    def _gen_outfilename(self):
        raise NotImplementedError


class MpiCommandLine(CommandLine):
    """Implements functionality to interact with command line programs
    that can be run with MPI (i.e. using 'mpiexec').

    Examples
    --------
    >>> from nipype.interfaces.base import MpiCommandLine
    >>> mpi_cli = MpiCommandLine(command='my_mpi_prog')
    >>> mpi_cli.inputs.args = '-v'
    >>> mpi_cli.cmdline
    'my_mpi_prog -v'

    >>> mpi_cli.inputs.use_mpi = True
    >>> mpi_cli.inputs.n_procs = 8
    >>> mpi_cli.cmdline
    'mpiexec -n 8 my_mpi_prog -v'

    """

    input_spec = MpiCommandLineInputSpec

    @property
    def cmdline(self):
        """Adds 'mpiexec' to begining of command"""
        result = []
        if self.inputs.use_mpi:
            result.append("mpiexec")
            if self.inputs.n_procs:
                result.append("-n %d" % self.inputs.n_procs)
        result.append(super(MpiCommandLine, self).cmdline)
        return " ".join(result)


class SEMLikeCommandLine(CommandLine):
    """In SEM derived interface all outputs have corresponding inputs.
    However, some SEM commands create outputs that are not defined in the XML.
    In those cases one has to create a subclass of the autogenerated one and
    overload the _list_outputs method. _outputs_from_inputs should still be
    used but only for the reduced (by excluding those that do not have
    corresponding inputs list of outputs.
    """

    def _list_outputs(self):
        outputs = self.output_spec().trait_get()
        return self._outputs_from_inputs(outputs)

    def _outputs_from_inputs(self, outputs):
        for name in list(outputs.keys()):
            corresponding_input = getattr(self.inputs, name)
            if isdefined(corresponding_input):
                if isinstance(corresponding_input, bool) and corresponding_input:
                    outputs[name] = os.path.abspath(self._outputs_filenames[name])
                else:
                    if isinstance(corresponding_input, list):
                        outputs[name] = [
                            os.path.abspath(inp) for inp in corresponding_input
                        ]
                    else:
                        outputs[name] = os.path.abspath(corresponding_input)
        return outputs

    def _format_arg(self, name, spec, value):
        if name in list(self._outputs_filenames.keys()):
            if isinstance(value, bool):
                if value:
                    value = os.path.abspath(self._outputs_filenames[name])
                else:
                    return ""
        return super(SEMLikeCommandLine, self)._format_arg(name, spec, value)


class PackageInfo:
    _version = None
    version_cmd = None
    version_file = None

    @classmethod
    def version(klass):
        if klass._version is None:
            if klass.version_cmd is not None:
                try:
                    clout = CommandLine(
                        command=klass.version_cmd,
                        resource_monitor=False,
                        terminal_output="allatonce",
                    ).run()
                except IOError:
                    return None

                raw_info = clout.runtime.stdout
            elif klass.version_file is not None:
                try:
                    with open(klass.version_file, "rt") as fobj:
                        raw_info = fobj.read()
                except OSError:
                    return None
            else:
                return None

            klass._version = klass.parse_version(raw_info)

        return klass._version

    @staticmethod
    def parse_version(raw_info):
        raise NotImplementedError
