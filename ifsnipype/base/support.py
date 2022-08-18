# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""

Miscellaneous tools to support Interface functionality
......................................................

"""
import os
import typing
import logging
from dataclasses import dataclass
from contextlib import AbstractContextManager
from copy import deepcopy
from textwrap import wrap
import re
from datetime import datetime as dt
from dateutil.parser import parse as parseutc
import platform


_iflogger = logging.getLogger("nipype.interface")

HELP_LINEWIDTH = 89


@dataclass
class Runtime:
    """Store the result of executing a particular Interface."""
    cwd: typing.Union[str, bytes, os.PathLike]
    environ: dict
    hostname: str
    interface: str
    platform: str
    prevcwd: typing.Union[str, bytes, os.PathLike]
    cmdline: str = None
    duration: float = None
    startTime: int = None
    endTime: int = None
    returncode: int = None
    stdout: str = None
    stderr: str = None
    success_codes: typing.Tuple[int] = (0, )
    command_path: str = None
    dependencies: str = "<skipped>"



class RuntimeContext(AbstractContextManager):
    """A context manager to run NiPype interfaces."""

    __slots__ = ("_runtime", "_ignore_exc")

    def __init__(self, ignore_exception=False):
        """Initialize the context manager object."""
        self._ignore_exc = ignore_exception

    def __call__(self, interface, cwd=None, redirect_x=False):
        """Generate a new runtime object."""
        from nipype.utils.misc import rgetcwd

        # Tear-up: get current and prev directories
        _syscwd = rgetcwd(error=False)  # Recover when wd does not exist
        if cwd is None:
            cwd = _syscwd

        self._runtime = Runtime(
            cwd=str(cwd),
            environ=deepcopy(dict(os.environ)),
            hostname=platform.node(),
            interface=interface.__class__.__name__,
            platform=platform.platform(),
            prevcwd=str(_syscwd),
        )
        return self

    def __enter__(self):
        """Tear-up the execution of an interface."""
        # TODO
        # if self._runtime.redirect_x:
        #     self._runtime.environ["DISPLAY"] = config.get_display()

        self._runtime.startTime = dt.isoformat(dt.utcnow())
        # TODO: Perhaps clean-up path and ensure it exists?
        os.chdir(self._runtime.cwd)
        return self._runtime

    def __exit__(self, exc_type, exc_value, exc_tb):
        """Tear-down interface execution."""
        self._runtime.endTime = dt.isoformat(dt.utcnow())
        timediff = parseutc(self._runtime.endTime) - parseutc(self._runtime.startTime)
        self._runtime.duration = (
            timediff.days * 86400 + timediff.seconds + timediff.microseconds / 1e6
        )

        os.chdir(self._runtime.prevcwd)

        if exc_type is not None or exc_value is not None or exc_tb is not None:
            import traceback

            # Retrieve the maximum info fast
            self._runtime.traceback = "".join(
                traceback.format_exception(exc_type, exc_value, exc_tb)
            )
            # Gather up the exception arguments and append nipype info.
            exc_args = exc_value.args if getattr(exc_value, "args") else tuple()
            exc_args += (
                f"An exception of type {exc_type.__name__} occurred while "
                f"running interface {self._runtime.interface}.",
            )
            self._runtime.traceback_args = ("\n".join([f"{arg}" for arg in exc_args]),)

            if self._ignore_exc:
                return True

        if hasattr(self._runtime, "cmdline"):
            retcode = self._runtime.returncode
            if retcode not in self._runtime.success_codes:
                self._runtime.traceback = (
                    f"RuntimeError: subprocess exited with code {retcode}."
                )

    @property
    def runtime(self):
        return self._runtime


class NipypeInterfaceError(Exception):
    """Custom error for interfaces"""

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return "{}".format(self.value)


def format_help(cls):
    """
    Prints help text of a Nipype interface

    >>> from nipype.interfaces.afni import GCOR
    >>> GCOR.help()  # doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
    Wraps the executable command ``@compute_gcor``.
    <BLANKLINE>
    Computes the average correlation between every voxel
    and ever other voxel, over any give mask.
    <BLANKLINE>
    <BLANKLINE>
    For complete details, ...

    """
    from ...utils.misc import trim

    docstring = []
    cmd = getattr(cls, "_cmd", None)
    if cmd:
        docstring += ["Wraps the executable command ``%s``." % cmd, ""]

    if cls.__doc__:
        docstring += trim(cls.__doc__).split("\n") + [""]

    allhelp = "\n".join(
        docstring
        + _inputs_help(cls)
        + [""]
        + _outputs_help(cls)
        + [""]
        + _refs_help(cls)
    )
    return allhelp.expandtabs(8)


def _inputs_help(cls):
    r"""
    Prints description for input parameters

    >>> from nipype.interfaces.afni import GCOR
    >>> _inputs_help(GCOR)  # doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
    ['Inputs::', '', '\t[Mandatory]', '\tin_file: (a pathlike object or string...

    """
    helpstr = ["Inputs::"]
    mandatory_keys = []
    optional_items = []

    if cls.input_spec:
        inputs = cls.input_spec()
        mandatory_items = list(inputs.traits(mandatory=True).items())
        if mandatory_items:
            helpstr += ["", "\t[Mandatory]"]
            for name, spec in mandatory_items:
                helpstr += get_trait_desc(inputs, name, spec)

        mandatory_keys = {item[0] for item in mandatory_items}
        optional_items = [
            "\n".join(get_trait_desc(inputs, name, val))
            for name, val in inputs.traits(transient=None).items()
            if name not in mandatory_keys
        ]
        if optional_items:
            helpstr += ["", "\t[Optional]"] + optional_items

    if not mandatory_keys and not optional_items:
        helpstr += ["", "\tNone"]
    return helpstr


def _outputs_help(cls):
    r"""
    Prints description for output parameters

    >>> from nipype.interfaces.afni import GCOR
    >>> _outputs_help(GCOR)  # doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
    ['Outputs::', '', '\tout: (a float)\n\t\tglobal correlation value']

    """
    helpstr = ["Outputs::", "", "\tNone"]
    if cls.output_spec:
        outputs = cls.output_spec()
        outhelpstr = [
            "\n".join(get_trait_desc(outputs, name, spec))
            for name, spec in outputs.traits(transient=None).items()
        ]
        if outhelpstr:
            helpstr = helpstr[:-1] + outhelpstr
    return helpstr


def _refs_help(cls):
    """Prints interface references."""
    references = getattr(cls, "_references", None)
    if not references:
        return []

    helpstr = ["References:", "-----------"]
    for r in references:
        helpstr += ["{}".format(r["entry"])]

    return helpstr


def get_trait_desc(inputs, name, spec):
    """Parses a HasTraits object into a nipype documentation string"""
    desc = spec.desc
    xor = spec.xor
    requires = spec.requires
    argstr = spec.argstr

    manhelpstr = ["\t%s" % name]

    type_info = spec.full_info(inputs, name, None)

    default = ""
    if spec.usedefault:
        default = ", nipype default value: %s" % str(spec.default_value()[1])
    line = "(%s%s)" % (type_info, default)

    manhelpstr = wrap(
        line,
        HELP_LINEWIDTH,
        initial_indent=manhelpstr[0] + ": ",
        subsequent_indent="\t\t  ",
    )

    if desc:
        for line in desc.split("\n"):
            line = re.sub(r"\s+", " ", line)
            manhelpstr += wrap(
                line, HELP_LINEWIDTH, initial_indent="\t\t", subsequent_indent="\t\t"
            )

    if argstr:
        pos = spec.position
        if pos is not None:
            manhelpstr += wrap(
                "argument: ``%s``, position: %s" % (argstr, pos),
                HELP_LINEWIDTH,
                initial_indent="\t\t",
                subsequent_indent="\t\t",
            )
        else:
            manhelpstr += wrap(
                "argument: ``%s``" % argstr,
                HELP_LINEWIDTH,
                initial_indent="\t\t",
                subsequent_indent="\t\t",
            )

    if xor:
        line = "%s" % ", ".join(xor)
        manhelpstr += wrap(
            line,
            HELP_LINEWIDTH,
            initial_indent="\t\tmutually_exclusive: ",
            subsequent_indent="\t\t  ",
        )

    if requires:
        others = [field for field in requires if field != name]
        line = "%s" % ", ".join(others)
        manhelpstr += wrap(
            line,
            HELP_LINEWIDTH,
            initial_indent="\t\trequires: ",
            subsequent_indent="\t\t  ",
        )
    return manhelpstr
