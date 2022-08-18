# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Base interface definitions and infrastructure."""

import os
import logging

import simplejson as json
from traits.trait_errors import TraitError

from ifsnipype.base.traits_extension import isdefined, Undefined
from ifsnipype.base.specs import BaseInterfaceInputSpec as _BaseInterfaceInputSpec
from ifsnipype.base.support import (
    RuntimeContext,
    InterfaceResult,
)

_iflogger = logging.getLogger("nipype.interface")


class _Interface:
    """
    Defines an abstract API for all interfaces.

    The I/O specifications corresponding to these base
    interfaces are found in the :py:mod:`~ifsnipype.base.specs`.

    """

    _input_spec = None
    """
    The specification of the input, defined by a :py:class:`~traits.has_traits.HasTraits` class.
    """
    _output_spec = None
    """
    The specification of the output, defined by a :py:class:`~traits.has_traits.HasTraits` class.
    """

    @classmethod
    def help(cls, returnhelp=False):
        """Prints class help"""
        from ifsnipype.base.support import format_help

        allhelp = format_help(cls)
        if returnhelp:
            return allhelp
        print(allhelp)
        return None  # R1710

    def run(self):
        """Execute the command."""
        raise NotImplementedError


class BaseInterface(_Interface):
    """Implement common interface functionality.

    * Initializes inputs/outputs from input_spec/output_spec
    * Provides help based on input_spec and output_spec
    * Checks for mandatory inputs before running an interface
    * Runs an interface and returns results
    * Determines which inputs should be copied or linked to cwd

    This class does not implement aggregate_outputs, input_spec or
    output_spec. These should be defined by derived classes.

    This class cannot be instantiated.

    Attributes
    ----------
    input_spec: :obj:`nipype.interfaces.base.specs.TraitedSpec`
        points to the traited class for the inputs
    output_spec: :obj:`nipype.interfaces.base.specs.TraitedSpec`
        points to the traited class for the outputs
    _redirect_x: bool
        should be set to ``True`` when the interface requires
        connecting to a ``$DISPLAY`` (default is ``False``).

    """

    input_spec = _BaseInterfaceInputSpec
    _version = None
    _additional_metadata = []
    _redirect_x = False
    _references = []

    def __init__(self, **inputs):
        if not self.input_spec:
            raise Exception("No input_spec in class: %s" % self.__class__.__name__)

        # Create input spec, disable any defaults that are unavailable due to
        # version, and then apply the inputs that were passed.
        self.inputs = self.input_spec()

        # TODO: Consider version checking
        # unavailable_traits = self._check_version_requirements(
        #     self.inputs, permissive=True
        # )
        # if unavailable_traits:
        #     self.inputs.trait_set(**{k: Undefined for k in unavailable_traits})
        self.inputs.trait_set(**inputs)


    def _outputs(self):
        """Returns a bunch containing output fields for the class"""
        outputs = None
        if self.output_spec:
            outputs = self.output_spec()

        return outputs

    def _run_interface(self, runtime):
        """Core function that executes interface"""
        raise NotImplementedError

    # TODO: Consider duecredit dependency
    # def _duecredit_cite(self):
    #     """Add the interface references to the duecredit citations"""
    #     for r in self._references:
    #         r["path"] = self.__module__
    #         due.cite(**r)

    def run(self, cwd=None, ignore_exception=None, **inputs):
        """Execute this interface.

        This interface will not raise an exception if runtime.returncode is
        non-zero.

        Parameters
        ----------
        cwd : specify a folder where the interface should be run
        inputs : allows the interface settings to be updated

        Returns
        -------
        results :  :obj:`nipype.interfaces.base.support.InterfaceResult`
            A copy of the instance that was executed, provenance information and,
            if successful, results

        """
        # TODO: Remove nipype dependency on indirectory
        from nipype.utils.filemanip import indirectory
        rtc = RuntimeContext(ignore_exception=bool(ignore_exception))

        with indirectory(cwd or os.getcwd()):
            self.inputs.trait_set(**inputs)
        # TODO: enable check
        # self._check_mandatory_inputs()

        # TODO: Version checking?
        # self._check_version_requirements(self.inputs)

        with rtc(self, cwd=cwd, redirect_x=self._redirect_x) as runtime:

            # Grab inputs now, as they should not change during execution
            inputs = self.inputs.get_traitsfree()
            outputs = None
            # Run interface
            runtime = self._pre_run_hook(runtime)
            runtime = self._run_interface(runtime)
            runtime = self._post_run_hook(runtime)
            # Collect outputs
            outputs = self.aggregate_outputs(runtime)

        results = InterfaceResult(
            self.__class__,
            rtc.runtime,
            inputs=inputs,
            outputs=outputs,
            provenance=None,
        )

        # TODO: Add provenance (if required)
        # if str2bool(config.get("execution", "write_provenance", "false")):
        #     # Provenance will only throw a warning if something went wrong
        #     results.provenance = write_provenance(results)

        # self._duecredit_cite()

        return results

    def _list_outputs(self):
        """List the expected outputs"""
        if self.output_spec:
            raise NotImplementedError
        else:
            return None

    def aggregate_outputs(self, runtime=None, needed_outputs=None):
        """Collate expected outputs and apply output traits validation."""
        outputs = self._outputs()  # Generate an empty output spec object
        predicted_outputs = self._list_outputs()  # Predictions from _list_outputs
        if not predicted_outputs:
            return outputs

        # Precalculate the list of output trait names that should be aggregated
        aggregate_names = set(predicted_outputs)
        if needed_outputs is not None:
            aggregate_names = set(needed_outputs).intersection(aggregate_names)

        if aggregate_names:  # Make sure outputs are compatible
            _na_outputs = self._check_version_requirements(outputs)
            na_names = aggregate_names.intersection(_na_outputs)
            if na_names:
                # XXX Change to TypeError in Nipype 2.0
                raise KeyError(
                    """\
Output trait(s) %s not available in version %s of interface %s.\
"""
                    % (", ".join(na_names), self.version, self.__class__.__name__)
                )

        for key in aggregate_names:  # Final aggregation
            val = predicted_outputs[key]
            try:
                setattr(outputs, key, val)
            except TraitError as error:
                if "an existing" in getattr(error, "info", "default"):
                    msg = (
                        "No such file or directory '%s' for output '%s' of a %s interface"
                        % (val, key, self.__class__.__name__)
                    )
                    raise FileNotFoundError(msg)
                raise error
        return outputs

    # @property
    # def version(self):
    #     return self._version

    def _pre_run_hook(self, runtime):
        """
        Perform any pre-_run_interface() processing

        Subclasses may override this function to modify ``runtime`` object or
        interface state

        MUST return runtime object
        """
        return runtime

    def _post_run_hook(self, runtime):
        """
        Perform any post-_run_interface() processing

        Subclasses may override this function to modify ``runtime`` object or
        interface state

        MUST return runtime object
        """
        return runtime


