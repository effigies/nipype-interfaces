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
"""Python library interface base."""
import logging
from ifsnipype.base.core import BaseInterface


iflogger = logging.getLogger("nipype.interface")


class LibraryBaseInterface(BaseInterface):
    _pkg = None
    imports = ()

    def __init__(self, check_import=True, *args, **kwargs):
        super(LibraryBaseInterface, self).__init__(*args, **kwargs)
        if check_import:
            import importlib.util

            failed_imports = []
            for pkg in (self._pkg,) + tuple(self.imports):
                if importlib.util.find_spec(pkg) is None:
                    failed_imports.append(pkg)
            if failed_imports:
                iflogger.warning(
                    "Unable to import %s; %s interface may fail to " "run",
                    failed_imports,
                    self.__class__.__name__,
                )

    @property
    def version(self):
        if self._version is None:
            import importlib

            try:
                self._version = importlib.import_module(self._pkg).__version__
            except (ImportError, AttributeError):
                pass
        return super(LibraryBaseInterface, self).version
