
# Copyright (c) 2012 Oscar Campos <oscar.campos@member.fsf.org>
# See LICENSE for more details

from mamba import plugin


class ControllerProvider:
    """
    Mount point for plugins which refer to Controllers for our applications

    Controllers implementing this reference should implements the
    IController interface
    """

    __metaclass__ = plugin.ExtensionPoint