class SimpleInterface(BaseInterface):
    """An interface pattern that allows outputs to be set in a dictionary
    called ``_results`` that is automatically interpreted by
    ``_list_outputs()`` to find the outputs.

    When implementing ``_run_interface``, set outputs with::

        self._results[out_name] = out_value

    This can be a way to upgrade a ``Function`` interface to do type checking.

    Examples
    --------
    >>> from nipype.interfaces.base import (
    ...     SimpleInterface, BaseInterfaceInputSpec, TraitedSpec)

    >>> def double(x):
    ...    return 2 * x
    ...
    >>> class DoubleInputSpec(BaseInterfaceInputSpec):
    ...     x = traits.Float(mandatory=True)
    ...
    >>> class DoubleOutputSpec(TraitedSpec):
    ...     doubled = traits.Float()
    ...
    >>> class Double(SimpleInterface):
    ...     input_spec = DoubleInputSpec
    ...     output_spec = DoubleOutputSpec
    ...
    ...     def _run_interface(self, runtime):
    ...          self._results['doubled'] = double(self.inputs.x)
    ...          return runtime

    >>> dbl = Double()
    >>> dbl.inputs.x = 2
    >>> dbl.run().outputs.doubled
    4.0

    """

    def __init__(self, **inputs):
        super().__init__(**inputs)
        self._results = {}

    def _list_outputs(self):
        return self._results
