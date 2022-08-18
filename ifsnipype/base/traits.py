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
"""A lightweight alternative to enthought traits with dataclasses."""
from copy import deepcopy


class Bunch:
    """
    Dictionary-like class that provides attribute-style access to its items.

    A ``Bunch`` is a simple container that stores its items as class
    attributes [1]_. Internally all items are stored in a dictionary and
    the class exposes several of the dictionary methods.

    Examples
    --------
    >>> from nipype.interfaces.base import Bunch
    >>> inputs = Bunch(infile='subj.nii', fwhm=6.0, register_to_mean=True)
    >>> inputs
    Bunch(fwhm=6.0, infile='subj.nii', register_to_mean=True)
    >>> inputs.register_to_mean = False
    >>> inputs
    Bunch(fwhm=6.0, infile='subj.nii', register_to_mean=False)

    References
    ----------
    .. [1] A. Martelli, D. Hudgeon, "Collecting a Bunch of Named
           Items", Python Cookbook, 2nd Ed, Chapter 4.18, 2005.

    """

    def __init__(self, default_value=None, **kwargs):
        self.__dict__.update(**kwargs)
        self.__dict__["value"] = default_value

    def metadata(self):
        """iterates over bunch attributes as key, value pairs"""
        return {
            metakey: metaval
            for metakey, metaval in self.__dict__.items()
            if metakey != "value"
        }

    def get(self, *args):
        """Support dictionary get() functionality"""
        return self.__dict__.get(*args)

    def set(self, **kwargs):
        """Support dictionary get() functionality"""
        return self.__dict__.update(**kwargs)

    def dictcopy(self):
        """returns a deep copy of existing Bunch as a dictionary"""
        return deepcopy(self.__dict__)

    def __repr__(self):
        """Representation of the sorted Bunch as a string."""
        outstr = [f"{self.__class__.__name__}({self.__dict__['value']}"]
        for k, v in sorted(self.metadata().items()):
            outstr.append(", ")
            if isinstance(v, dict):
                pairs = []
                for key, value in sorted(v.items()):
                    pairs.append("'%s': %s" % (key, value))
                v = "{" + ", ".join(pairs) + "}"
                outstr.append("%s=%s" % (k, v))
            else:
                outstr.append("%s=%r" % (k, v))
        outstr.append(")")
        return "".join(outstr)
